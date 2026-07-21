#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"
PYTHON_BIN="${PROJECT_ROOT}/venv/bin/python"
[[ -x "$PYTHON_BIN" ]] || { echo "Error: run scripts/setup.sh first." >&2; exit 1; }
exec "$PYTHON_BIN" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
