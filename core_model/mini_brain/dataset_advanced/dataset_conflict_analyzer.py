"""MB-05.1: Dataset Conflict Analyzer -- detects records that answer
the SAME question differently. Reuses
`ExternalDatasetDuplicateService.find_conflicts()` (Phase 12 Step 19's
own generic key/value conflict grouping, already reused by MB-05 for
exact-duplicate grouping) UNCHANGED, adapted to compare normalized
instruction text against normalized answer text. Exact/normalized
text matching only -- no semantic similarity, no embeddings.
"""

from __future__ import annotations

from typing import Any

from backend.services.dataset_sample_duplicate_service import ExternalDatasetDuplicateService

_DUPLICATE_SERVICE = ExternalDatasetDuplicateService()


def _normalize(text: str | None) -> str:
    return " ".join((text or "").strip().lower().split())


def detect_conflicts(records: list[dict[str, Any]]) -> dict[str, Any]:
    adapted = []
    for record in records:
        question = _normalize(record.get("instruction"))
        if not question:
            continue
        adapted.append({
            "public_id": record.get("public_id"),
            "structured_payload": {"question": question, "answer": _normalize(record.get("output_text"))},
        })

    conflicts = _DUPLICATE_SERVICE.find_conflicts(adapted, key_field="question", value_field="answer")

    conflict_groups = [
        {
            "question_preview": conflict["key"][:120],
            "record_public_ids": conflict["record_public_ids"],
            "distinct_answers": conflict["conflicting_values"],
        }
        for conflict in conflicts
    ]

    total = len(adapted) or 1
    conflict_score = round(len(conflict_groups) / total, 3)

    return {
        "conflict_score": conflict_score,
        "conflict_groups": conflict_groups,
        "conflict_count": len(conflict_groups),
        "reason": (
            f"{len(conflict_groups)} question(s) have 2+ records with different answers, "
            f"out of {len(adapted)} records with a non-empty instruction"
        ),
    }
