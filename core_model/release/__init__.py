"""Phase 14 pure-function package: model registry, release candidates,
artifact governance, and metadata-level rollback.

None of this package trains a model, serves inference, or connects
anything to the public chatbot. It only reasons about already-registered,
already-verified artifacts (checkpoints, tokenizers, configs, datasets,
evaluation evidence) produced by Phases 8-13, and decides — deterministically
and conservatively — whether a candidate is eligible to become a release,
and whether a release is deployment-eligible. Registry existence never
implies model quality: a registered candidate may still be
``evaluation_blocked``/``not_deployable``.
"""

from __future__ import annotations

ARTIFACT_TYPES = (
    "model_checkpoint",
    "model_config",
    "tokenizer_model",
    "tokenizer_vocab",
    "tokenizer_manifest",
    "dataset_manifest",
    "base_training_manifest",
    "instruction_tuning_manifest",
    "evaluation_manifest",
    "model_card",
    "release_manifest",
    "licence_notice",
)

VERIFICATION_STATUSES = (
    "pending",
    "verified",
    "missing",
    "checksum_mismatch",
    "invalid",
    "not_applicable",
)

CANDIDATE_STATUSES = (
    "draft",
    "collecting_artifacts",
    "validating",
    "eligible",
    "eligible_with_warnings",
    "blocked",
    "approved",
    "released",
    "rejected",
    "superseded",
    "archived",
)

COMPATIBILITY_STATUSES = ("compatible", "compatible_with_warnings", "incompatible", "not_assessed")

ELIGIBILITY_STATUSES = ("eligible", "eligible_with_warnings", "blocked", "not_assessed")

ELIGIBILITY_DIMENSIONS = (
    "artifact_integrity",
    "lineage_completeness",
    "tokenizer_compatibility",
    "model_config_compatibility",
    "checkpoint_integrity",
    "training_evidence",
    "instruction_tuning_evidence",
    "evaluation_evidence",
    "safety_evidence",
    "licence_completeness",
    "model_card_completeness",
    "manifest_integrity",
    "resource_compatibility",
    "rollback_readiness",
)

RELEASE_STATUSES = ("draft", "released", "deprecated", "retired", "rolled_back", "archived")

DEPLOYMENT_ELIGIBILITY_STATUSES = ("deployable", "deployable_with_warnings", "not_deployable")

APPROVAL_ROLES = ("technical", "evaluation", "security", "release")

APPROVAL_DECISIONS = ("approve", "approve_with_warning", "reject", "request_changes")

ROLLBACK_STATUSES = ("draft", "validated", "approved", "executed", "rejected", "cancelled")

ISSUE_CODES = (
    "artifact_missing",
    "artifact_checksum_mismatch",
    "artifact_path_invalid",
    "checkpoint_corrupt",
    "model_config_mismatch",
    "tokenizer_missing",
    "tokenizer_vocab_mismatch",
    "special_token_mismatch",
    "dataset_lineage_missing",
    "training_manifest_missing",
    "instruction_manifest_missing",
    "evaluation_manifest_missing",
    "evaluation_blocked",
    "evaluation_warning",
    "safety_blocking_issue",
    "licence_missing",
    "licence_unsupported",
    "model_card_incomplete",
    "model_card_misleading",
    "release_manifest_mismatch",
    "approval_missing",
    "approval_stale",
    "version_conflict",
    "resource_requirement_unknown",
    "rollback_target_missing",
    "rollback_target_ineligible",
    "bundle_generation_failed",
    "bundle_checksum_mismatch",
)

SEVERITIES = ("info", "warning", "error", "blocking")
