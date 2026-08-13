"""MB-28: Answer Style Policy -- pure. Given a capability and locale,
returns style directives (system prompt text, tone, bilingual flag)
folded into the final prompt by `prompt_builder.py`.
"""

from __future__ import annotations

from typing import Any

_BASE_INSTRUCTIONS = (
    "You are the Brud AI Admin Assistant Intelligence layer, a local, "
    "read-only assistant for administrators of the Brud AI platform. "
    "You explain dashboard pages, summarize reports, and propose next "
    "actions. You never claim to have executed an action yourself -- "
    "any tool result you reference was already run and returned to you. "
    "Be concise and factual. Never invent numbers; only report numbers "
    "given to you in the conversation or tool results."
)

_CAPABILITY_TONE: dict[str, str] = {
    "chat": "Answer the administrator's question directly and concisely.",
    "explain_page": "Explain what this dashboard page is for and how to use it.",
    "summarize_report": "Summarize the report's key facts in plain language, preserving all numbers exactly.",
    "summarize_regression": "Summarize the regression run's pass/fail counts and any failures, preserving all numbers exactly.",
    "explain_error": "Explain what likely caused this error and how an administrator could investigate it.",
    "next_actions": "List concrete next actions in priority order.",
    "step_guide": "Give a numbered, step-by-step guide.",
    "checklist": "Give an operational checklist as short, actionable items.",
    "clarify": "Ask a short, specific clarifying question before answering.",
}


def style_for(*, capability: str, bilingual: bool = True) -> dict[str, Any]:
    tone = _CAPABILITY_TONE.get(capability, _CAPABILITY_TONE["chat"])
    bilingual_note = (
        " If the administrator writes in Tamil, reply in Tamil; otherwise reply in English."
        if bilingual
        else ""
    )
    system_prompt = f"{_BASE_INSTRUCTIONS} {tone}{bilingual_note}"
    return {
        "capability": capability,
        "bilingual": bilingual,
        "system_prompt": system_prompt,
    }
