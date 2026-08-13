"""MB-05: Dataset Analyzer -- structural, deterministic description of
a dataset source and its records. Pure: takes already-fetched
dictionaries (from MB-05's own read-only service layer), never queries
a database itself.

Honest adaptation: `dataset_records` has no spreadsheet-style
"columns" -- the closest real equivalent is which of its four content
fields (instruction/input_text/output_text/normalized_input) are
actually populated, reported as `populated_fields` below. Likewise
there is no independent record "version" at this table -- versioning
exists at the corpus-build level via the existing, unmodified
`DatasetVersioningService`, noted rather than fabricated.
"""

from __future__ import annotations

from typing import Any


def _count_by(records: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        key = record.get(field) or "unknown"
        counts[key] = counts.get(key, 0) + 1
    return counts


def _record_text_fields(record: dict[str, Any]) -> dict[str, bool]:
    return {
        field: bool((record.get(field) or "").strip())
        for field in ("instruction", "input_text", "output_text", "normalized_input")
    }


def analyze_dataset(*, source: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)

    populated_fields: dict[str, dict[str, int]] = {
        field: {"populated": 0, "empty": 0}
        for field in ("instruction", "input_text", "output_text", "normalized_input")
    }
    for record in records:
        for field, present in _record_text_fields(record).items():
            populated_fields[field]["populated" if present else "empty"] += 1

    metadata_keys: set[str] = set()
    for record in records:
        metadata_keys.update((record.get("metadata") or {}).keys())

    return {
        "source": {
            "public_id": source.get("public_id"),
            "name": source.get("name"),
            "file_type": source.get("source_type"),
            "language": source.get("language"),
            "status": source.get("status"),
            "licence_status": source.get("licence_status"),
        },
        "record_count": total,
        "by_record_type": _count_by(records, "record_type"),
        "by_language": _count_by(records, "language"),
        "by_status": _count_by(records, "status"),
        "populated_fields": populated_fields,
        "metadata_keys_observed": sorted(metadata_keys),
        "versioning_note": (
            "Raw dataset records have no independent version field -- versioning applies at "
            "the corpus-build level via the existing DatasetVersioningService, which MB-05 "
            "does not duplicate or call."
        ),
    }
