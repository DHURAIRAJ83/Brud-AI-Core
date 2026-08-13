"""MB-13: Tanglish Intelligence -- pure. Reuses `core_model.mini_brain.
prompting.tanglish_normalizer.normalize_tanglish()`/`normalization_
coverage()` unchanged (MB-04A's own fixed Tanglish -> Tamil lookup
dictionary) -- never a second transliteration implementation, never a
model call. Never overwrites the original text; every conversion is a
suggestion carried alongside it.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.prompting.tanglish_normalizer import normalize_tanglish, normalization_coverage

MAX_CONVERSIONS_STORED = 200
MAX_UNMATCHED_WORDS_STORED = 20


def analyze_tanglish(*, texts: list[str]) -> dict[str, Any]:
    total = len(texts)
    conversions: list[dict[str, Any]] = []
    coverage_sum = 0.0
    tanglish_record_count = 0

    for i, text in enumerate(texts):
        coverage = normalization_coverage(text)
        if coverage["latin_word_count"] > 0 and coverage["matched_word_count"] > 0:
            tanglish_record_count += 1
            match_ratio = coverage["matched_word_count"] / coverage["latin_word_count"]
            coverage_sum += match_ratio
            conversions.append({
                "record_index": i, "normalized_preview": normalize_tanglish(text)[:80],
                "coverage_ratio": round(match_ratio, 3),
                "unmatched_words": coverage["unmatched_words"][:MAX_UNMATCHED_WORDS_STORED],
            })

    average_coverage = round(coverage_sum / tanglish_record_count, 3) if tanglish_record_count else 0.0

    return {
        "records_analyzed": total,
        "tanglish_record_count": tanglish_record_count,
        "average_coverage_ratio": average_coverage,
        "conversions": conversions[:MAX_CONVERSIONS_STORED],
        "confidence_score": round(average_coverage * 100, 1),
        "disclosure": (
            "reuses the existing fixed Tanglish->Tamil dictionary "
            "(core_model.mini_brain.prompting.tanglish_normalizer) -- coverage is bounded to that "
            "dictionary's vocabulary, never a full transliteration model; original text is never "
            "overwritten"
        ),
    }
