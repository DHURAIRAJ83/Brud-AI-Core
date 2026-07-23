# Training Worker Leases

## Overview

`worker_heartbeats` tracks registered worker processes; `training_worker_leases`
(a Phase 9 table, extended in Phase 10) tracks which job a worker currently
owns and its fencing generation. Both are managed entirely by
`backend/database/repositories/training_reliability.py` and
`backend/services/pretraining_service.py` — there is no separate heartbeat
network protocol; a worker is just a process calling
`PretrainingService.run_one()` in a loop (`backend/training_worker.py`).

## Worker heartbeat statuses

```text
starting  → registered, not yet polling
idle      → polling, no job claimed
claiming  → about to attempt a claim
running   → actively training a claimed job
failed    → the last run_one() call raised and the worker released its lease
stopped   → the worker exited (graceful shutdown, or --once with no work)
```

`pausing`, `recovering`, and `stopping` are reserved in the schema's `CHECK`
constraint for future finer-grained reporting but are not currently emitted —
this module reports honestly, not speculatively.

## Lease generation and fencing

`pretraining_jobs.lease_generation` is the fencing token, not a separate
lease table lookup:

1. `PretrainingService._claim()` claims a `queued` job (with
   `recovery_required=0`) inside one SQLite transaction: it increments
   `lease_generation`, sets `worker_id`, and sets `lease_expires_at` to
   `now + BRUD_PRETRAINING_WORKER_LEASE_SECONDS`. The same transaction upserts
   `training_worker_leases` and `worker_heartbeats` for that worker.
2. Every metric callback (`PretrainingService._metric`, roughly every
   `metric_interval_steps`) and every periodic checkpoint
   (`_save_periodic_checkpoint`, every `checkpoint_interval_steps`) re-checks
   that `pretraining_jobs.worker_id` and `lease_generation` still match what
   the worker was granted, and renews `lease_expires_at`. If they don't match,
   the call raises `StaleWorkerError` immediately — no further writes happen.
3. On completion, pause, cancel, or failure, the lease is released
   (`training_worker_leases.released_at` set, `worker_heartbeats` set to
   `idle`/`failed`).

## Stale-lease detection

Every call to `_claim()` first sweeps for `running` jobs whose
`lease_expires_at` has passed: it flips them to `status='queued',
recovery_required=1` and bumps `lease_generation` again (invalidating the
crashed worker's fencing token immediately), and records a
`stale_lease_detected` job event. A swept job cannot be claimed normally again
— it must go through `WorkerRecoveryService.recover()` first, which validates
its latest checkpoint and clears `recovery_required`.

## No PID or hostname exposure

`worker_heartbeats` has no PID or hostname column. Workers are identified only
by a server-issued `public_id` and a caller-supplied `worker_id` (name), and
the admin API/UI only ever shows `worker_id`/`public_id`, current job public
ID, lease generation, and heartbeat/expiry timestamps.

## Ungraceful termination

If a worker process is killed (`SIGKILL`, crash, power loss), nothing updates
its heartbeat or lease further — the row simply goes stale. This is
intentional: a frozen `last_heartbeat_at` and an expired `lease_expires_at`
are exactly the evidence `_claim()`'s stale sweep and
`GET /api/admin/pretraining/recovery/stale-jobs` need to detect it.
