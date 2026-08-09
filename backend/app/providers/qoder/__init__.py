"""Qoder provider module.

All Qoder-specific code lives here:
- auth: OAuth device flow + PAT import
- constants: URLs, COSY constants
- cosy: COSY signing (RSA + AES + MD5)
- encoding: WAF-bypass body encoding
- models: Model catalog fetching
- quota: Usage/quota fetching (quota tracker hook)
- transform: Request/response transformation
- config: Provider configuration
- handler: Handler methods
"""

from .auth import (
    generate_pkce_pair,
    initiate_device_flow,
    poll_device_token,
    fetch_user_info,
    exchange_personal_token,
    import_pat,
)
from .cosy import (
    build_cosy_headers,
    generate_machine_id,
)
from .encoding import qoder_encode_body
from .models import (
    resolve_qoder_models,
    get_qoder_model_config,
    fetch_qoder_catalog,
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
    "exchange_personal_token",
    "import_pat",
    "build_cosy_headers",
    "generate_machine_id",
    "qoder_encode_body",
    "resolve_qoder_models",
    "get_qoder_model_config",
    "fetch_qoder_catalog",
    "QODER_MODEL_MAP",
    "QODER_CHAT_URL_ENCODED",
    "QODER_QUOTA_USAGE_URL",
]
