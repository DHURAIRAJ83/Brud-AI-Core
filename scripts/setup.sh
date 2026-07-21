#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

command -v python3 >/dev/null || { echo "Error: Python 3 is required." >&2; exit 1; }
command -v node >/dev/null || { echo "Error: Node.js is required." >&2; exit 1; }
command -v npm >/dev/null || { echo "Error: npm is required." >&2; exit 1; }

python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' || {
  echo "Error: Python 3.11 or newer is required." >&2
  exit 1
}

if [[ ! -d venv ]]; then
  python3 -m venv venv
fi

venv/bin/python -m pip install --upgrade pip
venv/bin/python -m pip install -r requirements.txt
npm install --prefix apps/chatbot
npm install --prefix apps/admin-dashboard

if [[ ! -f .env ]]; then
  cp .env.example .env
fi

venv/bin/python -c 'from backend.core.config import get_settings; from backend.database.migrations import initialize_database; initialize_database(get_settings().resolved_database_path)'
echo "Brud AI Phase 1 setup complete."
