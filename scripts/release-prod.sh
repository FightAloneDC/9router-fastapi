#!/usr/bin/env bash
# Build Vite UI into backend/app/static and commit on main.
# Does not create tags. Does not touch remotes.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"
STATIC="$ROOT/backend/app/static"

# Per-invocation only (no gitconfig write). Helps mounted/worktree paths.
git_repo() {
  git -c "safe.directory=$ROOT" -C "$ROOT" "$@"
}

BRANCH="$(git_repo rev-parse --abbrev-ref HEAD)"

if [[ "$BRANCH" != "main" ]]; then
  echo "error: checkout main before release (on $BRANCH)" >&2
  exit 1
fi

if [[ -n "$(git_repo status --porcelain)" ]]; then
  echo "error: working tree not clean" >&2
  exit 1
fi

cd "$FRONTEND"
if [[ ! -d node_modules ]]; then
  npm ci
fi
npm run build

STAGE="$ROOT/.scratch/release-static"
rm -rf "$STAGE"
mkdir -p "$STAGE"
trap 'rm -rf "$STAGE"' EXIT
cp -r "$FRONTEND/dist/." "$STAGE/"
if [[ -f "$STATIC/README.md" && ! -f "$STAGE/README.md" ]]; then
  cp "$STATIC/README.md" "$STAGE/README.md"
fi

# Atomic swap
NEXT="$ROOT/backend/app/static.next"
rm -rf "$NEXT"
mv "$STAGE" "$NEXT"
trap - EXIT
rm -rf "$STATIC"
mv "$NEXT" "$STATIC"

git_repo add backend/app/static
if git_repo diff --cached --quiet; then
  echo "No UI changes"
  exit 0
fi

git_repo commit -m "chore: refresh production UI static"
echo "Committed production UI static on main."
