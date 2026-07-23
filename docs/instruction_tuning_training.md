# Instruction-Tuning Training and Worker Dispatch (Phase 12)

## Shared trainer, not a second trainer

`core_model/training/trainer.py::run_instruction_tuning()` is a sibling to
`run_pretraining()`, not a fork or a rewrite. It reuses, unchanged:

- `core_model.training.optimizer.adamw`
- `core_model.training.scheduler.build_scheduler`
- Gradient accumulation, gradient clipping, non-finite detection
- The pause/cancel/checkpoint callback contract (`on_step`, `on_checkpoint`,
  `should_pause`, `should_cancel`) — identical signatures to `run_pretraining`
- `BrudForCausalLM.forward()` and `causal_lm_loss` — completely unmodified

The only real difference: each accumulation step consumes a pre-built
`(input_ids, attention_mask, labels)` example (produced by
`core_model.instruction_tuning.batch_builder`) instead of calling
`pad_sequences` on a raw token block. Token accounting is split three ways
(`processed_prompt_tokens`, `processed_target_tokens`, `processed_ignored_tokens`)
via a new `InstructionTrainerResult` dataclass that extends `TrainerResult`
with those three extra fields — the base fields, and every checkpoint/
metrics/resume mechanism that reads them, are unchanged.

Validation uses `instruction_response_loss()` (a public sibling of the
private helper `run_instruction_tuning` uses internally), which computes
loss **only** over each example's already-response-masked labels — never
re-deriving full-sequence labels the way `core_model.training.validation.validation_loss`
does for base pretraining. Base-pretraining loss and instruction-tuning
response-only loss are therefore never directly comparable without
labeling — the Admin Dashboard and CLI both surface this as an explicit note.

## Worker dispatch isolation

Both job kinds are ordinary `pretraining_jobs` rows with
`job_mode = 'bounded_pretraining'` (unchanged from Phase 9/11 — no CHECK
constraint rebuild). The only signal that a job is instruction-tuning is a
row in `instruction_tuning_runs.pretraining_job_id`.

`PretrainingService._claim()` gained one additive parameter,
`require_instruction_tuning: bool = False`, with one SQL clause:

```sql
{EXISTS|NOT EXISTS} (
  SELECT 1 FROM instruction_tuning_runs itr
  WHERE itr.pretraining_job_id = pretraining_jobs.id
)
```

`PretrainingService.run_one()` (the base-pretraining worker) calls `_claim()`
with the default `False` — its behavior is provably unchanged for every
existing Phase 9/10/11 job, since `instruction_tuning_runs` did not exist
before this phase and the clause resolves to "not linked" for every row that
predates it. `InstructionTuningService.run_one()` calls
`_claim(worker_id, require_instruction_tuning=True)`. Neither worker can ever
claim the other's job — proven directly by test
(`test_run_lifecycle_and_worker_dispatch_isolation`), not by convention.

`InstructionTuningService` composes a `PretrainingService` instance and
calls several of its lower-level methods directly (`_model_config`,
`_metric`, `_save_periodic_checkpoint`, `_save_training_checkpoint`,
`_select_best_checkpoint`, `_generate_run_summary`, `verify_checkpoint`) —
these are entirely generic over `pretraining_jobs`/`pretraining_checkpoints`/
`pretraining_job_events` and Phase 10's `training_run_summaries`, so reusing
them directly avoids duplicating ~250 lines of checkpoint/lease/metrics
glue. `_guard_single_active_job`/`_guard_resources` are duplicated onto
`InstructionTuningService` itself, matching the exact precedent already set
by `BaseTrainingService` in Phase 11 (which also does not reuse
`PretrainingService`'s private guards, but re-implements the same two
checks locally).

## Base checkpoint immutability

The base checkpoint (`source_base_checkpoint_id`, resolved once at
experiment-creation time) is only ever **read** — `TrainingCheckpointManager.load_states()`
loads its weights into a fresh `BrudForCausalLM` instance, and every new
checkpoint written during SFT is saved under the **instruction-tuning job's
own** `safe_name`, never overwriting the base checkpoint's file. Candidate
selection re-verifies this explicitly: `base_checkpoint_checksum_before`
(read once at experiment creation) and `base_checkpoint_checksum_after`
(re-verified via `TrainingCheckpointManager.verify()` at selection time) are
both persisted on the candidate row, and are identical by construction —
proven directly by test.

## `training_run_summaries`/stream-manifest reuse note

`TrainingEvaluationService.verify_streams()` (Phase 10) reports
`verified: false` for instruction-tuning jobs — this is expected, not a
bug. Phase 10's stream manifests are written by `PretrainingService._blocks()`
/`_record_streams()`, which instruction-tuning jobs never call (they build
their own batches via `batch_builder`). Phase 12's equivalent verification is
the `input_stream_checksum_sha256`/`label_stream_checksum_sha256` pair
recorded directly on `instruction_tuning_runs`, not Phase 10's
`training_stream_manifests` table.
