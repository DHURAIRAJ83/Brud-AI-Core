# Base Training Generalization and Memorization (Phase 11)

The core principle behind Phase 11: **a decreasing training loss is
evidence of optimization, not evidence of learned language patterns.**
Every generalization claim in this codebase is derived from validation/test
behavior, never from training loss alone.

## Learning checks

`core_model/training/learning_checks.py` runs 11 fixed, deterministic
checks per evaluated run (persisted append-only in
`base_training_learning_checks`, [[database_schema_v11]]):

| Check | Meaning |
|---|---|
| `training_loss_improves` | final training loss < initial training loss |
| `validation_loss_finite` | validation loss computed and finite |
| `test_loss_finite` | test loss computed and finite (**warning**, not fail, if not yet evaluated — see [[base_training_reproducibility]] `TEST_EVALUATION_NOT_RELIABLE`) |
| `no_non_finite_gradients` | zero NaN/Inf events during training |
| `checkpoint_integrity` | best/latest checkpoint loaded and verified |
| `dataset_stream_integrity` | Phase 10 stream checksum verified |
| `language_metrics_complete` | metrics exist for every language present in the data |
| `generalization_gap_bounded` | `validation_loss - training_loss` ≤ `BRUD_BASE_TRAINING_GENERALIZATION_MAX_GAP` (3.0 default) |
| `memorization_risk_bounded` | warns if training loss < 0.05 **and** the gap exceeds `BRUD_BASE_TRAINING_MEMORIZATION_MAX_GAP` (4.0 default) |
| `tokenizer_coverage_adequate` | unknown-token rate ≤ `BRUD_BASE_TRAINING_TOKENIZER_MAX_UNKNOWN_RATE` (0.05) |
| `resource_limits_respected` | run stayed within configured memory/time limits |

Each check yields `pass`, `warning`, or `fail` — never a numeric score that
could be mistaken for a single "quality percentage."

## Generalization classification

`classify_generalization()` returns exactly one of three honest categories,
never a stronger claim:

- `not_assessed` — no validation loss available, or training loss did not
  improve (nothing to generalize from).
- `optimization_success_only` — training loss improved, but validation loss
  did not improve and no language showed improvement. This is the default,
  conservative outcome, and is the expected result for small/limited-scale
  experiments.
- `limited_generalization_evidence` — training loss improved **and**
  validation loss improved **and** at least one language's metrics
  improved. This is deliberately the *strongest* category available; Phase
  11 never claims "proven generalization" or "language understanding."

## Memorization warnings

`memorization_warnings()` flags, independently of the pass/fail checks
above: `low_train_high_validation_gap` (near-zero training loss with a
large validation gap), `high_duplicate_rate`, and
`high_near_duplicate_rate` (both sourced from the dataset profile's
duplication statistics) — any of these can indicate the model memorized
near-duplicate training examples rather than generalizing.

## How this feeds candidate selection

`select_candidate()` in `BaseTrainingService` combines Phase 10's
training-process quality gate (`TrainingEvaluationService.assess_quality()`)
with these Phase 11 checks. A run can be `ready_for_staging` by Phase 10's
process-integrity standard and still be `selected_with_warnings` by Phase
11's generalization standard — that separation is intentional and is the
reason Phase 11 does not reuse Phase 10's quality-assessment table for its
own verdict (see [[base_training_candidate_selection]]).
