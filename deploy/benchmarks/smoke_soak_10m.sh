#!/usr/bin/env bash
# Phase 5G-A: 10-minute smoke soak test.
#
# Starts a real uvicorn server on a dedicated test port against an
# isolated temp database, polls /api/health and RSS every 30s for 10
# minutes, and reports uptime percentage plus RSS growth trend. This
# is a short smoke-test proxy for the full 1h/6h/24h soak tests, which
# are Phase 5G-B's scope (unattended, documented, not executed here).
#
# Never touches a real running service: refuses to start if the test
# port is already bound, and always cleans up its own process + temp
# directory on exit.
#
# Usage: deploy/benchmarks/smoke_soak_10m.sh [port] [mode]

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

PORT="${1:-18097}"
MODE="${2:-public}"
DURATION_S="${3:-600}"
INTERVAL_S="${4:-30}"
HOST="127.0.0.1"
HEALTH_URL="http://$HOST:$PORT/api/health"
REPORTS_DIR="$ROOT/deploy/benchmarks/reports"
mkdir -p "$REPORTS_DIR"
OUT_JSON="$REPORTS_DIR/smoke_soak_10m.json"

TMP_DIR="$(mktemp -d /tmp/brud-benchmark-soak.XXXXXX)"
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

echo "=== 10-minute smoke soak: mode=$MODE port=$PORT ==="
venv/bin/python -m uvicorn backend.main:app --host "$HOST" --port "$PORT" \
  > "$TMP_DIR/uvicorn.log" 2>&1 &
PID=$!

deadline=$((SECONDS + 20))
ready=false
while [ "$SECONDS" -lt "$deadline" ]; do
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 0.3
done
if [ "$ready" != true ]; then
  echo "server did not become healthy within 20s -- aborting" >&2
  exit 1
fi
echo "server healthy (pid=$PID), starting $((DURATION_S / 60))-minute poll loop every ${INTERVAL_S}s..."

samples_json="["
first=true
healthy_count=0
total_count=0
rss_values=()

end_time=$((SECONDS + DURATION_S))
while [ "$SECONDS" -lt "$end_time" ]; do
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  if curl -fsS "$HEALTH_URL" >/dev/null 2>&1; then
    healthy=true
    healthy_count=$((healthy_count + 1))
  else
    healthy=false
  fi
  total_count=$((total_count + 1))

  rss_kb="$(ps -o rss= -p "$PID" 2>/dev/null | tr -d ' ' || true)"
  if [ -z "$rss_kb" ]; then
    rss_kb=0
  fi
  rss_values+=("$rss_kb")

  echo "  [$ts] healthy=$healthy rss_kb=$rss_kb"

  if [ "$first" = true ]; then
    first=false
  else
    samples_json+=","
  fi
  samples_json+="{\"timestamp\": \"$ts\", \"healthy\": $healthy, \"rss_kb\": $rss_kb}"

  sleep "$INTERVAL_S"
done
samples_json+="]"

rss_first="${rss_values[0]:-0}"
rss_last="${rss_values[-1]:-0}"
rss_max=0
for v in "${rss_values[@]}"; do
  if [ "$v" -gt "$rss_max" ]; then
    rss_max=$v
  fi
done

growth_pct=$(awk "BEGIN { if ($rss_first > 0) printf \"%.1f\", (($rss_last - $rss_first) / $rss_first) * 100; else print 0 }")
uptime_pct=$(awk "BEGIN { if ($total_count > 0) printf \"%.1f\", ($healthy_count / $total_count) * 100; else print 0 }")

# Smoke-test heuristic only -- not a substitute for the full 1h/6h/24h
# soak tests (Phase 5G-B), which have far more room to detect a slow leak.
if [ "$healthy_count" -eq "$total_count" ] && awk "BEGIN { exit !($growth_pct < 50) }"; then
  overall="PASS"
else
  overall="FAIL"
fi

cat > "$OUT_JSON" <<JSON
{
  "mode": "$MODE",
  "port": $PORT,
  "duration_s": $DURATION_S,
  "interval_s": $INTERVAL_S,
  "samples": $samples_json,
  "healthy_count": $healthy_count,
  "total_count": $total_count,
  "uptime_pct": $uptime_pct,
  "rss_first_kb": $rss_first,
  "rss_last_kb": $rss_last,
  "rss_max_kb": $rss_max,
  "rss_growth_pct": $growth_pct,
  "overall": "$overall"
}
JSON

echo ""
echo "uptime: $uptime_pct% ($healthy_count/$total_count checks healthy)"
echo "RSS: first=${rss_first}KB last=${rss_last}KB max=${rss_max}KB growth=${growth_pct}%"
echo "Result: $overall"
echo "Wrote $OUT_JSON"

[ "$overall" = "PASS" ]
