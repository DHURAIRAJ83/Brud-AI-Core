"""Rule Engine -- fixed, deterministic Brud Rules applied to the
accumulated pipeline state. No AI, no learned weights: every rule
below is a plain boolean condition over already-computed fields.

Rule 1 (training boundary) mirrors the Admin Assistant's own
`BLOCKED_ACTION_SUBSTRINGS` discipline -- Brud Mini Brain must never
present itself as able to start/resume/execute training, only to
explain it.
Rule 2-3 mirror ChatOrchestrationService's own "no evidence -> fail
closed" philosophy, applied here to knowledge rather than RAG chunks.
Rule 4 is purely informational.
Rule 5 restates MB-01's own hard boundary in every single response.
"""

from __future__ import annotations

from typing import Any

_TRAINING_ACTION_WORDS = ("start", "run", "trigger", "execute", "launch", "begin", "resume")
_TRAINING_INTENTS = ("training", "tokenizer", "instruction_tuning")


def apply_rules(
    *, question: str, intent: str, knowledge_plan: dict[str, Any], excluded_knowledge: list[str],
) -> dict[str, Any]:
    flags: list[str] = []
    disclaimers: list[str] = []

    text = question.lower()
    if intent in _TRAINING_INTENTS and any(w in text for w in _TRAINING_ACTION_WORDS):
        flags.append("cannot_execute_training")
        disclaimers.append(
            "Brud Mini Brain can explain training concepts but can never start, resume, "
            "or execute training itself -- that remains a direct, admin-performed action."
        )

    if intent == "unknown":
        flags.append("needs_clarification")
        disclaimers.append("The question's intent could not be determined from known keywords.")

    if not knowledge_plan["primary_knowledge"] and not knowledge_plan["supporting_knowledge"]:
        flags.append("insufficient_knowledge")
        disclaimers.append(
            "No matching knowledge item was found in the Brud Knowledge Core for this question."
        )

    if excluded_knowledge:
        flags.append("deprecated_content_excluded")
        disclaimers.append(f"{len(excluded_knowledge)} deprecated knowledge item(s) were excluded.")

    disclaimers.append(
        "This is Admin-only guidance from Brud Mini Brain, never a Public Chat response."
    )

    return {
        "flags": flags,
        "disclaimers": disclaimers,
        "blocked": "cannot_execute_training" in flags,
    }
