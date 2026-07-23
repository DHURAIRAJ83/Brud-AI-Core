# Database Schema v11 (Phase 11)

Migration `011_phase11_base_pretraining_evaluation` upgrades schema version
10 → 11. It is a separate, independent migration function (`_apply_v11`)
from migration 010 — Phase 10's `_apply_v10` is unchanged in behavior and
content.

## New tables

| Table | Purpose | Mutability |
|---|---|---|
| `base_training_experiments` | One row per representative base-pretraining experiment: links a dataset version, an (initially unset) tokenizer version, an (initially unset) core model version, seeds, tokenizer decision, and lifecycle status. | Mutable lifecycle row (matches `pretraining_jobs` convention) |
| `base_training_experiment_runs` | One row per compatible training run inside an experiment; links to a Phase 9 `pretraining_jobs` row (no duplicate trainer), a run label/index, and a config diff. | Mutable lifecycle row |
| `base_training_dataset_profiles` | Append-only snapshot of dataset composition: counts, language/record-type/source/licence distributions, duplication and coverage statistics, and a `profile_checksum_sha256`. | Append-only |
| `base_training_language_metrics` | Append-only per-run, per-split, per-language (`ta`/`en`/`tgl`/`mixed`/`overall`) loss/perplexity/coverage metrics. | Append-only |
| `base_training_learning_checks` | Append-only pass/warning/fail results for the 11 fixed learning-evidence checks. | Append-only |
| `base_training_candidate_selections` | Append-only record of a candidate-selection decision, its generalization classification, and memorization-warning count. | Append-only |
| `base_training_reproducibility_manifests` | Append-only manifest of the experiment's full reproducibility record plus its SHA-256 checksum. | Append-only |

All tables above except `base_training_experiments` and
`base_training_experiment_runs` carry `BEFORE UPDATE`/`BEFORE DELETE`
triggers that raise `RAISE(ABORT, ...)` — history is genuinely append-only,
not just append-only by convention.

## Key columns

```
base_training_experiments:
  dataset_version_id (FK, required)
  tokenizer_version_id (FK, nullable until evaluated)
  core_model_version_id (FK, nullable until assigned)
  tokenizer_decision  CHECK IN (not_evaluated, reuse_existing_tokenizer,
                                train_new_tokenizer_version,
                                blocked_tokenizer_unsuitable)
  status              CHECK IN (draft, profiled, tokenizer_evaluated, ready,
                                running, completed, archived)
  latest_profile_public_id / latest_candidate_selection_public_id /
  latest_manifest_public_id

base_training_experiment_runs:
  pretraining_job_id (FK to Phase 9's pretraining_jobs — reused, not duplicated)
  run_label, run_index UNIQUE per experiment
  config_diff_json
  test_evaluated  CHECK IN (0,1) — enforces the held-out test split is
                  evaluated at most once per run

base_training_dataset_profiles:
  total/train/validation/test counts, total_characters, total_tokens,
  unique_token_count, language/record_type/source/licence distribution JSON,
  duplicate_rate, near_duplicate_rate, zero_token_rate, oversized_record_rate,
  tamil_script_coverage, english_latin_coverage, tanglish_coverage,
  mixed_script_coverage, warnings_json,
  data_sufficiency_status CHECK IN (sufficient, limited_experiment, insufficient),
  profile_checksum_sha256

base_training_language_metrics:
  split    CHECK IN (train, valid, test)
  language CHECK IN (ta, en, tgl, mixed, overall)
  evaluated_records, evaluated_tokens, loss, perplexity, unknown_token_rate,
  average_tokens_per_record, maximum_tokens_per_record, long_sequence_rate

base_training_learning_checks:
  check_code CHECK IN (training_loss_improves, validation_loss_finite,
    test_loss_finite, no_non_finite_gradients, checkpoint_integrity,
    dataset_stream_integrity, language_metrics_complete,
    generalization_gap_bounded, memorization_risk_bounded,
    tokenizer_coverage_adequate, resource_limits_respected)
  status CHECK IN (pass, warning, fail)

base_training_candidate_selections:
  status CHECK IN (selected_base_candidate, selected_with_warnings, rejected)
  generalization_result CHECK IN (optimization_success_only,
    limited_generalization_evidence, not_assessed)
  memorization_warning_count

base_training_reproducibility_manifests:
  manifest_json, manifest_checksum_sha256
```

## Relationship to existing tables

No Phase 9/10 table is duplicated. Phase 11 tables reference, and reuse:

* `dataset_versions` / `dataset_version_items` / `dataset_records` for the
  representative dataset (Phase 6).
* `tokenizer_versions` for tokenizer suitability decisions (Phase 7).
* `core_model_versions` for the model configuration under test (Phase 8).
* `pretraining_jobs` for the actual training run (Phase 9) — `create_run`
  builds a `PretrainingJobCreate` and calls the existing
  `PretrainingService`, it does not run its own trainer.
* `training_run_summaries`, `training_quality_assessments`,
  `training_run_comparisons` (Phase 10) for training-process integrity,
  quality gating, and run comparison — Phase 11's
  `TrainingEvaluationService` reuse means there is no second comparison or
  quality-assessment table.

## Migration safety

* `_apply_v11` is guarded by `SELECT 1 FROM schema_migrations WHERE version = 11` — safe to call repeatedly.
* `initialize_database()`/`upgrade_database()` now include 10 in the set of versions that trigger a pre-upgrade verified backup (previously 1–9).
* Fresh databases go straight to v11; a v10 database upgrades additively; a v11 database is a no-op.
* Verified via `tests/database/test_phase11_migration.py`: fresh→11, isolated v10 behavior unchanged, v10→11 upgrade with backup+data preservation, v11→11 no-op, idempotent re-application, deterministic table/index/trigger sets, mutability of the two lifecycle tables, and append-only enforcement on the other five.

## Not in this migration

No Phase 11 table stores full record text, raw tensors, absolute paths, or
secrets. `base_training_dataset_profiles` stores aggregate counts and a
checksum only; `base_training_reproducibility_manifests.manifest_json`
stores public IDs, checksums, and counts only.
