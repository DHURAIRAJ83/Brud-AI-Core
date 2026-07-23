# Database Schema v12 (Phase 12)

Migration `012_phase12_instruction_tuning` upgrades schema version 11 → 12.
It is a separate, independent migration function (`_apply_v12`) from
migration 011 — Phase 11's `_apply_v11` is unchanged in behavior and content.

## New tables

| Table | Purpose | Mutability |
|---|---|---|
| `instruction_tuning_experiments` | One row per instruction-tuning experiment: links a base-pretrained model version, its verified source checkpoint, an approved instruction dataset version, the base model's tokenizer, and (once assigned) a validated instruction template. | Mutable lifecycle row |
| `instruction_tuning_runs` | One row per SFT run inside an experiment; links to a Phase 9 `pretraining_jobs` row — the **only** signal that a job is instruction-tuning rather than base-pretraining. | Mutable lifecycle row |
| `instruction_format_templates` | Versioned conversation template definitions, their tokenizer-compatibility validation result, and checksum. | Append-only |
| `instruction_dataset_profiles` | Deterministic per-experiment dataset profile: eligible/invalid/excluded counts, distributions, token statistics, input/label stream checksums, sufficiency status. | Append-only |
| `instruction_tuning_metrics` | Per-step training metrics: prompt/target/ignored token counts, training loss, learning rate, throughput, memory. | Append-only |
| `instruction_tuning_evaluations` + `instruction_tuning_evaluation_results` | Per-run evaluation passes (response-only loss, bounded-generation structural checks) and their per-language metric rows. | Append-only |
| `instruction_learning_checks` | The 12 fixed pass/warning/fail learning-evidence checks per run. | Append-only |
| `instruction_tuning_candidates` | Candidate-selection decisions, including base-checkpoint checksums before/after (proving the base checkpoint was never modified). | Append-only |
| `instruction_reproducibility_manifests` | Manifest JSON + SHA-256 checksum. | Append-only |

All tables above except `instruction_tuning_experiments` and
`instruction_tuning_runs` carry `BEFORE UPDATE`/`BEFORE DELETE` triggers that
raise `RAISE(ABORT, ...)` — history is genuinely append-only.

## Key columns

```
instruction_tuning_experiments:
  base_core_model_version_id  (FK core_model_versions, required)
  source_base_checkpoint_id   (FK pretraining_checkpoints, required — the
                                verified checkpoint this experiment fine-tunes)
  dataset_version_id          (FK dataset_versions, required)
  tokenizer_version_id        (FK tokenizer_versions, inherited from the base
                                model, immutable for the life of the experiment)
  instruction_template_id     (FK instruction_format_templates, nullable
                                until a validated template is assigned)
  status  CHECK IN (draft, profiled, template_validated, ready, running,
                     completed, completed_with_warnings, failed, archived)

instruction_tuning_runs:
  pretraining_job_id           (FK pretraining_jobs — the sole instruction-
                                 tuning signal; job_mode stays 'bounded_pretraining')
  truncation_policy  CHECK IN (reject, truncate_prompt_first, truncate_response_tail)
  input_stream_checksum_sha256 / label_stream_checksum_sha256  (two SEPARATE
                                 checksums — changing only the label mask
                                 changes the label checksum without touching
                                 the input checksum)
  assistant_target_tokens / prompt_tokens / ignored_tokens
  test_evaluated  CHECK IN (0,1)

instruction_dataset_profiles:
  total/eligible/invalid/excluded records, train/validation/test counts,
  language/record_type/source/licence distribution JSON,
  system_prompt_count, input_field_count, synthesized_flat_chat_count,
  average/maximum prompt & response tokens, empty_response_count,
  duplicate_prompt/response counts, exact_prompt_response_duplicate_count,
  response_language_mismatch_count, special_token_collision_count,
  truncation_risk_count, maskable_assistant_token_count,
  exclusion_reasons_json, input/label stream checksums,
  data_sufficiency_status CHECK IN (sufficient, limited_instruction_experiment,
                                     insufficient)

instruction_learning_checks:
  check_code CHECK IN (response_only_masking_verified, training_loss_improves,
    validation_response_loss_finite, language_metrics_complete,
    instruction_format_compliance, role_token_leakage_bounded,
    prompt_leakage_bounded, repetition_bounded, memorization_risk_bounded,
    checkpoint_integrity, base_model_lineage_complete, resource_limits_respected)

instruction_tuning_candidates:
  status CHECK IN (instruction_tuned_candidate, instruction_tuned_with_warnings, rejected)
  base_checkpoint_checksum_before / base_checkpoint_checksum_after
```

## Relationship to existing tables

No Phase 9–11 table is duplicated. Phase 12 tables reference and reuse:

* `core_model_versions` / `pretraining_checkpoints` for the eligible base
  candidate (Phase 8/9/11 promotion output).
* `dataset_versions` / `dataset_version_items` / `dataset_records` for the
  approved instruction dataset (Phase 6).
* `tokenizer_versions` for the inherited tokenizer (Phase 7).
* `pretraining_jobs` for the actual SFT run (Phase 9) — `create_run` builds
  a `PretrainingJobCreate` and calls the existing `PretrainingService`, it
  does not run its own trainer.
* `training_run_comparisons` (Phase 10) for run comparison — Phase 12's
  `compare_runs`/`comparisons` delegate to Phase 10's
  `TrainingEvaluationService` rather than adding a second comparison table.

## Migration safety

* `_apply_v12` is guarded by `SELECT 1 FROM schema_migrations WHERE version = 12` — safe to call repeatedly.
* `initialize_database()`/`upgrade_database()` now include 11 in the set of versions that trigger a pre-upgrade verified backup (previously 1–10).
* Fresh databases go straight to v12; a v11 database upgrades additively; a v12 database is a no-op.
* Verified via `tests/database/test_phase12_migration.py`: fresh→12, isolated v11 behavior unchanged, v11→12 upgrade with backup+data preservation, v12→12 no-op, idempotent re-application, deterministic table/index/trigger sets, mutability of the two lifecycle tables, and append-only enforcement on the other eight.
* Real dev database migrated v11→v12 with a verified backup; `PRAGMA integrity_check` = `ok`, `PRAGMA foreign_key_check` = no violations.

## Not in this migration

No Phase 12 table stores raw prompts, raw responses, full generated text,
absolute paths, or secrets. `instruction_dataset_profiles` and
`instruction_reproducibility_manifests` store aggregate counts and
checksums only; `instruction_tuning_evaluation_results.details_json` stores
structural check outcomes (booleans, rates, matched-character counts), never
the matched text itself.
