"""Grok CLI (Grok Build) constants.

Wire-captured from the official @xai-official/grok CLI 0.2.99 talking to
cli-chat-proxy.grok.com (OpenAI Responses API).

Distinct from:
- xai      -> api.x.ai (API key / xAI API OAuth PKCE)
- grok-web -> grok.com web SSO cookie
"""

# ── Client fingerprint ───────────────────────────────────────────────────
GROK_CLI_VERSION = "0.2.99"
# API model id (xAI pricing). Not "grok-build" — that is only
# the OAuth referrer / CLI product name, not a model.
GROK_CLI_MODEL = "grok-4.6"
# CLI product / OAuth referrer — not an API model id (xAI pricing).
GROK_CLI_DROP_MODEL_IDS = frozenset({"grok-build"})
GROK_CLI_BASE_URL = "https://cli-chat-proxy.grok.com/v1"
GROK_CLI_CLIENT_IDENTIFIER = "grok-shell"
GROK_CLI_USER_AGENT = (
    f"grok-shell/{GROK_CLI_VERSION} (linux; x86_64)"
)
# Fingerprint used on auth.x.ai OAuth endpoints (official CLI value)
GROK_CLI_OAUTH_USER_AGENT = (
    "grok-pager/0.2.93 grok-shell/0.2.93 (linux; x86_64)"
)
GROK_CLI_TOKEN_AUTH = "xai-grok-cli"

# ── Usage / billing endpoints (quota tracker) ────────────────────────────
GROK_CLI_BILLING_URL = (
    f"{GROK_CLI_BASE_URL}/billing?format=credits"
)
GROK_CLI_USER_URL = (
    f"{GROK_CLI_BASE_URL}/user?include=subscription"
)

# ── OAuth device code (public client, auth.x.ai) ─────────────────────────
GROK_CLI_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"
GROK_CLI_DEVICE_CODE_URL = "https://auth.x.ai/oauth2/device/code"
GROK_CLI_TOKEN_URL = "https://auth.x.ai/oauth2/token"
GROK_CLI_SCOPE = (
    "openid profile email offline_access grok-cli:access api:access "
    "conversations:read conversations:write"
)
GROK_CLI_REFERRER = "grok-build"
GROK_CLI_REFRESH_LEAD_SECONDS = 5 * 60

# ── Reasoning effort ─────────────────────────────────────────────────────
GROK_CLI_EFFORT_LEVELS = ("low", "medium", "high", "xhigh")
GROK_CLI_DEFAULT_EFFORT = "high"

# Off while isolating the literal-407 quality gate.
PHANTOM_WRITE_RETRY = False
# Off: probe-before-chat caused client timeouts.
QUALITY_GATE_407 = False

# ── Responses API request shaping ────────────────────────────────────────
# Fields accepted by cli-chat-proxy Responses API (Codex allowlist +
# Grok extras). Anything else is stripped from the forwarded body.
RESPONSES_API_ALLOWLIST = frozenset({
    "model",
    "input",
    "instructions",
    "tools",
    "tool_choice",
    "stream",
    "store",
    "reasoning",
    "include",
    "temperature",
    "top_p",
    "max_output_tokens",
    "parallel_tool_calls",
    "text",
    "metadata",
    "prompt_cache_key",
})

# Hosted tool types executed server-side by the Grok CLI backend
HOSTED_TOOL_TYPES = frozenset({
    "web_search",
    "x_search",
    "web_search_preview",
    "file_search",
    "image_generation",
    "code_interpreter",
    "mcp",
    "local_shell",
})

# Server-generated item id prefixes that /responses cannot resolve when
# store=false
SERVER_ID_PATTERN = r"^(rs|fc|resp|msg)_"

# Native grok-cli item ids survive store=false round-trips
GROK_CLI_NATIVE_ITEM_ID = (
    r"^(?:rs|msg|fc)_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}"
    r"-[0-9a-f]{4}-[0-9a-f]{12}$"
)

# Freeform schema used when a client sends type:"custom" tools
GROK_CLI_FREEFORM_TOOL_PARAMETERS: dict = {
    "type": "object",
    "properties": {"input": {"type": "string"}},
    "required": ["input"],
}

# Per-session turn index bookkeeping
GROK_CLI_TURN_STORE_MAX = 5000
GROK_CLI_SESSION_TTL_SECONDS = 30 * 60
