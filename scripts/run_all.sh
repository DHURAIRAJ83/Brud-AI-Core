#!/usr/bin/env bash
set -euo pipefail
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

pids=()
cleanup() {
  local exit_code=$?
  trap - EXIT INT TERM
  if ((${#pids[@]})); then
    kill "${pids[@]}" 2>/dev/null || true
    wait "${pids[@]}" 2>/dev/null || true
  fi
  exit "$exit_code"
}
trap cleanup EXIT INT TERM

scripts/run_backend.sh & pids+=("$!")
scripts/run_chatbot.sh & pids+=("$!")
scripts/run_admin.sh & pids+=("$!")

echo "Backend: http://127.0.0.1:8000"
echo "Chatbot: http://localhost:5173"
echo "Admin:   http://localhost:5174"
wait -n "${pids[@]}"
