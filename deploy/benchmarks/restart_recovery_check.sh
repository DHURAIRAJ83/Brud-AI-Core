#!/usr/bin/env bash
# Phase 5G-A: restart-recovery smoke check.
#
# Starts a real uvicorn server on a dedicated test port against an
# isolated temp database, verifies it's healthy, SIGKILLs it to
# simulate a crash, restarts it the same way, and verifies it comes
# back healthy. This tests the restart *mechanism* only -- it does not
# test systemd's own auto-restart persistence over time, which is
# Phase 5G-B's scope (unattended, documented separately).
#
# Never touches a real running service: refuses to start if the test
# port is already bound, and always cleans up its own process + temp
# directory on exit.
#
# Usage: deploy/benchmarks/restart_recovery_check.sh [port] [mode]

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PORT="${1:-18098}"
MODE="${2:-public}"
HOST="127.0.0.1"
HEALTH_URL="http://$HOST:$PORT/api/health"
REPORTS_DIR="$ROOT/deploy/benchmarks/reports"
mkdir -p "$REPORTS_DIR"
OUT_JSON="$REPORTS_DIR/restart_recovery_check.json"

TMP_DIR="$(mktemp -d /tmp/brud-benchmark-restart.XXXXXX)"
PID=""

cleanup() {
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID" 2>/dev/null || true
    wait "$PID" 2>/dev/null || true
  fi
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

if lsof -i ":$PORT" >/dev/null 2>&1; then
  echo "port $PORT is already in use -- refusing to start (would risk a real running service)" >&2
  exit 1
fi

export BRUD_DEPLOYMENT_MODE="$MODE"
export BRUD_DATABASE_PATH="$TMP_DIR/benchmark.db"
export BRUD_DATABASE_BACKUP_DIR="$TMP_DIR/backups"
export BRUD_ALLOW_EXTERNAL_STORAGE="true"

start_server() {
  venv/bin/python -m uvicorn backend.main:app --host "$HOST" --port "$PORT" \
    > "$TMP_DIR/uvicorn.log" 2>&1 &
  PID=$!
}

wait_healthy() {
  local deadline=$((SECONDS + 20))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.3
  done
  return 1
}

echo "=== restart-recovery check: mode=$MODE port=$PORT ==="

echo "1) starting server..."
start_server
if wait_healthy; then
  echo "   initial startup: HEALTHY (pid=$PID)"
  initial_ok=true
else
  echo "   initial startup: FAILED to become healthy" >&2
  initial_ok=false
fi

echo "2) simulating a crash (SIGKILL)..."
kill -9 "$PID" 2>/dev/null || true
wait "$PID" 2>/dev/null || true
sleep 1
if lsof -i ":$PORT" >/dev/null 2>&1; then
  echo "   WARNING: port $PORT still bound after kill -9" >&2
  port_freed=false
else
  echo "   port freed after crash"
  port_freed=true
fi

echo "3) restarting server..."
start_server
if wait_healthy; then
  echo "   post-restart: HEALTHY (pid=$PID)"
  recovery_ok=true
else
  echo "   post-restart: FAILED to become healthy" >&2
  recovery_ok=false
fi

if [ "$initial_ok" = true ] && [ "$port_freed" = true ] && [ "$recovery_ok" = true ]; then
  overall="PASS"
else
  overall="FAIL"
fi

cat > "$OUT_JSON" <<JSON
{
  "mode": "$MODE",
  "port": $PORT,
  "initial_startup_healthy": $initial_ok,
  "port_freed_after_crash": $port_freed,
  "recovery_healthy": $recovery_ok,
  "overall": "$overall"
}
JSON

echo ""
echo "Result: $overall"
echo "Wrote $OUT_JSON"

[ "$overall" = "PASS" ]
