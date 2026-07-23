# Base Training Experiments and Runs (Phase 11)

A **base training experiment** (`base_training_experiments`) groups one
representative dataset version, a tokenizer decision, a core model version,
and one or more comparable training runs under a single evaluation record.
It never trains anything itself — `BaseTrainingService` orchestrates the
existing Phase 9 `PretrainingService` and Phase 10 `TrainingEvaluationService`
rather than duplicating a trainer.

## Lifecycle

```
draft -> profiled -> tokenizer_evaluated -> ready -> running -> completed
                                                          \-> archived
```

`status` advances automatically as the corresponding step (`generate_profile`,
`evaluate_tokenizer`, first `create_run`, first `queue_run`,
`select_candidate`) completes; it is never set directly by an API caller.

## Tokenizer suitability

`evaluate_tokenizer()` calls `TokenizerService.evaluate_suitability()` — a
Phase 11 addition to the existing tokenizer registry (`backend/services/
tokenizer_registry.py`) that reuses `_processor()`, `_dataset_rows()`,
`_evaluate_rows()`, and `_record_fields()` against an *arbitrary* dataset
version, without writing to the tokenizer's own `tokenizer_evaluations`
table (that table is scoped to the tokenizer's original training dataset).

The decision is one of:

- `reuse_existing_tokenizer` — round-trip success rate ≥
  `BRUD_BASE_TRAINING_TOKENIZER_MIN_ROUND_TRIP` (0.95 default) and unknown-
  token rate ≤ `BRUD_BASE_TRAINING_TOKENIZER_MAX_UNKNOWN_RATE` (0.05).
- `train_new_tokenizer_version` — round-trip passes but unknown-token rate
  is too high; the existing tokenizer is assigned anyway so runs are not
  blocked, but the recorded decision flags that a fresh tokenizer version
  should be trained before scaling up.
- `blocked_tokenizer_unsuitable` — round-trip success rate is below
  threshold, or no tokenizer is registered at all. `create_run` refuses to
  proceed while this decision stands.

## Runs

`create_run()` requires a tokenizer and core model already assigned to the
experiment, and a tokenizer decision other than `blocked_tokenizer_unsuitable`.
It merges the experiment's `training_configuration_json` with the run's own
`configuration`, builds a `PretrainingJobCreate`, and calls the existing
`PretrainingService.create_job()` + `.validate_job()` — the created
`pretraining_jobs` row is linked from `base_training_experiment_runs.
pretraining_job_id`. `queue_run()` then calls the same service's
`.queue_job()`, guarded by `_guard_single_active_job()` (only one running
job at a time) and `_guard_resources()` (memory + disk headroom checks).

Runs are compared, not raced: `compare_runs()` delegates to Phase 10's
`TrainingEvaluationService.compare_runs()`, and `comparisons()` reads Phase
10's existing `training_run_comparisons` table filtered to this experiment's
jobs — there is no second comparison table.

## API surface

All routes are under `/api/admin/base-training/...`, gated by
`require_admin` + CSRF on mutations, same as every other admin route:

```
GET/POST   /experiments
GET/PATCH  /experiments/{id}
POST/GET   /experiments/{id}/profile
POST/GET   /experiments/{id}/tokenizer-evaluate
POST       /experiments/{id}/runs
GET        /experiments/{id}/runs
GET        /runs/{run_id}
POST       /runs/{run_id}/queue
POST       /runs/{run_id}/evaluate
GET        /runs/{run_id}/language-metrics
GET        /runs/{run_id}/learning-checks
POST       /experiments/{id}/compare-runs
GET        /experiments/{id}/comparisons
POST       /experiments/{id}/select-candidate
GET        /experiments/{id}/candidate
GET        /experiments/{id}/manifest
POST       /experiments/{id}/manifest/verify
```

## CLI

`backend/base_training_cli.py` mirrors the API 1:1 for scripted/manual
verification: `list, inspect, profile, tokenizer-evaluate, create-run,
evaluate-run, compare, select-candidate, verify-manifest`. `create-run` and
`select-candidate` require typed confirmation (`create` / `select`
respectively) before acting, matching the confirmation pattern used by
Phase 9/10 CLIs for state-changing operations.
