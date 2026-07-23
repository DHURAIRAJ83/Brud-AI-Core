# Training Crash Recovery

## Overview

`training_recovery_attempts` (append-only) records every attempt to bring a
pretraining job back into a runnable state, implemented by
`backend/services/worker_recovery_service.py:WorkerRecoveryService`. A job is
never resumed without first validating its latest checkpoint; if validation
fails, the checkpoint is marked `corrupt` and the failure is recorded — there
is no automatic fallback to an earlier checkpoint.

## Recovery types

| Type | Trigger |
|---|---|
| `pause_resume` | Admin calls `POST /jobs/{id}/resume` on a `paused` job. |
| `stale_lease` | `_claim()`'s sweep detected an expired lease and flagged the job; recovery is required before it can be claimed again. |
| `worker_crash` | Same mechanism as `stale_lease` — a crash is only distinguishable from a slow worker by the same expired-lease signal. |
| `manual_resume` | Admin explicitly calls `POST /jobs/{id}/recover` on a `failed`/`paused`/`queued` job that isn't lease-flagged. |
| `checkpoint_recovery` | Same manual path, used when an operator wants to force recovery review. |

## Statuses

Each attempt is recorded once, in its final state — `validating` and
`recovering` are transitional labels for future finer-grained reporting; the
current implementation writes a single row per attempt, immediately in
`completed` or `failed` status. (`completed_with_warnings`/`cancelled` remain
valid per the schema `CHECK` constraint for future use.)

## Validation performed before every recovery

`core_model/checkpoints/recovery_validator.py:validate_checkpoint_for_recovery`
checks, in order:

1. Checkpoint is registered and its status is `completed` or `verified`.
2. `TrainingCheckpointManager.verify()` — every file's SHA-256 checksum
   against the checkpoint's own manifest (covers combined/model/optimizer/
   scheduler/trainer-state checksums in one pass).
3. RNG state loads without error.
4. Model tensor names and shapes match a freshly constructed model for the
   job's current architecture config.
5. Dataset, tokenizer, and model-config checksums recorded in the checkpoint's
   `references.json` (captured at save time) match the *current* dataset
   version, tokenizer version, and model config checksums.
6. Stream checksum recorded at save time matches the job's current
   `latest_stream_checksum_sha256`.
7. Step and token counters are monotonic relative to the previous checkpoint
   for that job.

If any check fails, the checkpoint is marked `corrupt`, the attempt is
recorded with `status='failed'` and `error_code='checkpoint_validation_failed'`,
and the job is set to `status='failed'` — an operator must intervene; there is
no silent fallback to an older checkpoint.

## Resume guarantees

* **No optimizer-step duplication** — `pretraining_jobs.completed_steps`/
  `processed_tokens` are the source of truth for `run_pretraining()`'s
  `start_step`/`start_processed_tokens`; recovery only ever validates that the
  checkpoint being loaded is consistent with them, it never rewinds them.
* **Checkpoint-boundary resume only** — periodic checkpoints are saved every
  `checkpoint_interval_steps` completed optimizer steps
  (`PretrainingService._save_periodic_checkpoint`, wired through
  `core_model/training/trainer.py`'s `on_checkpoint` callback). If a crash
  happens between two periodic checkpoints, training resumes from the last
  completed one — any steps after it are re-run, not silently skipped or
  double-counted. This is a real, honest limitation: Brud AI does not claim
  exact mid-accumulation-step resume.
* **RNG/optimizer/scheduler state** are restored from the same checkpoint
  bundle that passed validation.
* **Split isolation** — recovery never changes which records are `train` vs
  `valid`; that partitioning is fixed at dataset-version build time.

## Where this differs from `docs/pretraining_recovery.md`

`pretraining_recovery.md` describes the Phase 9 baseline (pause/resume via
plain status flips, no fencing). This document describes what Phase 10 adds
on top: heartbeat/lease fencing, automated stale-job detection, and mandatory
pre-resume checkpoint validation for every recovery path, including plain
pause/resume.
