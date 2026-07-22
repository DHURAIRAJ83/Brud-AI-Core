# Pretraining Worker

Run:

```bash
python -m backend.training_worker
```

For a one-shot verification:

```bash
python -m backend.training_worker --once
```

The worker:

- claims one queued job transactionally;
- records `worker_claimed`;
- runs CPU training in-process;
- records step metrics;
- checks pause/cancel requests between optimizer steps;
- saves pause/final checkpoints;
- marks failures with safe error messages.

If no job is queued, `--once` returns `{'status': 'idle'}`. Unknown crashes are represented by stale lease/job state and can be recovered by future maintenance logic.
