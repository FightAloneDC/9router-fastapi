"""Keelcode provider constants."""

CLIENT_ID: str = "keelcode-cli"
AUTH_BASE_URL: str = "https://keelcode.ai"
API_BASE_URL: str = "https://api.keelcode.ai"
DEVICE_CODE_URL: str = (
    f"{AUTH_BASE_URL}/api/auth/device/code"
)
DEVICE_TOKEN_URL: str = (
    f"{AUTH_BASE_URL}/api/auth/device/token"
)
DEVICE_GRANT_TYPE: str = (
    "urn:ietf:params:oauth:grant-type:device_code"
)
DEFAULT_POLL_INTERVAL: int = 5
