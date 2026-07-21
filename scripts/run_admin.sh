#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT/apps/admin-dashboard"
[[ -d node_modules ]] || { echo "Error: run scripts/setup.sh first." >&2; exit 1; }
exec npm run dev
