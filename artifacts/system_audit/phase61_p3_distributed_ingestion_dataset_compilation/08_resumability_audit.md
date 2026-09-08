# 08 RESUMABILITY AUDIT

- Resumable Pipeline: Tasks carry persistent status flags (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED_RETRYABLE`, `QUARANTINED`). Interrupted batches resume from pending tasks without corrupting state.
