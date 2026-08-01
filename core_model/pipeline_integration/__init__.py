"""Pure, framework-agnostic policy for Phase 7 (Data Studio): governed
dataset-build selection/preflight across the eight target pipelines,
built entirely on top of the *existing* dataset build/versioning, RAG
ingestion, tokenizer/pretraining-readiness, instruction-tuning, and
evaluation systems (see
docs/data_studio/phase7_dataset_rag_training_integration_plan.md
section 2 for the full architecture rationale). No DB/IO here.
"""

from __future__ import annotations

# A "target_pipeline" is a distinct vocabulary axis from Phase 6's
# `core_model.data_governance.review.GOVERNANCE_TARGET_USES` (a
# rights-eligibility dimension) -- this is *which pipeline* a governed
# build is being produced for. `PIPELINE_TARGET_USE_MAP` below is the
# fixed, explicit bridge between the two; `GOVERNANCE_TARGET_USES` is
# never extended.
PIPELINE_TARGETS = (
    "dataset_version",
    "rag",
    "tokenizer",
    "pretraining",
    "instruction_tuning",
    "evaluation",
    "commercial_release",
    "public_export",
)

# Every candidate dataset_record is evaluated for the *mapped*
# `target_use` via the existing `GovernanceApprovalService.evaluate()`
# -- never a fabricated new rights dimension.
PIPELINE_TARGET_USE_MAP: dict[str, str] = {
    "dataset_version": "dataset_export",
    "rag": "rag",
    "tokenizer": "training",
    "pretraining": "training",
    "instruction_tuning": "training",
    "evaluation": "evaluation",
    "commercial_release": "commercial",
    "public_export": "public_export",
}

BUILD_REQUEST_STATUSES = (
    "draft",
    "preflight_running",
    "preflight_ready",
    "blocked",
    "approved_to_build",
    "building",
    "completed",
    "failed",
    "cancelled",
)

# A build request is done changing state on its own -- no further
# preflight/execute action can move it forward -- in exactly these
# terminal statuses.
TERMINAL_BUILD_STATUSES = frozenset({"completed", "failed", "cancelled"})

LINEAGE_RELATIONSHIP_TYPES = (
    "derived_from",
    "included_in",
    "exported_as",
    "indexed_into",
    "tokenized_into",
    "trained_from",
    "evaluated_with",
    "released_from",
    "supersedes",
)

# Governance decision codes specific to Phase 7 (distinct from Phase
# 6's own `decision_code` values -- these describe *build-selection*
# outcomes, not per-entity rights/quality decisions).
LEGACY_UNCLASSIFIED_STATUS = "legacy_unclassified"

RECORD_DECISIONS = ("eligible", "blocked", "warning", "excluded")

# Manual-Data/Structured-Record `record_type` values eligible for a
# `tokenizer`-target build by default (Step 14) -- metadata-only chunks
# and evaluation-only content are excluded structurally, never by
# omission.
DEFAULT_TOKENIZER_ELIGIBLE_RECORD_TYPES = frozenset(
    {
        "plain_text",
        "language_example",
        "dictionary_entry",
        "conversation",
        "tanglish_normalization",
    }
)

# Manual-Data/Structured-Record `record_type` values eligible for an
# `instruction_tuning`-target build (Step 16) -- exactly the seven
# types the task names, mapped through the existing
# `core_model.manual_data.DATASET_RECORD_TYPE_MAP` (never reinvented).
SFT_ELIGIBLE_RECORD_TYPES = frozenset(
    {
        "question_answer",
        "instruction_response",
        "conversation",
        "translation_pair",
        "tanglish_normalization",
        "grammar_example",
        "dictionary_entry",
    }
)

__all__ = [
    "PIPELINE_TARGETS",
    "PIPELINE_TARGET_USE_MAP",
    "BUILD_REQUEST_STATUSES",
    "TERMINAL_BUILD_STATUSES",
    "LINEAGE_RELATIONSHIP_TYPES",
    "LEGACY_UNCLASSIFIED_STATUS",
    "RECORD_DECISIONS",
    "DEFAULT_TOKENIZER_ELIGIBLE_RECORD_TYPES",
    "SFT_ELIGIBLE_RECORD_TYPES",
]
