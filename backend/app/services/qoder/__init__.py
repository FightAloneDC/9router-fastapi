"""Qoder provider services.

This module contains the Qoder-specific implementations for:
- Device flow authentication (PKCE + nonce)
- COSY signing (RSA + AES + MD5)
- WAF-bypass body encoding
- Model catalog fetching
- Usage/quota fetching
"""

from .auth import (
    generate_pkce_pair,
    initiate_device_flow,
    poll_device_token,
    fetch_user_info,
)
from .cosy import (
    build_cosy_headers,
    generate_machine_id,
)
from .encoding import qoder_encode_body
from .models import (
    resolve_qoder_models,
    get_qoder_model_config,
)
from .constants import (
    QODER_MODEL_MAP,
    QODER_CHAT_URL_ENCODED,
    QODER_QUOTA_USAGE_URL,
)

__all__ = [
    "generate_pkce_pair",
    "initiate_device_flow",
    "poll_device_token",
    "fetch_user_info",
    "build_cosy_headers",
    "generate_machine_id",
    "qoder_encode_body",
    "resolve_qoder_models",
    "get_qoder_model_config",
    "QODER_MODEL_MAP",
    "QODER_CHAT_URL_ENCODED",
    "QODER_QUOTA_USAGE_URL",
]
