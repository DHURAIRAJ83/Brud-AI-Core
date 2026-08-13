"""MB-04A: the structured prompt builder -- Role / Task / Knowledge /
Workflow / Rules / Expected response language / Response format /
Confidence, instead of MB-04's flat six-line template. Pure string
assembly: no model call, no I/O.

The language directive is deliberately repeated at both the top and
the bottom of the prompt (primacy + recency) -- small CPU models lose
track of instructions placed only once in the middle of a long
prompt; this is ordinary prompt engineering, not new architecture.
"""

from __future__ import annotations

from typing import Any

_LANGUAGE_LABEL = {"tamil": "Tamil", "english": "English"}
_LANGUAGE_DIRECTIVE = {
    "tamil": "நீங்கள் இந்த கேள்விக்கு தமிழில் மட்டுமே பதிலளிக்க வேண்டும். (Respond ONLY in Tamil.)",
    "english": "You must respond in English only.",
}

ROLE_TEXT = (
    "You are Brud Mini Brain, an Admin-only assistant for the Brud AI system. "
    "You explain the system; you never execute training, modify datasets, or "
    "take any admin action yourself."
)

RESPONSE_FORMAT_TEXT = (
    "A short, direct paragraph. No markdown headers, no bullet lists unless the "
    "question specifically asks for steps. No code fences unless the question is "
    "about code."
)


def _knowledge_block(context: dict[str, Any]) -> str:
    lines = ["Knowledge:"]
    if context["primary"]:
        lines.append("Primary:")
        lines.extend(f"- {item}" for item in context["primary"])
    if context["supporting"]:
        lines.append("Supporting:")
        lines.extend(f"- {item}" for item in context["supporting"])
    if not context["primary"] and not context["supporting"]:
        lines.append("No matching knowledge was found in the Brud Knowledge Core for this question.")
    return "\n".join(lines)


def _workflow_block(context: dict[str, Any]) -> str:
    if not context["workflow_lines"]:
        return "Workflow:\nNo specific workflow applies to this question."
    return "Workflow:\n" + "\n".join(f"- {line}" for line in context["workflow_lines"])


def _rules_block(context: dict[str, Any]) -> str:
    if not context["rules_lines"]:
        return "Rules:\n- Standard Admin-only guidance rules apply."
    return "Rules:\n" + "\n".join(f"- {line}" for line in context["rules_lines"])


def build_prompt(
    *,
    question: str,
    template_text: str,
    context: dict[str, Any],
    output_language: str,
    confidence_band: str,
    intent: str,
) -> str:
    language_label = _LANGUAGE_LABEL.get(output_language, "English")
    language_directive = _LANGUAGE_DIRECTIVE.get(output_language, _LANGUAGE_DIRECTIVE["english"])

    confidence_note = (
        f"Confidence: {confidence_band}. "
        + (
            "The available knowledge is limited -- state that plainly rather than "
            "inventing detail."
            if confidence_band in ("none", "low")
            else "Sufficient matching knowledge is available -- answer directly."
        )
    )

    sections = [
        f"Role: {ROLE_TEXT}",
        language_directive,
        f"Task: {template_text}",
        f"Detected intent: {intent}",
        f"Question: {question}",
        _knowledge_block(context),
        _workflow_block(context),
        _rules_block(context),
        f"Expected response language: {language_label}",
        f"Response format: {RESPONSE_FORMAT_TEXT}",
        confidence_note,
        language_directive,
        "Answer:",
    ]
    return "\n\n".join(sections)


def rebuild_with_stronger_language_directive(prompt: str, *, output_language: str) -> str:
    """The ONE allowed deterministic rebuild after a failed
    response-language validation: re-emit the same prompt with the
    language directive repeated a third time, immediately before
    "Answer:", and made maximally explicit. Never a second, different
    strategy -- exactly one rebuild, exactly this rule."""

    directive = _LANGUAGE_DIRECTIVE.get(output_language, _LANGUAGE_DIRECTIVE["english"])
    strong = (
        f"IMPORTANT: {directive} Do not use any other language in your answer."
    )
    if prompt.endswith("Answer:"):
        return prompt[: -len("Answer:")] + strong + "\n\nAnswer:"
    return prompt + "\n\n" + strong + "\n\nAnswer:"
