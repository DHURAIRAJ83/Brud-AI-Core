# Release Eligibility Assessment (Phase 14)

`core_model/release/eligibility.py::assess_release_eligibility()` is
release eligibility, **never** production-deployment approval. It
follows the exact blocking-first cascade Phase 13's
`assess_chat_readiness()` already established: any blocking reason
forces `blocked` regardless of other scores; only zero blocking and zero
warnings yields `eligible`.

## Fourteen dimensions

```
artifact_integrity, lineage_completeness, tokenizer_compatibility,
model_config_compatibility, checkpoint_integrity, training_evidence,
instruction_tuning_evidence, evaluation_evidence, safety_evidence,
licence_completeness, model_card_completeness, manifest_integrity,
resource_compatibility, rollback_readiness
```

Every assessment reports all fourteen, even when a dimension has no
data yet (`not_applicable`/`unknown`, never omitted).

## Blocking conditions (non-overridable)

Missing or corrupt checkpoint, missing model config, missing tokenizer
or a tokenizer/config vocabulary mismatch, any artifact checksum
mismatch, incomplete lineage, evaluation status `evaluation_blocked`
(or no evaluation evidence at all when evaluation is required), a
missing base-training or instruction-tuning manifest, a missing
evaluation manifest, a blocking safety issue, a missing or unsupported
licence, an incomplete model card, a release-manifest mismatch, or a
candidate that is already retired/archived. **These cannot be overridden
by an approval** — `core_model.release.approval_policy
.validate_approval_submission()` independently refuses to record an
`approve`/`approve_with_warning` decision while the candidate's status is
`blocked`.

## Warning conditions

`evaluation_warning`, limited training-dataset scale, partial human
review, an unknown resource-requirement estimate, and a model card that
has not yet been (re-)validated after the eligibility assessment. Warnings
push the result to `eligible_with_warnings` rather than `eligible`, never
silently dropped.

## The current evaluation-blocked harness candidate

The Phase 13 manual-verification harness candidate — `instruction_tuned
= true`, `evaluation_required = true`, evaluation result
`evaluation_blocked` — is exactly the case this gate exists to catch.
Registering it as a Phase 14 candidate is allowed (registry existence
does not imply quality); assessing its eligibility always returns
`blocked`, with `evaluation_blocked` among the blocking reasons, and no
approval or release can ever be recorded for it. This is verified
directly, both by automated test
(`tests/backend/test_model_release_api.py::test_candidate_a_blocked_by_evaluation`)
and by the Phase 14 manual verification run.

## `EligibilityThresholds`

Every toggle above (`require_evaluation`, `allow_warning_eligibility`,
`require_licence`, `require_model_card`, `require_evaluation_manifest`,
`require_instruction_manifest`, `require_base_training_manifest`,
`require_rollback_target`) is a field on the `EligibilityThresholds`
dataclass, driven by `BRUD_RELEASE_*` settings — defaults fail closed
(require evidence, block on absence) rather than silently passing when
evidence is missing.
