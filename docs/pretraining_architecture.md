# Pretraining Architecture

Phase 9 introduces bounded base pretraining for Brud Core.

```text
Admin Dashboard → Pretraining API → Pretraining Service
      → Dataset token stream → Trainer → Checkpoint manager
      → Validation evaluator → SQLite registry
```

The API creates and queues jobs. Actual training is performed by the separate local worker command:

```bash
python -m backend.training_worker
```

This is not distributed or asynchronous FastAPI execution. The worker claims one queued job at a time, updates metrics, writes checkpoints, and exits on SIGINT/SIGTERM after a safe boundary when possible.

The public chatbot remains disconnected.

## Phase 10: reliability layer

Phase 10 wraps the same worker and `PretrainingService` with heartbeat/lease
fencing, dataset coverage and stream-manifest generation, verified recovery,
run summaries, quality gates, and comparisons — no second training loop was
introduced. See [training_worker_leases.md](training_worker_leases.md) for
lease fencing, [training_crash_recovery.md](training_crash_recovery.md) for
recovery validation, [training_dataset_coverage.md](training_dataset_coverage.md)
and [training_stream_manifest.md](training_stream_manifest.md) for the stream
layer, [training_quality_gates.md](training_quality_gates.md) for promotion
gating, and [checkpoint_retention.md](checkpoint_retention.md) for checkpoint
retention. New services: `backend/services/pretraining_reliability_service.py`
(worker views), `backend/services/worker_recovery_service.py` (recovery),
`backend/services/training_evaluation_service.py` (coverage, streams,
summary, quality, comparisons, retention) — routed from
`backend/api/routes/training_reliability.py`.
