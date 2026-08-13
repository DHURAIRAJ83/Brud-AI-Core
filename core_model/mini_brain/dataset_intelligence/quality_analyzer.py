"""MB-05: Dataset Quality Analyzer -- measures missing values, empty
fields, invalid rows, and inconsistent fields, per record then
aggregated. Reuses `ExternalDatasetQualityService.assess()` (Phase 12
Step 18's own quality engine) UNCHANGED for the actual per-record
checks -- this module never re-implements broken-markup, repetition,
or low-information detection a second time. The one new piece here is
adapting `dataset_records`' four content fields into the single
raw/normalized text pair that service expects, and aggregating results
across a whole dataset.

"Broken references" is checked structurally against the records
actually supplied in the same call (e.g. a record's declared
`source_public_id` not matching the source it was fetched under) --
never a cross-table query MB-05 doesn't already have the data for.
"""

from __future__ import annotations

from typing import Any

from backend.services.dataset_sample_quality_service import ExternalDatasetQualityService
from core_model.corpus.language_detection import assess_language

_QUALITY_SERVICE = ExternalDatasetQualityService()

_LANGUAGE_CATEGORY_MAP = {
    "ta": "tamil", "en": "english", "tgl": "tanglish", "mixed": "mixed", "unknown": "unknown",
}

MAX_REPORTED_ISSUE_RECORDS = 200


def _record_text(record: dict[str, Any]) -> str:
    parts = [record.get("instruction"), record.get("input_text"), record.get("output_text")]
    return "\n".join(part for part in parts if part)


def analyze_quality(*, source_public_id: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    issue_counts: dict[str, int] = {}
    flagged_records: list[dict[str, Any]] = []
    empty_content_count = 0
    broken_reference_count = 0

    for record in records:
        text = _record_text(record)
        if not text.strip():
            empty_content_count += 1

        if record.get("source_public_id") and record["source_public_id"] != source_public_id:
            broken_reference_count += 1

        expected_language = _LANGUAGE_CATEGORY_MAP.get(record.get("language"), None)
        detected_language = _LANGUAGE_CATEGORY_MAP.get(
            assess_language(text)["language_category"] if text.strip() else None, None,
        )

        result = _QUALITY_SERVICE.assess(
            raw_content=text, normalized_content=text,
            structured_payload=record.get("metadata") or {},
            expected_language=expected_language, detected_language=detected_language,
        )

        if result["issues"]:
            flagged_records.append({"public_id": record.get("public_id"), "state": result["state"], "issues": result["issues"]})
            for issue in result["issues"]:
                issue_counts[issue["issue_type"]] = issue_counts.get(issue["issue_type"], 0) + 1

    clean_records = total - len(flagged_records)

    return {
        "total_records": total,
        "clean_records": clean_records,
        "flagged_records": len(flagged_records),
        "clean_ratio": round(clean_records / total, 3) if total else None,
        "issue_counts": issue_counts,
        "empty_content_records": empty_content_count,
        "broken_reference_records": broken_reference_count,
        "flagged_record_details": flagged_records[:MAX_REPORTED_ISSUE_RECORDS],
        "flagged_record_details_truncated": len(flagged_records) > MAX_REPORTED_ISSUE_RECORDS,
    }
