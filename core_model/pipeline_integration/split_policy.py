"""Split-configuration policy per target pipeline (Step 8), and the
cross-build evaluation-isolation exclusion set.

Never a new statistical split algorithm -- this only decides *which*
`split_configuration` (train/validation/test percentages) the existing
`DatasetVersioningService` should be driven with for a given
`target_pipeline`, and which prior-build record ids must be excluded
from a training-target build's candidate pool. The actual shuffling/
grouping/leakage-check logic remains entirely
`DatasetVersioningService`'s own.
"""

from __future__ import annotations

from typing import TypedDict


class SplitConfiguration(TypedDict):
    train_percent: int
    validation_percent: int
    test_percent: int
    seed: int | None


# RAG ingestion (`RagIngestionService._resolve_source_content`) only
# ever reads `dataset_version_items WHERE split='train'` -- these
# targets have no statistical train/validation/test distinction at all,
# so every eligible record must land in `train` or it is silently
# never used by the target pipeline.
_FULL_TRAIN_TARGETS = frozenset(
    {"dataset_version", "rag", "tokenizer", "commercial_release", "public_export"}
)

# Evaluation content must remain structurally isolated (Step 17): every
# record in an evaluation-target build is `test`, never `train`/
# `validation` -- isolation is enforced by construction, not by a
# reviewable policy flag alone.
_FULL_TEST_TARGETS = frozenset({"evaluation"})

_DEFAULT_TRAINING_SPLIT: SplitConfiguration = {
    "train_percent": 90,
    "validation_percent": 5,
    "test_percent": 5,
    "seed": None,
}


def split_configuration_for_target(
    target_pipeline: str,
    *,
    requested: SplitConfiguration | None = None,
) -> SplitConfiguration:
    """`requested` is only ever honored for `pretraining`/
    `instruction_tuning` targets, where an admin-chosen split genuinely
    applies -- every other target's split is fixed by the pipeline's
    own structural requirement and never left to be misconfigured."""

    if target_pipeline in _FULL_TRAIN_TARGETS:
        return {"train_percent": 100, "validation_percent": 0, "test_percent": 0, "seed": None}
    if target_pipeline in _FULL_TEST_TARGETS:
        return {"train_percent": 0, "validation_percent": 0, "test_percent": 100, "seed": None}
    return requested or dict(_DEFAULT_TRAINING_SPLIT)


def excluded_by_prior_evaluation_build(
    entity_public_id: str, *, prior_evaluation_entity_ids: frozenset[str]
) -> bool:
    """A record already included (Step 8) in a *prior* evaluation-target
    build must never enter the train/validation split of any other
    build -- checked against the full history of prior evaluation-target
    `governed_build_request_items`, not just the current build's own
    candidate set."""

    return entity_public_id in prior_evaluation_entity_ids


def missing_grouping_metadata_warning(
    *, has_document_group: bool, has_semantic_family_group: bool, has_translation_group: bool
) -> str | None:
    """Step 8: 'Add warnings when safe grouping metadata is
    unavailable' -- never silently drops the grouping guarantee, and
    never blocks the build for it either."""

    if has_document_group or has_semantic_family_group or has_translation_group:
        return None
    return (
        "no document, semantic-family, or translation grouping metadata was found for "
        "this record -- split-safety grouping could not be applied to it"
    )


__all__ = [
    "SplitConfiguration",
    "split_configuration_for_target",
    "excluded_by_prior_evaluation_build",
    "missing_grouping_metadata_warning",
]
