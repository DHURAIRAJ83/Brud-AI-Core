# Training Quality Gates

## Overview

`training_quality_assessments`/`training_quality_issues` (both append-only)
score the **integrity of a training run**, not the quality of the resulting
language model. Every response and UI surface carries this disclaimer
verbatim:

> This score measures training-process integrity. It does not measure Tamil
> fluency, chatbot quality, or instruction-following ability.

Scoring is a pure function (`core_model/training/quality_gates.py:assess`) —
identical inputs always produce identical scores and issues.

## Dimensions (10, each scored 0–1)

`data_integrity`, `stream_integrity`, `training_stability`, `loss_improvement`,
`validation_behavior`, `checkpoint_integrity`, `resume_integrity`,
`worker_integrity`, `resource_compliance`, `coverage_quality`. Overall score is
their unweighted mean.

## Readiness

* `ready_for_staging` — no issues at all.
* `warning` — at least one `info`/`warning`/`error` issue, no `blocking` issue. Promotion is possible with a required override comment (`POST /checkpoints/{id}/promote` with `override_comment`).
* `blocked` — at least one `blocking` issue. Promotion is refused regardless of any override comment.
* `not_assessed` — no assessment has been generated yet (schema default; not produced by `assess()` itself).

## Issue codes and severities

Checksum/integrity mismatches (`dataset_checksum_mismatch`,
`tokenizer_checksum_mismatch`, `model_config_mismatch`,
`stream_checksum_mismatch`, `non_finite_loss`, `validation_loss_missing`,
`checkpoint_corrupt`, `resume_inconsistent`) are always `blocking` and
non-overridable. Everything else (`loss_not_improving`, `loss_divergence`,
`validation_loss_worsening`, `train_validation_gap_high`,
`too_few_validation_tokens`, `coverage_too_low`,
`too_many_excluded_records`, `insufficient_training_tokens`,
`worker_lease_conflict`, `stale_worker_write`, `worker_recovery_failed`,
`memory_limit_exceeded`, `disk_limit_exceeded`, `throughput_unusually_low`) is
`warning`, `error`, or `info` and can be overridden with a comment.

## Configurable thresholds

```
BRUD_TRAINING_QUALITY_RULESET_VERSION           (default "phase10-v1")
BRUD_TRAINING_MIN_PROCESSED_TOKENS               (default 8)
BRUD_TRAINING_MIN_LOSS_IMPROVEMENT_RATIO         (default 0.0)
BRUD_TRAINING_MAX_TRAIN_VALIDATION_GAP           (default 5.0)
BRUD_TRAINING_MAX_EXCLUDED_RECORD_RATIO          (default 0.5)
BRUD_TRAINING_MIN_VALIDATION_TOKENS              (default 4)
BRUD_TRAINING_REQUIRE_VALIDATION                 (default true)
BRUD_TRAINING_REQUIRE_RESUME_CHECK_IF_RESUMED    (default true)
BRUD_TRAINING_MAX_NON_FINITE_EVENTS              (default 0)
BRUD_TRAINING_REQUIRE_ALL_CHECKPOINTS_VERIFIED   (default true)
BRUD_TRAINING_MIN_COVERAGE_RATIO                 (default 0.5)
```

The token-count defaults (`MIN_PROCESSED_TOKENS=8`, `MIN_VALIDATION_TOKENS=4`)
are intentionally low so a tiny CPU smoke job (tens of tokens) can reach
`ready_for_staging` without warnings, while remaining fully configurable
upward for real training runs.

## Inputs assembled by the service

`backend/services/training_evaluation_service.py:assess_quality` gathers:
latest per-split coverage, all checkpoints' verification status, the job's
recorded losses, recovery-attempt history (for resume consistency and worker
integrity counts), and checksum comparisons against the latest checkpoint's
saved `references.json` snapshot. `POST /jobs/{id}/quality/assess` persists
one assessment (with its issues) per call; `GET /jobs/{id}/quality` and
`GET /jobs/{id}/quality/issues` return the latest.
