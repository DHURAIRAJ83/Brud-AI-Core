# Feedback Policies

A feedback policy controls collection, retention, and candidate
conversion for every feedback event submitted under it.

## Fields

`name`, `description`, `allowed_subject_types`, `allowed_feedback_types`,
`allow_free_text`, `allow_corrected_response`, `require_privacy_scan`,
`require_safety_scan`, `require_human_review`,
`require_dataset_approval`, `maximum_feedback_characters` (default
2000), `maximum_attachment_bytes` (default 2,000,000),
`default_retention_seconds` (default 7,776,000 — 90 days),
`allow_regression_fixture_creation`, `allow_dataset_candidate_creation`,
`lifecycle_status`.

## Lifecycle

`draft -> validated -> active -> deprecated -> archived`, the same
draft/validated/active pattern used by every policy-shaped resource in
this codebase (`FeedbackService.validate_policy()`/`activate_policy()`).
A feedback event may only be submitted under an `active` policy.

## Conservative defaults

Every default is safety-first: `require_privacy_scan`,
`require_safety_scan`, `require_human_review`, and
`require_dataset_approval` all default `true`. A policy author must
explicitly relax these, never the other way around.

## Settings

21 `BRUD_FEEDBACK_*` settings in `backend/core/config.py` back every
policy default and the bounded-resource guarantees:

| Setting | Default | Purpose |
|---|---|---|
| `BRUD_FEEDBACK_ENABLED` | `true` | master feature flag |
| `BRUD_FEEDBACK_MAX_COMMENT_CHARACTERS` | 2000 | free-text comment length cap |
| `BRUD_FEEDBACK_MAX_CORRECTION_CHARACTERS` | 4000 | corrected-response length cap |
| `BRUD_FEEDBACK_MAX_ATTACHMENT_BYTES` | 2,000,000 | attachment size cap (metadata-only, no binary storage) |
| `BRUD_FEEDBACK_DEFAULT_RETENTION_SECONDS` | 7,776,000 (90 days) | default feedback retention |
| `BRUD_FEEDBACK_REQUIRE_PRIVACY_SCAN` | `true` | enforce the privacy filter on submission |
| `BRUD_FEEDBACK_REQUIRE_SAFETY_SCAN` | `true` | enforce the safety filter on submission |
| `BRUD_FEEDBACK_REQUIRE_HUMAN_REVIEW` | `true` | require a human review before candidate creation |
| `BRUD_FEEDBACK_REQUIRE_DATASET_APPROVAL` | `true` | require explicit approval before export |
| `BRUD_FEEDBACK_ALLOW_FREE_TEXT` | `true` | allow free-text comments at all |
| `BRUD_FEEDBACK_ALLOW_CORRECTIONS` | `true` | allow corrected-response proposals |
| `BRUD_FEEDBACK_ALLOW_DATASET_CANDIDATES` | `true` | allow candidate creation at all |
| `BRUD_FEEDBACK_ALLOW_REGRESSION_FIXTURES` | `true` | allow regression fixture creation |
| `BRUD_FEEDBACK_MAX_ACTIVE_REVIEW_ASSIGNMENTS` | 20 | bounded concurrent open review assignments |
| `BRUD_FEEDBACK_MAX_ACTIVE_REGRESSION_RUNS` | 1 | one regression run at a time (CPU-only resource safety) |
| `BRUD_FEEDBACK_NEAR_DUPLICATE_THRESHOLD` | 0.9 | `SequenceMatcher` ratio floor for near-duplicate detection |
| `BRUD_FEEDBACK_BLOCK_TEST_LEAKAGE` | `true` | test-split contamination blocks approval |
| `BRUD_FEEDBACK_BLOCK_EVALUATION_LEAKAGE` | `true` | evaluation-fixture contamination blocks approval |
| `BRUD_FEEDBACK_BLOCK_REGRESSION_LEAKAGE` | `true` | regression-fixture contamination blocks approval |
| `BRUD_FEEDBACK_REQUIRE_KNOWN_LICENCE` | `true` | unknown/blocked licence blocks approval |
| `BRUD_FEEDBACK_REQUIRE_CURRENT_APPROVAL_CHECKSUM` | `true` | a stale approval (candidate changed since approval) blocks export |
