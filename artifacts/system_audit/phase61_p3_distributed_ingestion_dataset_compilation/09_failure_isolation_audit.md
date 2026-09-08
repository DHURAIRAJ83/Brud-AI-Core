# 09 FAILURE ISOLATION AUDIT

- Failure Handling: Isolated book failures (e.g. unknown rights or corrupt download) flag the task as `QUARANTINED`.
- Batch Outcome: Batch completes with status `COMPLETED_WITH_EXCEPTIONS` while valid books continue to compilation.
