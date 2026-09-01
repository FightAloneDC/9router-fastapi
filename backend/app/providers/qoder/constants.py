"""Qoder API constants ported from Node.js implementation.

⚠️  CRITICAL: Do NOT modify this provider without user approval.
    Extensive investigation and trial-error has been done.
    See docs/archives/qoder-docs/BUG-FIXING-LOG.md before making any changes.
"""

# Base URLs
QODER_OPENAPI_BASE = "https://openapi.qoder.sh"
QODER_CENTER_BASE = "https://center.qoder.sh"
QODER_CHAT_BASE = "https://api3.qoder.sh"

# Login URL for device flow
QODER_LOGIN_URL = "https://qoder.com/device/selectAccounts"

# Device flow endpoints
QODER_DEVICE_TOKEN_URL = f"{QODER_OPENAPI_BASE}/api/v1/deviceToken/poll"
QODER_USERINFO_URL = f"{QODER_OPENAPI_BASE}/api/v1/userinfo"
QODER_QUOTA_USAGE_URL = f"{QODER_OPENAPI_BASE}/api/v2/quota/usage"
QODER_REFRESH_TOKEN_URL = f"{QODER_OPENAPI_BASE}/api/v1/jobToken/refresh"

# Inference endpoints (under /algo on api3.qoder.sh, all COSY-signed)
QODER_CHAT_SIG_PATH = "/api/v2/service/pro/sse/agent_chat_generation"
QODER_CHAT_URL = f"{QODER_CHAT_BASE}/algo{QODER_CHAT_SIG_PATH}?FetchKeys=llm_model_result&AgentId=agent_common"
QODER_CHAT_URL_ENCODED = f"{QODER_CHAT_URL}&Encode=1"
QODER_MODEL_LIST_URL = f"{QODER_CHAT_BASE}/algo/api/v2/model/list"

# COSY header constants.
# Catalog gates models by Cosy-Version (cmodel/Cantus needs
# cli >= 1.0.48). Chat with that key was verified 2026-09-01.
QODER_IDE_VERSION = "1.0.48"
QODER_CLIENT_TYPE = "5"
QODER_DATA_POLICY = "agree"
QODER_LOGIN_VERSION = "v2"
QODER_MACHINE_OS = "x86_64_windows"
QODER_MACHINE_TYPE = "5"

# Canonical model identifiers
QODER_MODEL_MAP = {
    # Tier models
    "auto": "auto",
    "ultimate": "ultimate",
    "performance": "performance",
    "efficient": "efficient",
    "lite": "lite",
    # Frontier models
    "qmodel": "qmodel",
    "dmodel": "dmodel",
    "dfmodel": "dfmodel",
    "gm51model": "gm51model",
    "kmodel": "kmodel",
    "mmodel": "mmodel",
}

# RSA public key for COSY encryption (extracted from Qoder IDE v0.9)
QODER_RSA_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDA8iMH5c02LilrsERw9t6Pv5Nc
4k6Pz1EaDicBMpdpxKduSZu5OANqUq8er4GM95omAGIOPOh+Nx0spthYA2BqGz+l
6HRkPJ7S236FZz73In/KVuLnwI8JJ2CbuJap8kvheCCZpmAWpb/cPx/3Vr/J6I17
XcW+ML9FoCI6AOvOzwIDAQAB
-----END PUBLIC KEY-----"""

# Custom alphabet for WAF-bypass encoding
QODER_STD_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
QODER_CUSTOM_ALPHABET = "_doRTgHZBKcGVjlvpC,@aFSx#DPuNJme&i*MzLOEn)sUrthbf%Y^w.(kIQyXqWA!"
