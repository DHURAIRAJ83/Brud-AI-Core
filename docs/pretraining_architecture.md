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
