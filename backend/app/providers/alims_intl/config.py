"""Alibaba Studio provider definition.

Model Studio Intl — standard DashScope API keys (sk-...), NOT Coding
Plan keys.  Sibling of alicode-intl (Coding Plan).  Two key types use
two different hosts.

Static provider characteristics — runtime data (API keys, custom
baseUrl) come from ProviderConnection.data in the database.
"""

from app.providers.base import BaseMetadata, BaseProviderConfig


class AlimsIntlConfig(BaseProviderConfig):
    """Alibaba Studio provider configuration."""

    # ── Identity ────────────────────────────────────────────────────────
    PROVIDER_NAME: str = "Alibaba Studio"
    PROVIDER_ID: str = "alims-intl"
    ALIAS: str = "alims-intl"
    BASE_URL: str = (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )
    SERVICE_KINDS: list[str] = [
        "llm", "rerank", "embedding", "image",
        "video", "tts", "stt",
    ]
    MODEL_CATALOG_TABLE: bool = True
    # International (Singapore) defaults from Model Studio
    # docs (.scratch/alibaba-studio-ratelimit.md).
    # RPM-only rows: image/video/tts/stt without TPM.
    # RPS docs converted to RPM (×60).
    RATE_LIMITS: dict[str, dict[str, int]] = {
        "qwen3.8-max": {"rpm": 15000, "tpm": 2000000},
        "qwen3.7-max": {"rpm": 600, "tpm": 1000000},
        "qwen3.7-max-2026-06-08": {"rpm": 60, "tpm": 1000000},
        "qwen3.7-max-2026-05-20": {"rpm": 60, "tpm": 1000000},
        "qwen3.7-max-preview": {"rpm": 600, "tpm": 1000000},
        "qwen3.7-max-2026-05-17": {"rpm": 600, "tpm": 1000000},
        "qwen3.6-max-preview": {"rpm": 600, "tpm": 1000000},
        "qwen3-max": {"rpm": 600, "tpm": 1000000},
        "qwen3-max-2026-01-23": {"rpm": 600, "tpm": 1000000},
        "qwen3-max-2025-09-23": {"rpm": 60, "tpm": 100000},
        "qwen3-max-preview": {"rpm": 600, "tpm": 1000000},
        "qwen3.7-plus": {"rpm": 15000, "tpm": 5000000},
        "qwen3.7-plus-2026-05-26": {"rpm": 60, "tpm": 1000000},
        "qwen3.6-plus": {"rpm": 15000, "tpm": 5000000},
        "qwen3.6-plus-2026-04-02": {"rpm": 60, "tpm": 1000000},
        "qwen3.7-flash": {"rpm": 15000, "tpm": 5000000},
        "qwen3.7-flash-2026-07-15": {"rpm": 15000, "tpm": 5000000},
        "qwen3.6-flash": {"rpm": 15000, "tpm": 5000000},
        "qwen3.6-flash-2026-04-16": {"rpm": 60, "tpm": 1000000},
        "qwen3.5-plus": {"rpm": 15000, "tpm": 5000000},
        "qwen3.5-plus-2026-04-20": {"rpm": 600, "tpm": 1000000},
        "qwen3.5-plus-2026-02-15": {"rpm": 60, "tpm": 1000000},
        "qwen-plus-latest": {"rpm": 600, "tpm": 1000000},
        "qwen-plus-2025-12-01": {"rpm": 120, "tpm": 1000000},
        "qwen-plus-2025-09-11": {"rpm": 120, "tpm": 1000000},
        "qwen-plus-2025-07-28": {"rpm": 60, "tpm": 100000},
        "qwen-plus-2025-07-14": {"rpm": 60, "tpm": 100000},
        "qwen-plus-0714": {"rpm": 60, "tpm": 100000},
        "qwen-plus-2025-04-28": {"rpm": 60, "tpm": 1000000},
        "qwen-plus-0428": {"rpm": 60, "tpm": 1000000},
        "qwen-plus-2025-01-25": {"rpm": 60, "tpm": 100000},
        "qwen-plus-0125": {"rpm": 60, "tpm": 100000},
        "qwen3.5-flash": {"rpm": 15000, "tpm": 5000000},
        "qwen3.5-flash-2026-02-23": {"rpm": 60, "tpm": 1000000},
        "qwen-flash-2025-07-28": {"rpm": 600, "tpm": 5000000},
        "qwq-plus": {"rpm": 60, "tpm": 100000},
        "qwen3-vl-plus": {"rpm": 1200, "tpm": 1000000},
        "qwen3-vl-plus-2025-12-19": {"rpm": 60, "tpm": 100000},
        "qwen3-vl-plus-2025-09-23": {"rpm": 120, "tpm": 1000000},
        "qwen3-vl-flash": {"rpm": 1200, "tpm": 1000000},
        "qwen3-vl-flash-2026-01-22": {"rpm": 60, "tpm": 100000},
        "qwen3-vl-flash-2025-10-15": {"rpm": 120, "tpm": 1000000},
        "qwen-vl-max": {"rpm": 1200, "tpm": 1000000},
        "qwen-vl-plus": {"rpm": 1200, "tpm": 1000000},
        "qvq-max": {"rpm": 60, "tpm": 100000},
        "qwen3.5-omni-flash": {"rpm": 60, "tpm": 100000},
        "qwen3.5-omni-flash-2026-03-15": {"rpm": 60, "tpm": 100000},
        "qwen3.5-omni-plus": {"rpm": 60, "tpm": 100000},
        "qwen3.5-omni-plus-2026-03-15": {"rpm": 60, "tpm": 100000},
        "qwen3-omni-flash": {"rpm": 60, "tpm": 100000},
        "qwen3-omni-flash-2025-12-01": {"rpm": 60, "tpm": 100000},
        "qwen3-omni-flash-2025-09-15": {"rpm": 60, "tpm": 100000},
        "qwen-omni-turbo": {"rpm": 60, "tpm": 100000},
        "qwen-omni-turbo-latest": {"rpm": 60, "tpm": 100000},
        "qwen-omni-turbo-2025-03-26": {"rpm": 60, "tpm": 100000},
        "qwen3.5-omni-plus-realtime": {"rpm": 60, "tpm": 100000},
        "qwen3.5-omni-plus-realtime-2026-03-15": {"rpm": 60, "tpm": 100000},
        "qwen3.5-omni-flash-realtime": {"rpm": 60, "tpm": 100000},
        "qwen3.5-omni-flash-realtime-2026-03-15": {"rpm": 60, "tpm": 100000},
        "qwen3-omni-flash-realtime": {"rpm": 60, "tpm": 100000},
        "qwen3-omni-flash-realtime-2025-12-01": {"rpm": 60, "tpm": 100000},
        "qwen3-omni-flash-realtime-2025-09-15": {"rpm": 60, "tpm": 100000},
        "qwen-omni-turbo-realtime": {"rpm": 60, "tpm": 10000},
        "qwen-omni-turbo-realtime-latest": {"rpm": 60, "tpm": 10000},
        "qwen-omni-turbo-realtime-2025-05-08": {
            "rpm": 60, "tpm": 10000,
        },
        "qwen-vl-ocr": {"rpm": 600, "tpm": 6000000},
        "qwen-vl-ocr-2025-11-20": {"rpm": 1200, "tpm": 6000000},
        "qwen3-coder-plus": {"rpm": 2400, "tpm": 2000000},
        "qwen3-coder-plus-2025-09-23": {"rpm": 600, "tpm": 1000000},
        "qwen3-coder-plus-2025-07-22": {"rpm": 60, "tpm": 1000000},
        "qwen3-coder-flash": {"rpm": 600, "tpm": 5000000},
        "qwen3-coder-flash-2025-07-28": {"rpm": 600, "tpm": 5000000},
        "qwen-mt-plus": {"rpm": 60, "tpm": 100000},
        "qwen-mt-flash": {"rpm": 60, "tpm": 100000},
        "qwen-mt-lite": {"rpm": 60, "tpm": 100000},
        "qwen-mt-turbo": {"rpm": 60, "tpm": 100000},
        "qwen3.8-2.4t-a95b": {"rpm": 5000, "tpm": 5000000},
        "qwen3.6-35b-a3b": {"rpm": 600, "tpm": 1000000},
        "qwen3.6-27b": {"rpm": 600, "tpm": 1000000},
        "qwen3.5-397b-a17b": {"rpm": 600, "tpm": 1000000},
        "qwen3.5-122b-a10b": {"rpm": 600, "tpm": 1000000},
        "qwen3.5-27b": {"rpm": 600, "tpm": 1000000},
        "qwen3.5-35b-a3b": {"rpm": 600, "tpm": 5000000},
        "qwen3-next-80b-a3b-thinking": {"rpm": 600, "tpm": 1000000},
        "qwen3-next-80b-a3b-instruct": {"rpm": 600, "tpm": 1000000},
        "qwen3-235b-a22b-thinking-2507": {"rpm": 600, "tpm": 1000000},
        "qwen3-235b-a22b-instruct-2507": {"rpm": 600, "tpm": 1000000},
        "qwen3-30b-a3b-thinking-2507": {"rpm": 600, "tpm": 5000000},
        "qwen3-30b-a3b-instruct-2507": {"rpm": 600, "tpm": 5000000},
        "qwen3-235b-a22b": {"rpm": 600, "tpm": 1000000},
        "qwen3-32b": {"rpm": 600, "tpm": 1000000},
        "qwen3-30b-a3b": {"rpm": 600, "tpm": 1000000},
        "qwen3-14b": {"rpm": 600, "tpm": 1000000},
        "qwen3-8b": {"rpm": 600, "tpm": 1000000},
        "qwen3-vl-32b-thinking": {"rpm": 60, "tpm": 100000},
        "qwen3-vl-32b-instruct": {"rpm": 60, "tpm": 100000},
        "qwen3-vl-30b-a3b-thinking": {"rpm": 60, "tpm": 100000},
        "qwen3-vl-30b-a3b-instruct": {"rpm": 60, "tpm": 100000},
        "qwen3-vl-8b-thinking": {"rpm": 60, "tpm": 100000},
        "qwen3-vl-8b-instruct": {"rpm": 60, "tpm": 100000},
        "qwen3-vl-235b-a22b-thinking": {"rpm": 60, "tpm": 100000},
        "qwen3-vl-235b-a22b-instruct": {"rpm": 60, "tpm": 100000},
        "qwen2.5-omni-7b": {"rpm": 60, "tpm": 100000},
        "qwen3-omni-30b-a3b-captioner": {"rpm": 60, "tpm": 100000},
        "qwen3-coder-next": {"rpm": 600, "tpm": 1000000},
        "qwen3-coder-480b-a35b-instruct": {"rpm": 600, "tpm": 1000000},
        "qwen3-coder-30b-a3b-instruct": {"rpm": 600, "tpm": 1000000},
        "deepseek-v4-pro": {"rpm": 10000, "tpm": 1200000},
        "deepseek-v4-pro-0813": {"rpm": 10000, "tpm": 1200000},
        "deepseek-v4-flash-0731": {"rpm": 15000, "tpm": 1200000},
        "deepseek-v4-flash": {"rpm": 10000, "tpm": 1200000},
        "deepseek-v3.2": {"rpm": 10000, "tpm": 1200000},
        "kimi-k2.7-code": {"rpm": 500, "tpm": 1000000},
        "glm-5.2": {"rpm": 500, "tpm": 1000000},
        "glm-5.1": {"rpm": 500, "tpm": 1000000},
        "ZHIPU/GLM-5.2": {"rpm": 200, "tpm": 3000000},
        "qwen-image-3.0-pro": {"rpm": 5},
        "qwen-image-3.0": {"rpm": 20},
        "qwen-image-2.0-pro": {"rpm": 2},
        "qwen-image-2.0-pro-2026-06-22": {"rpm": 2},
        "qwen-image-2.0-pro-2026-04-22": {"rpm": 2},
        "qwen-image-2.0-pro-2026-03-03": {"rpm": 2},
        "qwen-image-2.0": {"rpm": 120},
        "qwen-image-2.0-2026-03-03": {"rpm": 120},
        "qwen-image-max": {"rpm": 2},
        "qwen-image-max-2025-12-30": {"rpm": 2},
        "qwen-image-plus": {"rpm": 120},
        "qwen-image-plus-2026-01-09": {"rpm": 120},
        "qwen-image": {"rpm": 120},
        "qwen-image-edit-max": {"rpm": 2},
        "qwen-image-edit-max-2026-01-16": {"rpm": 2},
        "qwen-image-edit-plus": {"rpm": 120},
        "qwen-image-edit-plus-2025-12-15": {"rpm": 120},
        "qwen-image-edit-plus-2025-10-30": {"rpm": 120},
        "qwen-image-edit": {"rpm": 120},
        "z-image-turbo": {"rpm": 120},
        "wan2.7-image-pro": {"rpm": 300},
        "wan2.7-image": {"rpm": 300},
        "wan2.6-image": {"rpm": 300},
        "wan2.6-t2i": {"rpm": 300},
        "wan2.5-t2i-preview": {"rpm": 300},
        "wan2.2-t2i-flash": {"rpm": 120},
        "wan2.2-t2i-plus": {"rpm": 120},
        "wan2.1-t2i-turbo": {"rpm": 120},
        "wan2.1-t2i-plus": {"rpm": 120},
        "wan2.5-i2i-preview": {"rpm": 300},
        "happyhorse-1.1-t2v": {"rpm": 300},
        "happyhorse-1.1-i2v": {"rpm": 300},
        "happyhorse-1.1-r2v": {"rpm": 300},
        "happyhorse-1.0-t2v": {"rpm": 300},
        "happyhorse-1.0-i2v": {"rpm": 300},
        "happyhorse-1.0-r2v": {"rpm": 300},
        "happyhorse-1.0-video-edit": {"rpm": 300},
        "wan2.7-r2v-2026-06-12": {"rpm": 300},
        "wan2.7-t2v-2026-06-12": {"rpm": 300},
        "wan2.7-t2v-2026-04-25": {"rpm": 300},
        "wan2.7-t2v": {"rpm": 300},
        "wan2.6-t2v": {"rpm": 300},
        "wan2.5-t2v-preview": {"rpm": 300},
        "wan2.2-t2v-plus": {"rpm": 120},
        "wan2.1-t2v-turbo": {"rpm": 120},
        "wan2.1-t2v-plus": {"rpm": 120},
        "wan2.7-i2v-2026-04-25": {"rpm": 300},
        "wan2.7-i2v": {"rpm": 300},
        "wan2.6-i2v-flash": {"rpm": 300},
        "wan2.6-i2v": {"rpm": 300},
        "wan2.5-i2v-preview": {"rpm": 300},
        "wan2.2-i2v-flash": {"rpm": 120},
        "wan2.1-i2v-plus": {"rpm": 120},
        "wan2.1-i2v-turbo": {"rpm": 120},
        "wan2.2-i2v-plus": {"rpm": 120},
        "wan2.2-kf2v-flash": {"rpm": 120},
        "wan2.1-kf2v-plus": {"rpm": 60},
        "wan2.1-vace-plus": {"rpm": 120},
        "wan2.7-videoedit": {"rpm": 300},
        "wan2.7-r2v": {"rpm": 300},
        "wan2.6-r2v-flash": {"rpm": 300},
        "wan2.6-r2v": {"rpm": 300},
        "wan2.2-animate-move": {"rpm": 300},
        "wan2.2-animate-mix": {"rpm": 300},
        "qwen-audio-3.0-realtime-plus": {"rpm": 60, "tpm": 100000},
        "qwen-audio-3.0-realtime-flash": {"rpm": 60, "tpm": 100000},
        "qwen-audio-3.0-tts-plus": {"rpm": 180},
        "qwen-audio-3.0-tts-flash": {"rpm": 180},
        "qwen3-tts-instruct-flash": {"rpm": 180},
        "qwen3-tts-instruct-flash-2026-01-26": {"rpm": 180},
        "qwen3-tts-vd-2026-01-26": {"rpm": 180},
        "qwen3-tts-vc-2026-01-22": {"rpm": 180},
        "qwen3-tts-flash": {"rpm": 180},
        "qwen3-tts-flash-2025-11-27": {"rpm": 180},
        "qwen3-tts-flash-2025-09-18": {"rpm": 10},
        "qwen3-tts-instruct-flash-realtime": {"rpm": 180},
        "qwen3-tts-instruct-flash-realtime-2026-01-22": {"rpm": 180},
        "qwen3-tts-vd-realtime-2026-01-15": {"rpm": 180},
        "qwen3-tts-vc-realtime-2026-01-15": {"rpm": 180},
        "qwen3-tts-flash-realtime": {"rpm": 180},
        "qwen3-tts-flash-realtime-2025-11-27": {"rpm": 180},
        "qwen3-tts-flash-realtime-2025-09-18": {"rpm": 10},
        "qwen-voice-enrollment": {"rpm": 180},
        "qwen-voice-design": {"rpm": 180},
        "cosyvoice-v3-plus": {"rpm": 180},
        "voice-enrollment": {"rpm": 600},
        "qwen3-livetranslate-flash": {"rpm": 100, "tpm": 100000},
        "qwen3-livetranslate-flash-2025-12-01": {"rpm": 100, "tpm": 100000},
        "qwen3.5-livetranslate-flash-realtime": {"rpm": 10, "tpm": 100000},
        "qwen-audio-3.0-asr-flash-streaming": {"rpm": 1200},
        "qwen-audio-3.0-asr-flash-filetrans": {"rpm": 600},
        "qwen-audio-3.0-asr-flash": {"rpm": 600},
        "qwen3-asr-flash-filetrans": {"rpm": 100},
        "qwen3-asr-flash": {"rpm": 100},
        "qwen3-asr-flash-realtime": {"rpm": 1200},
        "fun-asr": {"rpm": 600},
        "fun-asr-2025-11-07": {"rpm": 600},
        "fun-asr-2025-08-25": {"rpm": 600},
        "fun-asr-mtl": {"rpm": 100},
        "fun-asr-mtl-2025-08-25": {"rpm": 100},
        "fun-asr-flash-2026-06-15": {"rpm": 600},
        "fun-asr-realtime": {"rpm": 1200},
        "text-embedding-v4": {"rpm": 1800, "tpm": 1000000},
        "text-embedding-v3": {"rpm": 6000, "tpm": 24000000},
        "tongyi-embedding-vision-plus": {"rpm": 600, "tpm": 200000},
        "tongyi-embedding-vision-flash": {"rpm": 600, "tpm": 200000},
        "qwen3-rerank": {"rpm": 5400, "tpm": 5000000000},
        "qwen-plus-character": {"rpm": 120, "tpm": 500000},
        "qwen-flash-character": {"rpm": 120, "tpm": 500000},
        "qwen-plus-character-ja": {"rpm": 120, "tpm": 500000},
    }


    # ── Bulk Import ─────────────────────────────────────────────────────
    SUPPORTS_BULK_IMPORT: bool = True
    BULK_IMPORT_FORMAT: str = "farm-json"


class AlimsIntlMetadata(BaseMetadata):
    """Alibaba Studio UI display metadata."""

    name: str = "Alibaba Studio"
    color: str = "#FF6A00"
    textIcon: str = "ALi"
    icon: str = "Cloud"
    website: str = "https://modelstudio.console.alibabacloud.com"
    notice: dict | None = {
        "text": (
            "International RPM/TPM from Model Studio docs "
            "(Singapore). Quota Tracker shows last-60s totals; "
            "use Model details for per-model bars. Temporary "
            "raises: console Limits."
        ),
        "apiKeyUrl": (
            "https://modelstudio.console.alibabacloud.com/?apiKey=1"
        ),
    }
