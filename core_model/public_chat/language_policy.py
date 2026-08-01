"""Public-chat answer-language policy (Step 5). A pure function layered
on top of `core_model.conversation.language_continuity.decide_language()`
-- never inside it, so Admin Assistant's own (Tanglish-permitting)
language policy stays completely isolated from this one.

Tamil input -> Tamil output. English input -> English output. Tanglish
input -> Tamil output by default. Mixed input -> Tamil by default
unless an explicit supported override selects English. Unknown ->
Tamil (the product's own Tamil-first default, matching every other
Tamil-first decision already made in this codebase).

Public users may only override to `ta` or `en` -- never `tanglish`,
which is not a valid public output language.
"""

from __future__ import annotations

from dataclasses import dataclass

from core_model.public_chat import PUBLIC_OUTPUT_LANGUAGES

_DEFAULT_OUTPUT_LANGUAGE = "ta"


@dataclass(frozen=True)
class AnswerLanguageDecision:
    answer_language: str
    # source: "explicit_override" | "tamil_input" | "english_input" |
    # "tanglish_default" | "mixed_default" | "unknown_default"
    source: str


def resolve_answer_language(
    *, detected_language_category: str, explicit_override: str | None = None
) -> AnswerLanguageDecision:
    if explicit_override is not None:
        normalized = explicit_override.strip().lower()
        if normalized in PUBLIC_OUTPUT_LANGUAGES:
            return AnswerLanguageDecision(answer_language=normalized, source="explicit_override")
        # An invalid/unsupported override (e.g. "tanglish") is ignored,
        # never honored -- fall through to detection-based policy.

    if detected_language_category == "ta":
        return AnswerLanguageDecision(answer_language="ta", source="tamil_input")
    if detected_language_category == "en":
        return AnswerLanguageDecision(answer_language="en", source="english_input")
    if detected_language_category == "tgl":
        return AnswerLanguageDecision(answer_language="ta", source="tanglish_default")
    if detected_language_category == "mixed":
        return AnswerLanguageDecision(answer_language="ta", source="mixed_default")
    return AnswerLanguageDecision(
        answer_language=_DEFAULT_OUTPUT_LANGUAGE, source="unknown_default"
    )


def is_valid_public_override(value: str | None) -> bool:
    return value is not None and value.strip().lower() in PUBLIC_OUTPUT_LANGUAGES


__all__ = ["AnswerLanguageDecision", "is_valid_public_override", "resolve_answer_language"]
