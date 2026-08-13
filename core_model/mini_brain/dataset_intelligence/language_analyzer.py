"""MB-05: Language Analyzer -- Tamil/English/Tanglish/Mixed/Unknown
percentages, character statistics, and token estimation across a
dataset. Reuses `core_model.corpus.language_detection.assess_language`
UNCHANGED (the same, already-audited, production script/lexicon-based
detector `ExternalDatasetSampleLanguageService` itself wraps) -- this
is the fourth place in this project that could plausibly need Tamil
language detection (after MB-04A's own question-oriented detector);
reusing the existing dataset-record-purposed one here, rather than
building a fifth implementation, is a direct application of "do not
duplicate existing functionality."
"""

from __future__ import annotations

from typing import Any

from core_model.corpus.language_detection import assess_language
from core_model.mini_brain.dataset_intelligence.token_estimator import estimate_dataset_tokens

_CATEGORY_MAP = {
    "ta": "tamil", "en": "english", "tgl": "tanglish", "mixed": "mixed", "unknown": "unknown",
    "numeric": "unknown", "code": "unknown",
}


def _record_text(record: dict[str, Any]) -> str:
    parts = [record.get("instruction"), record.get("input_text"), record.get("output_text")]
    return "\n".join(part for part in parts if part)


def analyze_language(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    distribution = {"tamil": 0, "english": 0, "tanglish": 0, "mixed": 0, "unknown": 0}
    tamil_char_total = 0
    latin_char_total = 0
    declared_vs_detected_mismatches = 0

    for record in records:
        text = _record_text(record)
        if not text.strip():
            distribution["unknown"] += 1
            continue
        assessment = assess_language(text)
        category = _CATEGORY_MAP.get(assessment["language_category"], "unknown")
        distribution[category] += 1
        tamil_char_total += round(assessment["tamil_script_ratio"] * len(text))
        latin_char_total += round(assessment["latin_script_ratio"] * len(text))

        declared = _CATEGORY_MAP.get(record.get("language"), None)
        if declared and declared != category:
            declared_vs_detected_mismatches += 1

    percentages = {
        key: round((count / total) * 100, 1) if total else 0.0
        for key, count in distribution.items()
    }

    return {
        "total_records": total,
        "distribution_counts": distribution,
        "distribution_percentages": percentages,
        "character_statistics": {
            "tamil_script_chars_observed": tamil_char_total,
            "latin_script_chars_observed": latin_char_total,
        },
        "declared_language_mismatches": declared_vs_detected_mismatches,
        "token_estimation": estimate_dataset_tokens(records),
    }
