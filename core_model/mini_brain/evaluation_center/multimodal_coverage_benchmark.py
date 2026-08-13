"""MB-19: Multimodal Coverage Benchmark -- pure. Aggregates MB-16's
own record-type counts and MB-17's own evidence-type counts -- never
inspects an image, object, or graph edge itself.
"""

from __future__ import annotations

from typing import Any


def run_multimodal_coverage_benchmark(
    *, record_type_counts: dict[str, int], evidence_type_counts: dict[str, int],
) -> dict[str, Any]:
    total_records = sum(record_type_counts.values())
    total_evidence = sum(evidence_type_counts.values())

    if total_records == 0 and total_evidence == 0:
        return {
            "image_coverage": None, "object_coverage": None, "qa_coverage": None,
            "knowledge_graph_coverage": None, "total_record_count": 0, "total_evidence_count": 0,
            "disclosure": "no MB-16 records or MB-17 evidence were supplied -- multimodal coverage is honestly empty",
        }

    return {
        "image_coverage": round(record_type_counts.get("vision", 0) / total_records, 3) if total_records else 0.0,
        "object_coverage": round(evidence_type_counts.get("object", 0) / total_evidence, 3) if total_evidence else 0.0,
        "qa_coverage": round(record_type_counts.get("qa", 0) / total_records, 3) if total_records else 0.0,
        "knowledge_graph_coverage": (
            round(evidence_type_counts.get("graph_edge", 0) / total_evidence, 3) if total_evidence else 0.0
        ),
        "total_record_count": total_records,
        "total_evidence_count": total_evidence,
        "record_type_counts": record_type_counts,
        "evidence_type_counts": evidence_type_counts,
        "disclosure": (
            "image/qa coverage is the share of MB-16 record types; object/knowledge-graph coverage "
            "is the share of MB-17 evidence types -- a text-only dataset with no RAG evidence "
            "honestly scores 0.0 on the evidence-based metrics, never fabricated"
        ),
    }
