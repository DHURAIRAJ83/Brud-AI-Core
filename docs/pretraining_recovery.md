# Pretraining Recovery

Phase 9 recovery is checkpoint based.

- Pause requests are handled between optimizer steps.
- A pause checkpoint is saved before the job becomes `paused`.
- Resume requeues the same job and restores the latest registered checkpoint.
- Cancel requests stop at a safe boundary and preserve checkpoint evidence where available.
- Failed jobs keep safe error codes/messages and are not presented as completed.

Retention must never delete latest, pause, best-validation, or final checkpoints accidentally. Automated cleanup is deferred.

## Phase 10 update

Resume is no longer a plain status flip. `PretrainingService.resume()` now
calls `WorkerRecoveryService.recover(job, admin_id, "pause_resume")`, which
validates the job's latest checkpoint (checksums, tensor shapes, RNG,
monotonic step/token counters) before setting the job back to `queued`. If
validation fails, the checkpoint is marked `corrupt` and resume is refused —
this is a genuine behavior change from the Phase 9 description above, and it
applies uniformly to every recovery path (pause/resume, stale-lease takeover,
worker crash, and manual/CLI-triggered recovery). Retention is no longer
deferred: see [checkpoint_retention.md](checkpoint_retention.md) for the
implemented preview/apply workflow and configurable keep-counts. Full detail
on validation and recovery types is in
[training_crash_recovery.md](training_crash_recovery.md).
