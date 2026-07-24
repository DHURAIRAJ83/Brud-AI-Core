# Internal Canary (Phase 15)

Controlled internal comparison against a small, **explicit** fixture
set — never real user traffic, and never a path to public activation.

## Lifecycle (append-only, "latest row wins")

`inference_canary_runs` is append-only, so a canary's lifecycle is a
sequence of rows, not in-place mutation:

1. `POST /canary/start` inserts one row (`run_status="running"`,
   `percentage`, `max_request_count`). All `inference_canary_results`
   for this canary attach to **this** row's internal ID for the entire
   "running" phase.
2. `POST /canary/execute` (repeatable) routes each fixture prompt via
   `stable_routing_key()` — a deterministic SHA-256-derived bucket, so
   the same routing key always routes the same way — computes live
   metrics from all results recorded so far under the running row, and
   only **appends a new terminal row** (`completed`/`paused`) once the
   configured `max_request_count` is reached or an auto-stop condition
   fires. This was a genuine append-only-vs-`UPDATE` bug caught during
   automated testing (see `docs/phase_15_report.md`) — the original
   implementation tried to `UPDATE` the running row's
   `requests_executed`/`metrics_json` in place, which the schema's
   `BEFORE UPDATE` trigger correctly rejected.
3. `POST /canary/stop` (manual) likewise appends a terminal row rather
   than mutating the running one.

## Metrics (`compute_canary_metrics()`)

Total/model/fallback request counts, success/failure/timeout counts,
average latency (P95 only reported once ≥ 30 samples —
`sample_size_small: true` otherwise, never a fabricated percentile from
too few points), input/output token totals, role-leakage/prompt-
leakage/repetition-warning/unicode-valid rates, and the stop-reason
distribution.

## Auto-stop rules (`assess_canary_stop()`)

Checkpoint mismatch, runtime unhealthy, memory-guard failure, role-
leakage rate above threshold, prompt-leakage rate above threshold,
failure/timeout rate above threshold, an inherited unsafe-output issue
from evaluation evidence, or an explicit admin stop. Thresholds are
configurable via `BRUD_INFERENCE_CANARY_*` settings; defaults are
conservative (0% role/prompt leakage tolerance).

## No public activation, ever, from a canary alone

A successful canary is one **input** to the public-chat activation
gate, never sufficient by itself — see
`docs/inference_runtime_architecture.md`'s activation-gate section.
