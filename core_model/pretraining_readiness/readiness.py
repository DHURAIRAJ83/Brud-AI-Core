"""Phase 21A base-model pretraining-readiness gate -- pure
aggregation only, mirroring Phase 20's `core_model.corpus.readiness`
pattern exactly. Every dimension is scored independently, and a
warning or an unevaluated dimension is never silently upgraded to a
pass."""

from __future__ import annotations

from typing import Any

READINESS_DIMENSIONS = (
    "tokenizer_corpus_sufficiency",
    "tokenizer_quality",
    "tokenizer_artifact_integrity",
    "tokenizer_activation",
    "corpus_release_integrity",
    "dataset_snapshot_integrity",
    "partition_isolation",
    "tokenization_statistics",
    "model_configuration_safety",
    "data_loader_reliability",
    "training_configuration_validity",
    "forward_backward_stability",
    "checkpoint_integrity",
    "resume_integrity",
    "validation_execution",
    "resource_safety",
    "audit_completeness",
)

DIMENSION_STATUSES = ("pass", "warning", "fail", "not_evaluated")
READINESS_RESULTS = (
    "not_ready", "ready_for_experimental_pretraining", "ready_for_bounded_pretraining"
)


def overall_readiness(dimension_results: dict[str, str]) -> str:
    """`ready_for_bounded_pretraining` requires every single dimension
    to genuinely pass -- any fail is `not_ready`; any warning or
    unevaluated dimension caps the result at
    `ready_for_experimental_pretraining`, never silently upgraded."""

    if any(status == "fail" for status in dimension_results.values()):
        return "not_ready"
    if any(status in ("warning", "not_evaluated") for status in dimension_results.values()):
        return "ready_for_experimental_pretraining"
    return "ready_for_bounded_pretraining"


def build_readiness_report(dimension_results: dict[str, str]) -> dict[str, Any]:
    return {
        "overall_result": overall_readiness(dimension_results),
        "dimensions": dict(dimension_results),
        "pass_count": sum(1 for s in dimension_results.values() if s == "pass"),
        "warning_count": sum(1 for s in dimension_results.values() if s == "warning"),
        "fail_count": sum(1 for s in dimension_results.values() if s == "fail"),
        "not_evaluated_count": sum(1 for s in dimension_results.values() if s == "not_evaluated"),
    }
