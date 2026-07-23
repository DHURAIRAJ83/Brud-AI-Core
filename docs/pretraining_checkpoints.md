# Pretraining Checkpoints

Checkpoints are written under `BRUD_PRETRAINING_DIR` using server-generated safe names.

Layout:

```text
data/core_models/pretraining/<job-public-id>/step-00000020-<suffix>/
  model_state.pt
  optimizer_state.pt
  scheduler_state.pt
  rng_state.pt
  trainer_state.json
  config.json
  references.json
  manifest.json
  checksums.txt
```

The checkpoint manager writes to a temporary directory first, calculates SHA-256 checksums, then atomically promotes the directory. Loading is restricted to registered checkpoint metadata. `torch.load` uses CPU mapping and `weights_only=True` when supported.

Resume restores model, optimizer, scheduler, RNG, processed-token count, and block position from the latest checkpoint.

## Phase 10: periodic checkpoints and reference snapshots

Beyond the final checkpoint saved when a job completes/pauses/cancels,
`core_model/training/trainer.py:run_pretraining` now also invokes an optional
`on_checkpoint` callback every `config.checkpoint_interval_steps` completed
optimizer steps. `PretrainingService._save_periodic_checkpoint` uses this to
persist a `checkpoint_kind='periodic'` checkpoint mid-run, so an ungraceful
worker crash still leaves a recent, verified checkpoint to recover from — not
just whatever existed at the last pause/resume boundary.

`references.json` inside every checkpoint (final and periodic) now also
snapshots, at save time: the job's dataset-version checksum, tokenizer
checksum, model-config checksum, and current stream checksum. Recovery
(`core_model/checkpoints/recovery_validator.py`) recomputes all four from the
live database and rejects the checkpoint if any of them drifted since it was
saved — see [training_crash_recovery.md](training_crash_recovery.md).

Best-checkpoint selection (`PretrainingService._select_best_checkpoint`) runs
automatically whenever a job reaches `completed`/`completed_with_warnings`: it
picks the checkpoint with the lowest verified `validation_loss` (falling back
to lowest `training_loss` with a recorded event if no validation loss exists
anywhere), sets `is_best=1` on exactly one checkpoint, and records
`pretraining_jobs.best_checkpoint_public_id`. This selection does not change
again after the job finishes.
