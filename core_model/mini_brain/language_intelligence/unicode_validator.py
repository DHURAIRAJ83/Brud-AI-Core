"""MB-13: Unicode Validator -- pure. Reuses `core_model.corpus.
unicode_normalization.normalize_unicode()` unchanged (Phase 16/19's
own NFC normalization, replacement-character/mojibake/escaped-unicode
detection, and Tamil combining-mark preservation check) per record,
and aggregates the result into one dataset-level Unicode Score. Never
reimplements Unicode integrity checking -- never writes a record.
"""

from __future__ import annotations

from typing import Any

from core_model.corpus.unicode_normalization import normalize_unicode

MAX_FLAGGED_INDICES_STORED = 200


def analyze_unicode(*, texts: list[str]) -> dict[str, Any]:
    total = len(texts)
    replacement_total = 0
    mojibake_total = 0
    escaped_total = 0
    combining_marks_broken = 0
    flagged_indices: list[int] = []

    for i, text in enumerate(texts):
        result = normalize_unicode(text)
        replacement_total += result["replacement_character_count"]
        mojibake_total += result["mojibake_count"]
        escaped_total += result["escaped_unicode_count"]
        if not result["tamil_combining_marks_preserved"]:
            combining_marks_broken += 1
        if result["unicode_integrity_status"] != "valid" or not result["tamil_combining_marks_preserved"]:
            flagged_indices.append(i)

    issue_rate = (len(flagged_indices) / total) if total else 0.0
    unicode_score = round(max(0.0, 100.0 - issue_rate * 100.0), 1)
    status = "valid" if unicode_score >= 90.0 else "needs_review" if unicode_score >= 60.0 else "invalid"

    return {
        "records_analyzed": total,
        "replacement_character_count": replacement_total,
        "mojibake_count": mojibake_total,
        "escaped_unicode_count": escaped_total,
        "combining_marks_broken_count": combining_marks_broken,
        "flagged_record_count": len(flagged_indices),
        "flagged_record_indices": flagged_indices[:MAX_FLAGGED_INDICES_STORED],
        "unicode_score": unicode_score,
        "status": status,
    }
