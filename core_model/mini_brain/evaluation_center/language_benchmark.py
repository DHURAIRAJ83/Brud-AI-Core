"""MB-19: Language Benchmark -- pure. Reuses MB-13's own already-built
Unicode/Tamil/Tanglish analyzers unchanged, plus the production RAG
system's own `classify_language()` for a real per-text majority-
language consistency check -- never a second implementation of any of
these.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.language_intelligence.tamil_character_validator import (
    validate_tamil_characters,
)
from core_model.mini_brain.language_intelligence.tanglish_intelligence import analyze_tanglish
from core_model.mini_brain.language_intelligence.unicode_validator import analyze_unicode
from core_model.rag.language_routing import classify_language


def run_language_benchmark(*, texts: list[str]) -> dict[str, Any]:
    if not texts:
        return {
            "records_analyzed": 0, "unicode_integrity": None, "tamil_character_validity": None,
            "tanglish_normalization_coverage": None, "language_consistency": None,
            "dominant_language": None, "language_distribution": {},
            "disclosure": "no text was supplied -- language benchmark is honestly empty, not fabricated",
        }

    unicode_report = analyze_unicode(texts=texts)
    tamil_report = validate_tamil_characters(texts=texts)
    tanglish_report = analyze_tanglish(texts=texts)

    categories = [classify_language(text)["language_category"] for text in texts]
    distribution: dict[str, int] = {}
    for category in categories:
        distribution[category] = distribution.get(category, 0) + 1
    dominant_language = max(distribution, key=distribution.get)
    consistency = round(distribution[dominant_language] / len(categories), 3)

    return {
        "records_analyzed": len(texts),
        "unicode_integrity": unicode_report["unicode_score"],
        "tamil_character_validity": tamil_report["character_score"],
        "tanglish_normalization_coverage": tanglish_report["confidence_score"],
        "language_consistency": round(consistency * 100, 1),
        "dominant_language": dominant_language,
        "language_distribution": distribution,
        "details": {
            "unicode": unicode_report, "tamil": tamil_report, "tanglish": tanglish_report,
        },
        "disclosure": (
            "language_consistency is the fraction of records classified into the single dominant "
            "language category by the production RAG router's own classify_language() -- a mixed-"
            "language dataset by design will score lower here, which is expected, not a defect"
        ),
    }
