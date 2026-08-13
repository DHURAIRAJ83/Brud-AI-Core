"""MB-08: Difficulty Analyzer -- pure. Classifies knowledge-gap case
canonical questions into the task spec's Easy/Medium/Hard/Expert/Unknown
bands.

Reuses MB-05.1's `difficulty_for_text()` (word count, average word
length, advanced-vocabulary hits -- rule-based, no AI) UNCHANGED for
the actual scoring; this module only adds an "Unknown" band for
missing/redacted text and renames MB-05.1's "Very Hard" label to
"Expert" to match this phase's own taxonomy -- a label mapping, not a
second scoring implementation.
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.dataset_advanced.dataset_difficulty_analyzer import difficulty_for_text

_LABEL_MAP = {"Easy": "Easy", "Medium": "Medium", "Hard": "Hard", "Very Hard": "Expert"}
LEVELS = ("Easy", "Medium", "Hard", "Expert", "Unknown")


def classify_difficulty(text: str | None) -> str:
    if not text or not text.strip():
        return "Unknown"
    return _LABEL_MAP[difficulty_for_text(text)]


def analyze_difficulty(*, knowledge_gap_cases: list[dict[str, Any]]) -> dict[str, Any]:
    distribution = {level: 0 for level in LEVELS}
    for case in knowledge_gap_cases:
        text = None if case.get("content_unavailable_for_review") else case.get("canonical_question")
        level = classify_difficulty(text)
        distribution[level] += 1

    total = len(knowledge_gap_cases)
    return {
        "total_cases_classified": total,
        "distribution": distribution,
        "hard_or_expert_ratio": (
            round((distribution["Hard"] + distribution["Expert"]) / total, 4) if total else None
        ),
    }
