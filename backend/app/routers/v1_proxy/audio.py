"""POST /v1/audio/* — TTS (speech), STT (transcriptions), and voice listing."""

import json
import time
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.services.api_key_auth import validate_api_key
from app.services.proxy import (
    get_connections_cached,
    get_provider_strategy,
    select_connection_for_provider,
    clear_connection_error,
    update_connection_usage,
    calculate_cooldown,
    mark_connection_unavailable,
    parse_tts_model,
    _resolve_provider_alias,
    _resolve_base_url,
)
from app.services.tts_adapters import TTS_ADAPTERS, _format_to_mime
from app.services.usage_tracking import save_request_tracking
from app.models.provider import ProviderConnection
from app.services.stt_adapters import (
    STT_ADAPTERS,
    _FIXED_URL_STT_PROVIDERS,
    get_stt_adapter,
    resolve_audio_mime,
)

from .shared import _should_fallback_on_error

router = APIRouter()

_FIXED_URL_PROVIDERS: set[str] = {"gemini", "elevenlabs", "openrouter", "edge-tts"}


# ─────────────────────────────────────────────────────────────────────────────
# POST /v1/audio/speech (TTS)
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/audio/speech")
async def audio_speech(
    request: Request,
    response_format: str | None = Query(
        None, description="Audio format override: mp3 (default), wav, opus, aac, flac, json"
    ),
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> Response:
    """OpenAI-compatible TTS proxy.

    Model field encodes provider, model, and voice: ``provider/model/voice``.

    Examples:
      - ``openai/gpt-4o-mini-tts/alloy``           → openai, gpt-4o-mini-tts, alloy
      - ``openai/alloy``                           → openai, default model, alloy
      - ``siliconflow/FunAudioLLM/CosyVoice2/x``   → siliconflow, FunAudioLLM, CosyVoice2 (extras dropped)

    Iterasi 1 supports Group A providers: openai, siliconflow, hyperbolic.
    Other providers (gemini, elevenlabs, minimax, etc.) return 501 until
    their adapter is wired in.

    Response:
      - Default: binary audio with ``Content-Type: audio/{format}``
      - ``response_format=json``: ``{"audio": <base64>, "format": "mp3"}``
    """
    try:
        body: dict = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON body",
        )

    model_str: str | None = body.get("model")
    input_text: str | None = body.get("input")
    if not model_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: model",
        )
    if not input_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: input",
        )

    # ── 1. Parse provider from model string ──
    if "/" not in model_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model must be in 'provider/model/voice' or 'provider/voice' format",
        )

    provider_name, model_remainder = model_str.split("/", 1)
    provider_id: str = _resolve_provider_alias(provider_name)

    # ── 2. Adapter must exist for this provider ──
    adapter = TTS_ADAPTERS.get(provider_id)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"TTS provider '{provider_id}' is not yet supported. "
                f"Iterasi 1 supports: {', '.join(sorted(TTS_ADAPTERS.keys()))}"
            ),
        )

    # ── 3. Resolve tts_model + voice ──
    body_voice: str | None = body.get("voice")
    body_tts_model: str | None = body.get("tts_model")

    if body_tts_model and body_voice:
        tts_model, voice = body_tts_model, body_voice
    else:
        try:
            tts_model, voice = parse_tts_model(model_remainder)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        if body_tts_model:
            tts_model = body_tts_model
        if body_voice:
            voice = body_voice

    # ── 4. Response format (query param takes precedence over body) ──
    fmt: str = response_format or body.get("response_format") or "mp3"
    speed: float | None = body.get("speed")

    # ── 5. Lookup active connections + strategy ──
    connections = await get_connections_cached(db, provider_id)
    if not connections:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No active connection for provider: {provider_id}",
        )

    strategy, sticky_limit = await get_provider_strategy(db, provider_id)

    # ── 6. Fallback loop with cooldown, model lock, and strategy ──
    request_id: str = str(uuid.uuid4())
    exclude_ids: set[str] = set()
    last_error: dict | None = None

    while True:
        conn = select_connection_for_provider(
            connections=list(connections),
            provider_id=provider_id,
            strategy=strategy,
            sticky_limit=sticky_limit,
            exclude_ids=exclude_ids,
            model=tts_model,
        )
        if not conn:
            break

        conn_data: dict = json.loads(conn.data) if conn.data else {}
        api_key: str = conn_data.get("apiKey") or conn_data.get("api_key") or ""
        base_url: str = conn_data.get("baseUrl") or _resolve_base_url(provider_id, conn_data)
        conn_id: str = str(conn.id)

        if not base_url and provider_id not in _FIXED_URL_PROVIDERS:
            last_error = {"status": 500, "detail": f"No base_url for provider {provider_id}"}
            exclude_ids.add(conn_id)
            continue

        # Pass body-level `language` through for gemini (TTS prompt prefix).
        extra: dict = {}
        body_language: str | None = body.get("language")
        if body_language:
            extra["language"] = body_language

        try:
            request_start_time: float = time.time()
            async with httpx.AsyncClient(timeout=120.0) as client:
                audio_bytes, content_type = await adapter(
                    client,
                    base_url=base_url,
                    api_key=api_key,
                    tts_model=tts_model,
                    voice=voice,
                    input_text=input_text,
                    response_format=fmt if fmt != "json" else "mp3",
                    speed=speed,
                    **extra,
                )
            total_latency_ms: int = int((time.time() - request_start_time) * 1000)

            # Success — clear cooldown
            if conn_id:
                await clear_connection_error(db, conn_id, tts_model)
                await update_connection_usage(db, conn_id)

            # Track usage (TTS — no token counts)
            await save_request_tracking(
                db,
                provider=provider_id,
                model=tts_model,
                connection_id=conn_id,
                endpoint="/v1/audio/speech",
                latency_ttft=total_latency_ms,
                latency_total=total_latency_ms,
                request_body=body,
                provider_request_body={**body, "model": tts_model, "voice": voice},
                provider_response_body={"_note": "Binary audio response"},
                response_body={"_note": f"Audio response ({len(audio_bytes)} bytes, {content_type})"},
            )

            # Return audio (binary or json base64)
            if fmt == "json":
                import base64 as _b64
                return JSONResponse(
                    status_code=200,
                    content={
                        "audio": _b64.b64encode(audio_bytes).decode("ascii"),
                        "format": content_type.split("/")[-1],
                    },
                    headers={"X-Request-Id": request_id},
                )
            return Response(
                content=audio_bytes,
                media_type=content_type or _format_to_mime(fmt),
                headers={"X-Request-Id": request_id},
            )

        except httpx.HTTPStatusError as e:
            last_error = {"status": e.response.status_code, "detail": e.response.text[:500]}
            if not _should_fallback_on_error(e.response.status_code, e.response.text):
                return JSONResponse(
                    status_code=e.response.status_code,
                    content={"error": {"message": e.response.text[:500]}},
                    headers={"X-Request-Id": request_id},
                )
            if conn_id:
                conn_row = await db.execute(select(ProviderConnection).where(ProviderConnection.id == conn_id))
                conn_obj = conn_row.scalar_one_or_none()
                current_backoff: int = json.loads(conn_obj.data).get("backoffLevel", 0) if conn_obj and conn_obj.data else 0
                cooldown_ms, new_level = calculate_cooldown(e.response.status_code, last_error["detail"], backoff_level=current_backoff)
                await mark_connection_unavailable(db, conn_id, cooldown_ms, tts_model, new_level)
                exclude_ids.add(conn_id)
            continue
        except httpx.ConnectError as e:
            last_error = {"status": 503, "detail": f"Upstream connect error: {e}"}
            if conn_id:
                exclude_ids.add(conn_id)
            continue
        except Exception as e:
            last_error = {"status": 500, "detail": str(e)[:500]}
            if conn_id:
                exclude_ids.add(conn_id)
            continue

    # All connections failed
    err_msg: str = last_error.get("detail", "All TTS providers failed") if last_error else "No targets"
    err_status: int = last_error.get("status", 502) if last_error else 502
    return JSONResponse(
        status_code=err_status,
        content={"error": {"message": err_msg}},
        headers={"X-Request-Id": request_id},
    )


# ─────────────────────────────────────────────────────────────────────────────
# POST /v1/audio/transcriptions (STT)
# ─────────────────────────────────────────────────────────────────────────────


@router.post("/audio/transcriptions")
async def audio_transcriptions(
    request: Request,
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> JSONResponse:
    """OpenAI Whisper-compatible STT proxy (multipart form data).

    Body is ``multipart/form-data`` with fields:
      - ``file`` (required): audio file (mp3, wav, ogg, flac, webm, m4a, ...)
      - ``model`` (required): ``provider/model_id`` (e.g. ``openai/whisper-1``,
        ``deepgram/nova-3``, ``huggingface/openai/whisper-large-v3``)
      - ``language`` (optional): ISO 639-1 language code
      - ``prompt`` (optional): context hint for Whisper-style models
      - ``response_format`` (optional): json (default), text, srt, vtt, verbose_json
      - ``temperature`` (optional): 0.0–1.0

    Returns OpenAI-shaped JSON ``{"text": "..."}`` (or verbose with
    ``segments`` etc. when supported by the provider).

    Supported providers (Iterasi 1): openai, groq, azure, deepgram, gemini,
    assemblyai, huggingface, nvidia.
    """
    # Parse multipart form
    try:
        form = await request.form()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid multipart body: {e}",
        )

    file_field = form.get("file")
    model_str: str = (form.get("model") or "").strip() if form.get("model") else ""
    language: str = (form.get("language") or "").strip() if form.get("language") else ""
    prompt: str = (form.get("prompt") or "").strip() if form.get("prompt") else ""
    response_format_str: str = (
        (form.get("response_format") or "").strip()
        if form.get("response_format")
        else ""
    )
    temperature_raw = form.get("temperature") or ""

    if not file_field or not hasattr(file_field, "read"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: file (must be a multipart file upload)",
        )
    if not model_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required field: model",
        )

    # ── 1. Parse provider from model string ──
    if "/" not in model_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model must be in 'provider/model' format (e.g. 'openai/whisper-1')",
        )

    provider_name, model_id = model_str.split("/", 1)
    provider_id: str = _resolve_provider_alias(provider_name)

    # ── 2. Adapter must exist ──
    adapter = get_stt_adapter(provider_id)
    if adapter is None:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"STT provider '{provider_id}' is not yet supported. "
                f"Iterasi 1 supports: {', '.join(sorted(STT_ADAPTERS.keys()))}"
            ),
        )

    # ── 3. Parse temperature (validation) ──
    temperature: float | None = None
    if temperature_raw:
        try:
            temperature = float(temperature_raw)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid temperature value: {temperature_raw!r}",
            )

    # ── 4. Read file bytes + resolve MIME ──
    file_bytes: bytes = await file_field.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )
    filename: str = getattr(file_field, "filename", None) or "audio.wav"
    declared_ct: str = getattr(file_field, "content_type", "") or ""
    content_type: str = resolve_audio_mime(filename, declared_ct)

    # ── 5. Lookup active connections + strategy ──
    connections = await get_connections_cached(db, provider_id)
    if not connections:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"No active connection for provider: {provider_id}",
        )

    strategy, sticky_limit = await get_provider_strategy(db, provider_id)

    # ── 6. Fallback loop with cooldown, model lock, and strategy ──
    request_id: str = str(uuid.uuid4())
    exclude_ids: set[str] = set()
    last_error: dict | None = None

    while True:
        conn = select_connection_for_provider(
            connections=list(connections),
            provider_id=provider_id,
            strategy=strategy,
            sticky_limit=sticky_limit,
            exclude_ids=exclude_ids,
            model=model_id,
        )
        if not conn:
            break

        conn_data: dict = json.loads(conn.data) if conn.data else {}
        api_key: str = conn_data.get("apiKey") or conn_data.get("api_key") or ""
        base_url: str = conn_data.get("baseUrl") or _resolve_base_url(provider_id, conn_data)
        conn_id: str = str(conn.id)

        if not base_url and provider_id not in _FIXED_URL_STT_PROVIDERS:
            last_error = {"status": 500, "detail": f"No base_url for provider {provider_id}"}
            exclude_ids.add(conn_id)
            continue

        # Azure deployment override (only relevant for azure provider).
        extra_url: str | None = None
        if provider_id == "azure":
            endpoint: str = conn_data.get("azureEndpoint") or base_url
            deployment: str = conn_data.get("deployment", "whisper")
            api_version: str = conn_data.get("apiVersion", "2024-06-01")
            if not endpoint or not deployment:
                last_error = {"status": 500, "detail": "Azure STT requires azureEndpoint and deployment"}
                exclude_ids.add(conn_id)
                continue
            extra_url = (
                f"{endpoint.rstrip('/')}/openai/deployments/{deployment}"
                f"/audio/transcriptions?api-version={api_version}"
            )

        try:
            request_start_time: float = time.time()
            async with httpx.AsyncClient(timeout=180.0) as client:
                result_payload: dict = await adapter(
                    client,
                    base_url=base_url,
                    api_key=api_key,
                    model=model_id,
                    file_bytes=file_bytes,
                    filename=filename,
                    content_type=content_type,
                    language=language or None,
                    prompt=prompt or None,
                    response_format=response_format_str or None,
                    temperature=temperature,
                    extra_url=extra_url,
                    auth_header="api-key" if provider_id == "azure" else "Authorization",
                    auth_prefix="" if provider_id == "azure" else "Bearer ",
                )
            total_latency_ms: int = int((time.time() - request_start_time) * 1000)

            # Success — clear cooldown
            if conn_id:
                await clear_connection_error(db, conn_id, model_id)
                await update_connection_usage(db, conn_id)

            # Track usage (STT — no token counts)
            await save_request_tracking(
                db,
                provider=provider_id,
                model=model_id,
                connection_id=conn_id,
                endpoint="/v1/audio/transcriptions",
                latency_ttft=total_latency_ms,
                latency_total=total_latency_ms,
                request_body={"model": model_str, "language": language, "response_format": response_format_str},
                provider_request_body={"model": model_id, "language": language, "response_format": response_format_str},
                provider_response_body=result_payload,
                response_body=result_payload,
            )

            return JSONResponse(
                status_code=200,
                content=result_payload,
                headers={"X-Request-Id": request_id},
            )

        except httpx.HTTPStatusError as e:
            last_error = {"status": e.response.status_code, "detail": e.response.text[:500]}
            if not _should_fallback_on_error(e.response.status_code, e.response.text):
                return JSONResponse(
                    status_code=e.response.status_code,
                    content={"error": {"message": e.response.text[:500]}},
                    headers={"X-Request-Id": request_id},
                )
            if conn_id:
                conn_row = await db.execute(select(ProviderConnection).where(ProviderConnection.id == conn_id))
                conn_obj = conn_row.scalar_one_or_none()
                current_backoff: int = json.loads(conn_obj.data).get("backoffLevel", 0) if conn_obj and conn_obj.data else 0
                cooldown_ms, new_level = calculate_cooldown(e.response.status_code, last_error["detail"], backoff_level=current_backoff)
                await mark_connection_unavailable(db, conn_id, cooldown_ms, model_id, new_level)
                exclude_ids.add(conn_id)
            continue
        except httpx.ConnectError as e:
            last_error = {"status": 503, "detail": f"Upstream connect error: {e}"}
            if conn_id:
                exclude_ids.add(conn_id)
            continue
        except ValueError as e:
            return JSONResponse(
                status_code=400,
                content={"error": {"message": str(e)}},
                headers={"X-Request-Id": request_id},
            )
        except Exception as e:
            last_error = {"status": 500, "detail": str(e)[:500]}
            if conn_id:
                exclude_ids.add(conn_id)
            continue

    # All connections failed
    err_msg: str = last_error.get("detail", "All STT providers failed") if last_error else "No targets"
    err_status: int = last_error.get("status", 502) if last_error else 502
    return JSONResponse(
        status_code=err_status,
        content={"error": {"message": err_msg}},
        headers={"X-Request-Id": request_id},
    )


# ─────────────────────────────────────────────────────────────────────────────
# GET /v1/audio/voices
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/audio/voices")
async def audio_voices(
    provider: str = Query(..., description="TTS provider ID"),
    lang: str = Query(None, description="Filter by language code (ISO 639-1)"),
    db: AsyncSession = Depends(get_db),
    api_key_info: dict = Depends(validate_api_key),
) -> JSONResponse:
    """List available TTS voices for a provider.

    Plan: docs/plans/v1-audio-voices.md (Phase 4).
    """
    from app.services.voice_fetchers import (
        VOICE_FETCHER_PROVIDERS,
        fetch_voices_cached,
        is_no_key_provider,
    )
    from app.services.proxy import ID_TO_ALIAS

    if provider not in VOICE_FETCHER_PROVIDERS:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "message": (
                        f"provider must be one of: "
                        f"{', '.join(sorted(VOICE_FETCHER_PROVIDERS))}"
                    ),
                    "type": "invalid_request_error",
                }
            },
        )

    # Get API key from DB (not needed for edge-tts / local-device / gemini)
    api_key: str = ""
    if not is_no_key_provider(provider):
        result = await db.execute(
            select(ProviderConnection).where(
                ProviderConnection.provider == provider,
                ProviderConnection.is_active == True,
            ).order_by(ProviderConnection.priority)
        )
        conn = result.scalars().first()
        if not conn:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": f"No {provider} connection found",
                        "type": "invalid_request_error",
                    }
                },
            )
        data: dict = json.loads(conn.data) if conn.data else {}
        api_key = data.get("apiKey") or data.get("api_key") or ""
        if not api_key:
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "message": f"No API key stored for {provider}",
                        "type": "invalid_request_error",
                    }
                },
            )

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            voices = await fetch_voices_cached(client, provider, api_key, lang)
    except Exception as e:
        return JSONResponse(
            status_code=502,
            content={
                "error": {
                    "message": str(e) or "upstream voice fetch failed",
                    "type": "server_error",
                }
            },
        )

    alias: str = ID_TO_ALIAS.get(provider, provider)
    data_out: list[dict] = [
        {
            "id": v["id"],
            "name": v["name"],
            "lang": v.get("lang", ""),
            "gender": v.get("gender", ""),
            "model": f"{alias}/{v['id']}",
        }
        for v in voices
    ]
    return JSONResponse(content={"object": "list", "data": data_out})
