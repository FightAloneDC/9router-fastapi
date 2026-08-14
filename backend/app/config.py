"""Application configuration — all values loaded from .env file."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings. Every value MUST be defined in .env.
    Missing keys will cause a validation error on startup.
    """

    # Database
    DATABASE_URL: str

    # Auth / JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # App
    APP_NAME: str
    DEBUG: bool

    # Admin seed password
    ADMIN_PASSWORD: str

    # CORS — comma-separated origins or "*"
    CORS_ORIGINS: str

    # ── OAuth Client IDs ──────────────────────────────────────────────────
    CLAUDE_CLIENT_ID: str
    CODEX_CLIENT_ID: str
    GEMINI_CLIENT_ID: str
    GEMINI_CLIENT_SECRET: str
    QWEN_CLIENT_ID: str
    IFLOW_CLIENT_ID: str
    IFLOW_CLIENT_SECRET: str
    ANTIGRAVITY_CLIENT_ID: str
    ANTIGRAVITY_CLIENT_SECRET: str
    GITHUB_CLIENT_ID: str
    KIMI_CODING_CLIENT_ID: str

    # Paths
    BACKUP_DIR: str = "backups"

    # Grok CLI request/response dumps under .scratch/grok-cli/.
    # Off unless set true in .env (or GROK_CLI_DUMP=1 in the environment).
    GROK_CLI_DUMP: bool = False
    GROK_CLI_DUMP_DIR: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
