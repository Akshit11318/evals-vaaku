#!/usr/bin/env bash
# Start the bench on localhost. Reach a remote box with scripts/tunnel.sh.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
export TOKENIZERS_PARALLELISM="${TOKENIZERS_PARALLELISM:-false}"
export HF_HUB_DISABLE_TELEMETRY=1
HOST="${DASHBOARD_HOST:-127.0.0.1}"
PORT="${DASHBOARD_PORT:-8787}"
exec .venv/bin/python -m uvicorn app.server:app --host "$HOST" --port "$PORT"
