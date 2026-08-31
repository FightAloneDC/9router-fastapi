"""MiMo Code Free handler — bootstrap JWT with anti-abuse measures.

Impersonates MiMo Code CLI desktop client. Uses bootstrap endpoint
to obtain JWT tokens, then routes chat requests through the free AI
endpoint. Includes anti-abuse measures: system marker, Chrome-like
User-Agent, and session affinity.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import platform
import random
import string
import time

import httpx

from app.providers.base import BaseProviderHandler, ValidateResult

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

BOOTSTRAP_URL = "https://api.xiaomimimo.com/api/free-ai/bootstrap"
CHAT_URL = "https://api.xiaomimimo.com/api/free-ai/openai/chat"

SESSION_AFFINITY_PREFIX = "ses_"
SESSION_ID_LENGTH = 24
SESSION_CHARS = string.ascii_lowercase + string.digits

JWT_FALLBACK_TTL_SEC = 3000
JWT_EXPIRY_BUFFER_MS = 300000
BOOTSTRAP_TIMEOUT = 10.0

# Anti-abuse: upstream rejects requests without Chrome-like User-Agent
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

# Anti-abuse marker: system message must contain this substring
MIMO_SYSTEM_MARKER = (
    "You are MiMoCode, an interactive CLI tool that helps users "
    "with software engineering tasks."
)


# ── JWT Cache ─────────────────────────────────────────────────────────────

_cached_jwt: str | None = None
_jwt_expires_at: float = 0


def _reset_jwt_cache() -> None:
    """Invalidate cached JWT."""
    global _cached_jwt, _jwt_expires_at
    _cached_jwt = None
    _jwt_expires_at = 0


def _parse_jwt_exp(jwt: str) -> float:
    """Derive expiry from JWT exp claim; fallback to fixed TTL."""
    try:
        payload_b64 = jwt.split(".")[1]
        # Add padding if needed
        payload_b64 += "=" * (4 - len(payload_b64) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        if payload.get("exp"):
            return payload["exp"] * 1000
    except Exception:
        pass
    return (time.time() + JWT_FALLBACK_TTL_SEC) * 1000


def _generate_fingerprint() -> str:
    """Generate device fingerprint for bootstrap client."""
    try:
        username = os.environ.get("USER") or os.environ.get("LOGNAME") or "unknown-user"
    except Exception:
        username = "unknown-user"

    try:
        cpu = platform.processor() or "unknown-cpu"
        if not cpu:
            cpu = "unknown-cpu"
        seed = f"{platform.node()}|{platform.system()}|{platform.machine()}|{cpu}|{username}"
    except Exception:
        seed = f"unknown|{username}"

    return hashlib.sha256(seed.encode()).hexdigest()


def _generate_session_id() -> str:
    """Generate random session affinity ID."""
    suffix = "".join(random.choices(SESSION_CHARS, k=SESSION_ID_LENGTH))
    return f"{SESSION_AFFINITY_PREFIX}{suffix}"


# ── Bootstrap ─────────────────────────────────────────────────────────────

async def _bootstrap_jwt() -> str:
    """Obtain JWT from bootstrap endpoint (cached)."""
    global _cached_jwt, _jwt_expires_at

    # Return cached JWT if still valid
    if _cached_jwt and time.time() * 1000 < _jwt_expires_at - JWT_EXPIRY_BUFFER_MS:
        return _cached_jwt

    fingerprint = _generate_fingerprint()

    async with httpx.AsyncClient(timeout=BOOTSTRAP_TIMEOUT) as client:
        resp = await client.post(
            BOOTSTRAP_URL,
            json={"client": fingerprint},
            headers={
                "Content-Type": "application/json",
                "User-Agent": random.choice(USER_AGENTS),
            },
        )
        resp.raise_for_status()

    data = resp.json()
    jwt = data.get("jwt")
    if not jwt:
        raise ValueError("MiMo bootstrap returned no JWT")

    _cached_jwt = jwt
    _jwt_expires_at = _parse_jwt_exp(jwt)

    logger.info("MiMo bootstrap success, JWT expires at %s", _jwt_expires_at)
    return jwt


# ── Handler ───────────────────────────────────────────────────────────────

class MimoFreeHandler(BaseProviderHandler):
    """Handler for MiMo Code Free provider."""

    async def validate(
        self,
        api_key: str = "",
        data: dict | None = None,
    ) -> ValidateResult:
        """NoAuth provider — always valid, no key to check."""
        return ValidateResult(valid=True, latency_ms=0)

    async def fetch_models(
        self,
        api_key: str = "",
        data: dict | None = None,
    ) -> list[dict]:
        """Return available free models.

        MiMo Free endpoint supports mimo-auto model.
        """
        return [
            {"id": "mimo-auto", "name": "MiMo Auto"},
        ]

    def build_upstream_url(
        self,
        base_url: str,
        stream: bool = False,
        data: dict | None = None,
        model: str = "",
    ) -> str:
        """Route to MiMo free chat endpoint."""
        return CHAT_URL

    def build_headers(
        self,
        api_key: str = "",
        stream: bool = False,
        data: dict | None = None,
    ) -> dict[str, str]:
        """Build headers impersonating MiMo Code CLI client.

        JWT is injected later in execute_request.
        """
        return {
            "Content-Type": "application/json",
            "X-Mimo-Source": "mimocode-cli-free",
            "User-Agent": random.choice(USER_AGENTS),
            "x-session-affinity": _generate_session_id(),
        }

    async def prepare_request(
        self,
        headers: dict[str, str],
        body: dict,
        stream: bool = False,
    ) -> tuple[dict[str, str], dict]:
        """Bootstrap JWT and inject system marker before sending request.

        Called by the proxy after build_headers but before sending.
        """
        # Bootstrap JWT
        jwt = await _bootstrap_jwt()
        headers["Authorization"] = f"Bearer {jwt}"
        if stream:
            headers["Accept"] = "text/event-stream"

        # Inject system marker
        body = _inject_system_marker(body)

        return headers, body


def _inject_system_marker(body: dict) -> dict:
    """Ensure system message with MiMo marker is present (idempotent)."""
    messages = body.get("messages")
    if not isinstance(messages, list):
        return body

    # Check if marker already present
    has_marker = any(
        m.get("role") == "system"
        and isinstance(m.get("content"), str)
        and MIMO_SYSTEM_MARKER in m["content"]
        for m in messages
    )

    if has_marker:
        return body

    # Inject marker as first system message
    return {
        **body,
        "messages": [
            {"role": "system", "content": MIMO_SYSTEM_MARKER},
            *messages,
        ],
    }
