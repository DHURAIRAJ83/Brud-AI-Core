# Pretraining Recovery

Phase 9 recovery is checkpoint based.

- Pause requests are handled between optimizer steps.
- A pause checkpoint is saved before the job becomes `paused`.
- Resume requeues the same job and restores the latest registered checkpoint.
- Cancel requests stop at a safe boundary and preserve checkpoint evidence where available.
- Failed jobs keep safe error codes/messages and are not presented as completed.

Retention must never delete latest, pause, best-validation, or final checkpoints accidentally. Automated cleanup is deferred.
