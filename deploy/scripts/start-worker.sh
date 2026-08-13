#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

source venv/bin/activate
export BRUD_DEPLOYMENT_MODE=worker

exec uvicorn backend.main:app \
  --host 0.0.0.0 \
  --port 8002
