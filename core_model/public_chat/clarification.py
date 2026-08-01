"""Deterministic, bilingual, exactly-one-question clarification text
(Step 13). No LLM call -- a small, bounded template keyed by the
ambiguity category, derived from whichever `AMBIGUOUS_*` reason code
Phase 17's classification already emitted (its public service output
does not expose a separate `matched_category` field, but the reason
code carries the same information -- one lookup table maps reason code
-> template category, so this module reads nothing that isn't already
part of the classifier's own stable, documented output). Selects Tamil
or English per the resolved answer language.
"""

from __future__ import annotations

_CATEGORY_BY_REASON_CODE = {
    "AMBIGUOUS_UNCLEAR_PRONOUN": "unclear_pronoun",
    "AMBIGUOUS_MISSING_SUBJECT": "missing_subject",
    "AMBIGUOUS_MISSING_OBJECT": "missing_object",
    "AMBIGUOUS_MISSING_CONTEXT": "missing_subject",
    "AMBIGUOUS_INCOMPLETE_ACTION": "incomplete_action",
    "AMBIGUOUS_UNKNOWN_ACRONYM": "unknown_acronym",
    "AMBIGUOUS_CONFLICTING_INSTRUCTION": "conflicting_instruction",
}

_TEMPLATES: dict[str, dict[str, str]] = {
    "unclear_pronoun": {
        "ta": "இதில் குறிப்பிடும் விஷயம் என்ன என்பதை தெளிவுபடுத்த முடியுமா?",
        "en": "Could you clarify what you're referring to?",
    },
    "missing_subject": {
        "ta": "யாரைப் பற்றி அல்லது எதைப் பற்றி கேட்கிறீர்கள்?",
        "en": "Who or what is this question about?",
    },
    "missing_object": {
        "ta": "எதைச் செய்ய வேண்டும் என்று குறிப்பிட முடியுமா?",
        "en": "Could you specify what exactly you'd like done?",
    },
    "incomplete_action": {
        "ta": "எதை apply/செய்ய வேண்டும் என்பதை தெளிவுபடுத்த முடியுமா?",
        "en": "Could you clarify what this action should apply to?",
    },
    "unknown_acronym": {
        "ta": "இந்த சுருக்கச்சொல் எதைக் குறிக்கிறது என்பதை விளக்க முடியுமா?",
        "en": "Could you expand that abbreviation for me?",
    },
    "conflicting_instruction": {
        "ta": "இதில் இரண்டு முரண்பட்ட வழிமுறைகள் உள்ளன -- எதை செய்ய வேண்டும்?",
        "en": "That contains two conflicting instructions -- which one should I follow?",
    },
}

_DEFAULT_TEMPLATE = {
    "ta": "உங்கள் கேள்வியை இன்னும் கொஞ்சம் தெளிவாகக் கூற முடியுமா?",
    "en": "Could you rephrase your question with a bit more detail?",
}


def clarifying_question(*, reason_codes: tuple[str, ...], answer_language: str) -> str:
    category = None
    for code in reason_codes:
        if code in _CATEGORY_BY_REASON_CODE:
            category = _CATEGORY_BY_REASON_CODE[code]
            break
    templates = _TEMPLATES.get(category or "", _DEFAULT_TEMPLATE)
    return templates.get(answer_language, templates.get("ta", _DEFAULT_TEMPLATE["ta"]))


__all__ = ["clarifying_question"]
