"""MB-19: Benchmark Registry -- pure. The single, fixed definition of
every benchmark category and metric this phase ever produces. No
computation happens here -- this is the deterministic "menu" every
other benchmark module and the report generator reference, so the set
of metrics a suite claims to cover can never silently drift from what
was actually run.
"""

from __future__ import annotations

from typing import Any

BENCHMARK_CATEGORIES = (
    "language", "ocr", "grounding", "retrieval", "multimodal", "package",
)

METRIC_DEFINITIONS: dict[str, tuple[str, ...]] = {
    "language": (
        "unicode_integrity", "tamil_character_validity", "tanglish_normalization_coverage",
        "language_consistency",
    ),
    "ocr": ("ocr_text_availability", "ocr_dataset_overlap_ratio", "ocr_conflict_ratio"),
    "grounding": ("citation_validity_rate", "evidence_coverage_rate", "unsupported_sentence_ratio"),
    "retrieval": ("topk_evidence_availability", "average_relevance_score", "insufficient_evidence_rate"),
    "multimodal": ("image_coverage", "object_coverage", "qa_coverage", "knowledge_graph_coverage"),
    "package": ("manifest_checksum_validity_rate", "artifact_count_consistency_rate", "missing_file_count"),
}


def build_benchmark_suite(
    *, topic: str, source_dataset_count: int, source_rag_session_count: int,
    source_training_package_count: int,
) -> dict[str, Any]:
    return {
        "topic": topic,
        "categories": list(BENCHMARK_CATEGORIES),
        "metric_definitions": {category: list(metrics) for category, metrics in METRIC_DEFINITIONS.items()},
        "input_counts": {
            "source_dataset_count": source_dataset_count,
            "source_rag_session_count": source_rag_session_count,
            "source_training_package_count": source_training_package_count,
        },
        "no_model_inference_required": True,
        "disclosure": (
            "a fixed, deterministic suite definition -- the same category and metric names are used "
            "every run, so a report's claimed coverage can never silently drift from what was "
            "actually computed"
        ),
    }
