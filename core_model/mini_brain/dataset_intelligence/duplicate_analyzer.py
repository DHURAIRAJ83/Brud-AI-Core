"""MB-05: Duplicate Analyzer -- exact matches only, as required.
Reuses `ExternalDatasetDuplicateService.group_exact_duplicates()`
(Phase 12 Step 19's own duplicate/conflict engine) UNCHANGED for
`dataset_records`' own real, already-stored `content_hash` column
(computed by the existing `content_hash()` function at record
creation/update time -- MB-05 never recomputes it). The service's own
near-duplicate (fuzzy Jaccard) detection exists but is deliberately
NOT called here, since the task requires exact matches only.

Honest scope note: `dataset_records` has no independent "title" or
"document" field, so "duplicate titles" and "duplicate documents" (as
distinct from duplicate records/instructions/conversations) do not
map onto this table's real schema -- reported as `not_applicable`
rather than fabricated. "Duplicate files" is checked at the
dataset_source level via source name, the closest real equivalent.
"""

from __future__ import annotations

from typing import Any

from backend.services.dataset_sample_duplicate_service import ExternalDatasetDuplicateService

_DUPLICATE_SERVICE = ExternalDatasetDuplicateService()


def _exact_groups(entries: list[dict[str, Any]]) -> list[list[str]]:
    adapted = [{"public_id": entry["public_id"], "record_checksum": entry["checksum"]} for entry in entries if entry["checksum"]]
    return _DUPLICATE_SERVICE.group_exact_duplicates(adapted)


def analyze_duplicates(*, source: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    duplicate_records = _exact_groups([
        {"public_id": r.get("public_id"), "checksum": r.get("content_hash")} for r in records
    ])

    duplicate_instructions = _exact_groups([
        {"public_id": r.get("public_id"), "checksum": (r.get("instruction") or "").strip().lower() or None}
        for r in records
    ])

    duplicate_conversations = _exact_groups([
        {"public_id": r.get("public_id"), "checksum": (r.get("input_text") or "").strip().lower() or None}
        for r in records if r.get("record_type") == "chat"
    ])

    return {
        "duplicate_record_groups": duplicate_records,
        "duplicate_record_count": sum(len(g) for g in duplicate_records),
        "duplicate_instruction_groups": duplicate_instructions,
        "duplicate_conversation_groups": duplicate_conversations,
        "duplicate_titles": "not_applicable -- dataset_records has no title field",
        "duplicate_documents": "not_applicable -- dataset_records has no document field; see RAG Readiness for chunk-level analysis",
        "duplicate_files_note": (
            f"source '{source.get('name')}' checked individually -- cross-source duplicate-file "
            "detection would require fetching every other source's records, out of scope for a "
            "single-source, read-only analysis call"
        ),
    }
