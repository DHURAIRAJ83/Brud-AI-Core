"""MB-13: Tamil Character Validator -- pure. Reuses `core_model.
mini_brain.quality.tamil_fluency_validator.validate_tamil_fluency()`
unchanged for its orphan-vowel-sign/virama detection -- a genuine
Unicode structural rule (a Tamil dependent vowel sign or virama must
attach to a preceding base consonant), never a second implementation.
Grantha letter (ஜ/ஷ/ஸ/ஹ) usage is counted as informational only --
Grantha letters are legitimate in loanwords, not a defect.

Disclosure: this does not, and does not claim to, classify Uyir/Mei/
Uyirmei letters or judge "illegal sequences" beyond the one genuine
structural rule above -- that would require real Tamil orthographic
grammar this codebase has never implemented.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.quality.tamil_fluency_validator import validate_tamil_fluency

_GRANTHA_LETTERS = frozenset("ஜஷஸஹ")
MAX_FLAGGED_INDICES_STORED = 200


def validate_tamil_characters(*, texts: list[str]) -> dict[str, Any]:
    total = len(texts)
    broken_sequence_count = 0
    grantha_usage_count = 0
    flagged_indices: list[int] = []

    for i, text in enumerate(texts):
        result = validate_tamil_fluency(text)
        if any(issue.startswith("broken_tamil_script_sequences") for issue in result["issues"]):
            broken_sequence_count += 1
            flagged_indices.append(i)
        grantha_usage_count += sum(1 for ch in text if ch in _GRANTHA_LETTERS)

    issue_rate = (broken_sequence_count / total) if total else 0.0
    character_score = round(max(0.0, 100.0 - issue_rate * 100.0), 1)

    return {
        "records_analyzed": total,
        "broken_sequence_count": broken_sequence_count,
        "grantha_letter_occurrences": grantha_usage_count,
        "flagged_record_count": len(flagged_indices),
        "flagged_record_indices": flagged_indices[:MAX_FLAGGED_INDICES_STORED],
        "character_score": character_score,
        "disclosure": (
            "detects orphan Tamil vowel-sign/virama sequences (a genuine Unicode structural rule) "
            "via the existing Tamil Fluency Validator -- never a claim of full Uyir/Mei/Uyirmei "
            "grammatical classification, which is a linguistic judgment this module does not make"
        ),
    }
