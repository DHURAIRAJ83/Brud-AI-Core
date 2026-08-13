#!/usr/bin/env bash
set -euo pipefail

check() {
  local name="$1"
  local url="$2"
  echo "=== $name ==="
  curl -fsS "$url" | head -c 200
  echo
}

check public_health http://127.0.0.1:8000/api/health
check admin_health  http://127.0.0.1:8001/api/health
check worker_health http://127.0.0.1:8002/api/health
