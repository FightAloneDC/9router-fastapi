# ── Base ──
FROM python:3.12-slim AS base

WORKDIR /app

# Install system deps: uv + espeak-ng (for local-device TTS)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends espeak-ng && \
    ln -sf /usr/bin/espeak-ng /usr/bin/espeak && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency files first (cache layer)
COPY pyproject.toml uv.lock README.md ./

# ── Dev ── (source mounted as volume, hot-reload)
FROM base AS dev

ARG UID=1000
ARG GID=1000

RUN groupadd -g ${GID} devuser && \
    useradd -m -u ${UID} -g ${GID} devuser && \
    chown -R devuser:devuser /app

USER devuser

# Install all deps including dev (runs as devuser so .venv is owned by devuser)
RUN uv sync --frozen

# Source is mounted as volume — no COPY needed
# Sync deps if .venv doesn't exist (first run or after host .venv deletion)
CMD ["sh", "-c", "[ -d .venv ] || uv sync --frozen && uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload"]

# ── Production ──
FROM base AS prod

# Install prod deps only
RUN uv sync --frozen --no-dev

# Copy application code
COPY . .

# Run migrations then start server
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 9000"]
