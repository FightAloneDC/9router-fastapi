#!/usr/bin/env bash
# After commits on `dev`: push origin/dev, fast-forward main, return to
# dev. Does not rewrite history. Push of `main` is opt-in.
#
# Usage:
#   ./scripts/promote-to-main.sh              # push dev + merge into main
#   ./scripts/promote-to-main.sh --push-main  # also push origin/main
#
# Must start on a clean `dev` branch.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

git_repo() {
  git -c "safe.directory=$ROOT" -C "$ROOT" "$@"
}

PUSH_MAIN=0
for arg in "$@"; do
  case "$arg" in
    --push-main) PUSH_MAIN=1 ;;
    -h|--help)
      cat <<'EOF'
After commits on `dev`: push origin/dev, fast-forward main,
return to `dev`. Push of `main` is opt-in.

Usage:
  ./scripts/promote-to-main.sh              # push dev + merge into main
  ./scripts/promote-to-main.sh --push-main  # also push origin/main

Must start on a clean `dev` branch.
EOF
      exit 0
      ;;
    *)
      echo "error: unknown arg: $arg (try --help)" >&2
      exit 1
      ;;
  esac
done

BRANCH="$(git_repo rev-parse --abbrev-ref HEAD)"
if [[ "$BRANCH" != "dev" ]]; then
  echo "error: must run on dev (on $BRANCH)" >&2
  exit 1
fi

if [[ -n "$(git_repo status --porcelain)" ]]; then
  echo "error: working tree not clean — commit or stash first" >&2
  exit 1
fi

echo "==> push origin/dev"
git_repo push origin dev

echo "==> checkout main"
git_repo checkout main

echo "==> merge --ff-only dev"
git_repo merge --ff-only dev

if [[ "$PUSH_MAIN" -eq 1 ]]; then
  echo "==> push origin/main"
  git_repo push origin main
else
  echo "==> skip origin/main (pass --push-main to push)"
fi

echo "==> checkout dev"
git_repo checkout dev

echo "Done. HEAD=$(git_repo rev-parse --short HEAD)"
