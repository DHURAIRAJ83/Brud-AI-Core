#!/usr/bin/env bash
# Phase 5G-A: RSS memory snapshot per deployment mode.
#
# For each mode, builds the FastAPI `app` object in a background
# process (import only -- never binds a port, never runs the ASGI
# lifespan, so no database is touched) and reads its RSS via `ps`.
# Each process is explicitly killed before moving to the next mode.
#
# Usage: deploy/benchmarks/rss_snapshot.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

REPORTS_DIR="$ROOT/deploy/benchmarks/reports"
mkdir -p "$REPORTS_DIR"
OUT_JSON="$REPORTS_DIR/rss_snapshot.json"

MODES=(dev admin public worker)
echo "{" > "$OUT_JSON"
first=true

printf "%-10s %10s\n" "Mode" "RSS (MB)"

for mode in "${MODES[@]}"; do
  if [ "$mode" = "dev" ]; then
    unset BRUD_DEPLOYMENT_MODE || true
  else
    export BRUD_DEPLOYMENT_MODE="$mode"
  fi

  # The child sleeps far longer (60s) than any plausible import time, so
  # there is no race between "app finished importing" and "child process
  # exits" -- an earlier revision used a fixed-duration poll loop that
  # only checked whether the process was still *alive* (kill -0), not
  # whether it had actually finished importing, and lost the race for
  # fast-starting modes. This version polls the child's own stdout for
  # its "ready" marker, so the RSS snapshot is taken deterministically
  # after import completes, regardless of how long that takes.
  READY_FILE="$(mktemp)"
  venv/bin/python -u -c "
import time
from backend.main import app
print('ready')
time.sleep(60)
" > "$READY_FILE" 2>/dev/null &
  PID=$!

  ready=false
  for _ in $(seq 1 200); do
    if ! kill -0 "$PID" 2>/dev/null; then
      echo "process for mode=$mode exited early" >&2
      break
    fi
    if grep -q "ready" "$READY_FILE" 2>/dev/null; then
      ready=true
      break
    fi
    sleep 0.1
  done
  if [ "$ready" != true ]; then
    echo "WARNING: mode=$mode did not report ready within timeout; RSS snapshot may be mid-import" >&2
  fi
  rm -f "$READY_FILE"

  RSS_KB="$(ps -o rss= -p "$PID" 2>/dev/null | tr -d ' ' || true)"
  if [ -z "$RSS_KB" ]; then
    RSS_KB=0
  fi
  RSS_MB=$(awk "BEGIN { printf \"%.1f\", $RSS_KB/1024 }")

  kill -9 "$PID" 2>/dev/null || true
  wait "$PID" 2>/dev/null || true

  printf "%-10s %10s\n" "$mode" "$RSS_MB"

  if [ "$first" = true ]; then
    first=false
  else
    echo "," >> "$OUT_JSON"
  fi
  printf '  "%s": {"rss_kb": %s, "rss_mb": %s}' "$mode" "$RSS_KB" "$RSS_MB" >> "$OUT_JSON"
done

unset BRUD_DEPLOYMENT_MODE || true
echo "" >> "$OUT_JSON"
echo "}" >> "$OUT_JSON"

echo ""
echo "Wrote $OUT_JSON"
