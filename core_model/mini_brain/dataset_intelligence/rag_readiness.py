"""MB-05: RAG Readiness Analyzer -- assesses whether THIS dataset's
raw records would be suitable INPUT for eventual RAG ingestion. Honest
scope: this does not analyze already-ingested RAG chunks (those live
in the existing, separate `rag.py` repository/corpus system, untouched
by MB-05) -- it is a pre-ingestion advisory over Dataset Studio
records, built from the already-computed Quality/Language/Duplicate
analyses.

`dataset_records` has no title field, so "missing titles" is always
reported as a real, structural gap (100%), not a per-record check --
disclosed rather than fabricated as a partial number.
"""

from __future__ import annotations

from typing import Any

MIN_CHUNK_CHARS = 200
MAX_CHUNK_CHARS = 2000
READY_SUITABLE_LENGTH_RATIO = 0.7
READY_CLEAN_RATIO = 0.85


def _record_text(record: dict[str, Any]) -> str:
    parts = [record.get("instruction"), record.get("input_text"), record.get("output_text")]
    return "\n".join(part for part in parts if part)


def assess_rag_readiness(
    *, records: list[dict[str, Any]], quality: dict[str, Any], duplicates: dict[str, Any],
    language: dict[str, Any],
) -> dict[str, Any]:
    total = len(records)
    if total == 0:
        return {"status": "Not Ready", "reasons": ["no records available"], "chunk_suitability_ratio": 0.0}

    suitable_length_count = sum(
        1 for r in records if MIN_CHUNK_CHARS <= len(_record_text(r)) <= MAX_CHUNK_CHARS
    )
    suitability_ratio = round(suitable_length_count / total, 3)

    citation_ready_count = sum(
        1 for r in records
        if any(key in (r.get("metadata") or {}) for key in ("source", "citation", "reference", "url"))
    )
    citation_ratio = round(citation_ready_count / total, 3)

    clean_ratio = quality.get("clean_ratio") or 0.0
    duplicate_ratio = round(duplicates["duplicate_record_count"] / total, 3)
    mismatch_ratio = round(language.get("declared_language_mismatches", 0) / total, 3)

    blockers: list[str] = []

    if clean_ratio < 0.5:
        blockers.append(f"document quality too low: clean_ratio {clean_ratio} is below 0.5")
    if suitability_ratio < 0.3:
        blockers.append(
            f"only {round(suitability_ratio * 100, 1)}% of records fall in a usable chunk size "
            f"range ({MIN_CHUNK_CHARS}-{MAX_CHUNK_CHARS} chars)"
        )
    if blockers:
        return {
            "status": "Not Ready", "reasons": blockers, "chunk_suitability_ratio": suitability_ratio,
            "citation_readiness_ratio": citation_ratio, "duplicate_chunk_ratio": duplicate_ratio,
            "document_consistency_mismatch_ratio": mismatch_ratio,
            "missing_titles": "100% -- dataset_records has no title field; RAG ingestion would need to derive or assign one",
        }

    improvements: list[str] = []
    if suitability_ratio < READY_SUITABLE_LENGTH_RATIO:
        improvements.append(f"chunk suitability {round(suitability_ratio * 100, 1)}% is below the {READY_SUITABLE_LENGTH_RATIO * 100:.0f}% Ready threshold")
    if clean_ratio < READY_CLEAN_RATIO:
        improvements.append(f"document quality clean_ratio {clean_ratio} is below the {READY_CLEAN_RATIO} Ready threshold")
    if citation_ratio < 0.5:
        improvements.append(f"only {round(citation_ratio * 100, 1)}% of records carry citation/source metadata")
    if duplicate_ratio > 0.05:
        improvements.append(f"{round(duplicate_ratio * 100, 1)}% duplicate records would become duplicate chunks")

    status = "Needs Improvement" if improvements else "Ready"
    if status == "Ready":
        improvements = [
            f"chunk suitability {round(suitability_ratio * 100, 1)}% >= {READY_SUITABLE_LENGTH_RATIO * 100:.0f}%",
            f"document quality clean_ratio {clean_ratio} >= {READY_CLEAN_RATIO}",
        ]

    return {
        "status": status, "reasons": improvements, "chunk_suitability_ratio": suitability_ratio,
        "citation_readiness_ratio": citation_ratio, "duplicate_chunk_ratio": duplicate_ratio,
        "document_consistency_mismatch_ratio": mismatch_ratio,
        "missing_titles": "100% -- dataset_records has no title field; RAG ingestion would need to derive or assign one",
    }
