#!/usr/bin/env bash
# Run backend (uvicorn --reload) + frontend (Vite) on the host in one terminal.
# Does not start or stop Docker. Production on :8013 stays untouched.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"

BACKEND_PORT="${BACKEND_PORT:-9000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"

port_busy() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn "sport = :$port" 2>/dev/null | grep -q ":$port"
    return
  fi
  if command -v nc >/dev/null 2>&1; then
    nc -z 127.0.0.1 "$port" >/dev/null 2>&1
    return
  fi
  return 1
}

cleanup() {
  trap - EXIT INT TERM
  local pids
  pids="$(jobs -p 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    kill "$pids" 2>/dev/null || true
    wait "$pids" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

if port_busy "$BACKEND_PORT"; then
  echo "error: port $BACKEND_PORT already in use" >&2
  echo "hint: stop the other process or set BACKEND_PORT" >&2
  exit 1
fi

if port_busy "$FRONTEND_PORT"; then
  echo "error: port $FRONTEND_PORT already in use" >&2
  echo "hint: stop the other process or set FRONTEND_PORT" >&2
  exit 1
fi

cd "$BACKEND"
if [[ ! -d .venv ]]; then
  echo "[dev] syncing backend deps..."
  uv sync --frozen
fi
echo "[dev] running alembic upgrade head..."
uv run alembic upgrade head

cd "$FRONTEND"
if [[ ! -d node_modules ]]; then
  echo "[dev] installing frontend deps..."
  npm ci
fi

echo "[dev] backend  http://localhost:${BACKEND_PORT}"
echo "[dev] frontend http://localhost:${FRONTEND_PORT}"
echo "[dev] prod stays on http://localhost:8013 (unchanged)"
echo "[dev] Ctrl+C stops both processes"

(
  cd "$BACKEND"
  exec uv run uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "$BACKEND_PORT" \
    --reload \
    --timeout-graceful-shutdown 3
) 2>&1 | sed -u 's/^/[backend] /' &

(
  cd "$FRONTEND"
  exec npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"
) 2>&1 | sed -u 's/^/[frontend] /' &

wait
