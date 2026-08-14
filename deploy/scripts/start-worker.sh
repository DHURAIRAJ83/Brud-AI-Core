#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

source venv/bin/activate
export BRUD_DEPLOYMENT_MODE=worker

HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8002}"

UVICORN_ARGS=(backend.main:app --host "$HOST" --port "$PORT")
if [ "${BRUD_TRUST_PROXY_HEADERS:-false}" = "true" ]; then
  UVICORN_ARGS+=(--proxy-headers --forwarded-allow-ips "${BRUD_TRUSTED_PROXY_IPS:-127.0.0.1}")
fi

exec uvicorn "${UVICORN_ARGS[@]}"
