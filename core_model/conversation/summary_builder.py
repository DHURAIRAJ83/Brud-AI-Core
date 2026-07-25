"""Conversation summary generation.

Default strategy for correctness-sensitive data is
``deterministic_extract`` -- a bounded, rule-based extraction that never
invents facts. ``bounded_model_summary`` builds a prompt for the
existing controlled inference runtime; the model's output must still
pass ``summary_validation`` before acceptance, exactly like every other
generated artifact in this project.
"""

from __future__ import annotations

import re
from typing import Any

_QUESTION_PATTERN = re.compile(r"[^.!?]*\?")
# Each group's tokens must all co-occur in the sentence, but need not be
# adjacent -- a real Tamil preference statement like "எனக்கு பதில்
# தமிழில் வேண்டும்" ("I want the answer in Tamil") has other words
# between "எனக்கு" and "வேண்டும்"; a naive contiguous-substring match
# would miss it entirely (caught and fixed during implementation).
_PREFERENCE_TOKEN_GROUPS = (
    ("எனக்கு", "வேண்டும்"),
    ("எனக்கு", "பிடிக்கும்"),
    ("i prefer",),
    ("i want",),
    ("please use",),
    ("i'd like",),
)

SYSTEM_INSTRUCTIONS = (
    "Summarize only what was explicitly said in the conversation below.\n"
    "Do not invent facts, numbers, or dates that are not present.\n"
    "Preserve uncertainty and unresolved questions.\n"
    "Do not treat assistant statements as user facts."
)


def estimate_token_count(text: str) -> int:
    return max(1, len(text) // 4)


def deterministic_extract(turns: list[dict[str, Any]]) -> dict[str, Any]:
    """Bounded, rule-based summary: lists explicit user-stated
    preferences (matched against a fixed marker list, never inferred)
    and any unresolved (unanswered) questions, in source order. Never
    fabricates a fact the turns do not contain."""

    preferences: list[str] = []
    unresolved_questions: list[str] = []
    user_texts = [turn["content"] for turn in turns if turn["role"] == "user"]
    assistant_texts = [turn["content"] for turn in turns if turn["role"] == "assistant"]

    for text in user_texts:
        lowered = text.lower()
        if any(all(token in lowered for token in group) for group in _PREFERENCE_TOKEN_GROUPS):
            preferences.append(text.strip())
        for match in _QUESTION_PATTERN.findall(text):
            unresolved_questions.append(match.strip())

    answered_fragment_count = sum(1 for text in assistant_texts if text.strip())
    if answered_fragment_count >= len(unresolved_questions):
        unresolved_questions = []

    lines = []
    if preferences:
        lines.append("Stated preferences: " + " | ".join(preferences))
    if unresolved_questions:
        lines.append("Unresolved questions: " + " | ".join(unresolved_questions))
    if not lines:
        lines.append("No explicit preferences or unresolved questions were stated.")
    summary_text = "\n".join(lines)

    return {
        "summary_text": summary_text,
        "generation_method": "deterministic_extract",
        "token_count": estimate_token_count(summary_text),
    }


def build_bounded_model_summary_prompt(
    turns: list[dict[str, Any]], *, bos_token: str = "<bos>"
) -> str:
    transcript = "\n".join(f"{turn['role']}: {turn['content']}" for turn in turns)
    return f"{bos_token}\n<system>\n{SYSTEM_INSTRUCTIONS}\n<user>\n{transcript}\n<assistant>"
