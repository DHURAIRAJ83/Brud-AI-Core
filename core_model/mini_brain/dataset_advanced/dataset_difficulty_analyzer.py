"""MB-05.1: Dataset Difficulty Analyzer -- Easy / Medium / Hard / Very
Hard. Rule-based only, no AI: a fixed-point score from word count,
average word length, and hits against a small, disclosed advanced-
vocabulary list, thresholded into 4 bands.
"""

from __future__ import annotations

from typing import Any

_ADVANCED_VOCABULARY = (
    "asymptotic", "eigenvalue", "polymorphism", "differential", "quantum",
    "stochastic", "homomorphism", "recursion", "concurrency", "thermodynamics",
    "asynchronous", "heuristic", "topology", "combinatorial",
)

_LEVELS = ("Easy", "Medium", "Hard", "Very Hard")
LONG_TEXT_WORD_THRESHOLD = 60
LONG_AVERAGE_WORD_LENGTH = 5.5


def _record_text(record: dict[str, Any]) -> str:
    parts = [record.get("instruction"), record.get("input_text"), record.get("output_text")]
    return "\n".join(part for part in parts if part)


def difficulty_for_text(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "Easy"
    words = stripped.split()
    word_count = len(words)
    average_word_length = sum(len(w) for w in words) / word_count if word_count else 0.0
    advanced_hits = sum(1 for term in _ADVANCED_VOCABULARY if term in stripped.lower())

    score = 0
    if word_count > LONG_TEXT_WORD_THRESHOLD:
        score += 1
    if average_word_length > LONG_AVERAGE_WORD_LENGTH:
        score += 1
    if advanced_hits >= 1:
        score += 1
    if advanced_hits >= 3:
        score += 1

    return _LEVELS[min(score, 3)]


def analyze_difficulty(records: list[dict[str, Any]]) -> dict[str, Any]:
    distribution = {level: 0 for level in _LEVELS}
    per_record: list[dict[str, str]] = []
    difficulty_by_id: dict[str, str] = {}

    for record in records:
        level = difficulty_for_text(_record_text(record))
        distribution[level] += 1
        public_id = record.get("public_id")
        per_record.append({"public_id": public_id, "difficulty": level})
        difficulty_by_id[public_id] = level

    return {
        "distribution": distribution,
        "per_record": per_record[:200],
        "difficulty_by_id": difficulty_by_id,
        "methodology": (
            "rule-based: word count, average word length, and hits against a fixed "
            "advanced-vocabulary list -- no AI, no learned model"
        ),
    }
