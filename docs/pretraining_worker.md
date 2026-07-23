# Pretraining Worker

Run:

```bash
python -m backend.training_worker
```

For a one-shot verification:

```bash
python -m backend.training_worker --once
```

Additional flags: `--poll-seconds <n>` overrides
`BRUD_PRETRAINING_WORKER_POLL_SECONDS`; `--worker-name <name>` sets a stable
worker identity (defaults to a random `worker-<hex>`).

The worker:

- registers/renews a `worker_heartbeats` row every poll and on every metric callback;
- claims one queued job transactionally, receiving a fencing `lease_generation`;
- records `worker_claimed`;
- runs CPU training in-process, generating dataset coverage and a stream manifest before the first step;
- records step metrics and renews its lease at the same cadence, verifying its fencing token still matches on every write;
- saves periodic checkpoints every `checkpoint_interval_steps`, in addition to the final pause/complete/cancel checkpoint;
- checks pause/cancel requests between optimizer steps;
- marks failures with safe error messages, and releases its lease on any terminal outcome;
- on graceful shutdown (SIGINT/SIGTERM after the current `run_one()` call returns), marks its heartbeat `stopped`.

If no job is queued, `--once` returns `{'status': 'idle'}`. If the worker's
lease is taken over mid-run by another worker (stale-lease detection), the
current call returns `{'status': 'stale', ...}` without writing further
metrics or checkpoints — see
[training_worker_leases.md](training_worker_leases.md). An ungraceful crash
(no chance to run the `finally` block) leaves the heartbeat and lease rows
stale on purpose; `python -m backend.training_recovery_cli stale-jobs` and
`GET /api/admin/pretraining/recovery/stale-jobs` surface exactly that
evidence, and recovery is performed via
`python -m backend.training_recovery_cli recover <job_public_id>` or
`POST /api/admin/pretraining/jobs/{public_id}/recover` — see
[training_crash_recovery.md](training_crash_recovery.md).
