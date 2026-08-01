"""Deterministic, bilingual fallback reply text for the routes that
never call the model: `refuse` and `insufficient` (Steps 14-17). No
LLM call, no fabricated detail -- a small, bounded, honest template
per resolved answer language and reason.
"""

from __future__ import annotations

_REFUSAL_TEXT = {
    "ta": "மன்னிக்கவும், இந்த கோரிக்கைக்கு நான் பதிலளிக்க முடியாது.",
    "en": "I'm not able to help with that request.",
}

_INSUFFICIENT_GENERIC = {
    "ta": "இந்த கேள்விக்கு உறுதியான தகவல் தற்போது கிடைக்கவில்லை.",
    "en": "I don't have reliable information to answer this right now.",
}

_INSUFFICIENT_WEB_UNAVAILABLE = {
    "ta": (
        "இது தற்போதைய தகவலைச் சார்ந்த கேள்வி -- சரிபார்க்கப்பட்ட நிகழ்நேர தேடல் "
        "தற்போது இந்த அமைப்பில் கிடைக்கவில்லை. பழைய தகவலை பதிலாகத் தர விரும்பவில்லை."
    ),
    "en": (
        "This needs current, verified information -- live web lookup isn't "
        "available in this system yet, and I don't want to guess with outdated "
        "model knowledge."
    ),
}

_INSUFFICIENT_TOOL_UNAVAILABLE = {
    "ta": (
        "இதற்கு துல்லியமான கணக்கீடு தேவை -- அதற்கான deterministic tool தற்போது "
        "இந்த அமைப்பில் கிடைக்கவில்லை. தவறான மதிப்பீட்டைத் தர விரும்பவில்லை."
    ),
    "en": (
        "This needs a precise, deterministic calculation -- that tool isn't "
        "available in this system yet, and I don't want to guess at the answer."
    ),
}

_INSUFFICIENT_RAG = {
    "ta": "இதற்கான ஆதாரமான ஆவணங்களில் போதுமான தகவல் கிடைக்கவில்லை.",
    "en": "The approved documents don't contain enough evidence to answer this reliably.",
}

_INSUFFICIENT_MEMORY = {
    "ta": "இது தொடர்பான தகவலை உங்கள் உரையாடலில் இதுவரை நான் பதிவு செய்யவில்லை.",
    "en": "I don't have anything remembered from our conversation for this yet.",
}

_INSUFFICIENT_MODEL_UNAVAILABLE = {
    "ta": "தற்போது பதில் அளிக்கும் மாதிரி கிடைக்கவில்லை. பிறகு முயற்சிக்கவும்.",
    "en": "The answering model isn't available right now. Please try again shortly.",
}

# -- Phase 20: Trusted Web / Tool routes are now sometimes executable,
# sometimes honestly unavailable -- these cover the specific reasons
# an *attempted* Web search or tool call still couldn't produce an
# answer (distinct from `trusted_web_unavailable`/`tool_unavailable`
# above, which mean the route was never even attempted).

_INSUFFICIENT_WEB_NO_TRUSTED_SOURCE = {
    "ta": (
        "இந்தக் கேள்விக்கு நம்பகமான, சரிபார்க்கப்பட்ட மூலத்தை தேடலில் கண்டறிய "
        "முடியவில்லை."
    ),
    "en": "I couldn't find a trusted, verified source for this in the search results.",
}

_INSUFFICIENT_WEB_EVIDENCE = {
    "ta": (
        "தேடலில் கிடைத்த ஆதாரங்கள் இந்தக் கேள்விக்கு நம்பகமான பதில் தர "
        "போதுமானதாக இல்லை."
    ),
    "en": "The evidence I found wasn't strong enough to answer this reliably.",
}

_INSUFFICIENT_WEB_QUOTA = {
    "ta": "தேடல் வழங்குநரின் வரம்பு தற்போது தீர்ந்துவிட்டது. பிறகு முயற்சிக்கவும்.",
    "en": "The search provider's quota is exhausted right now. Please try again shortly.",
}

_INSUFFICIENT_WEB_FETCH_BLOCKED = {
    "ta": "பாதுகாப்பு காரணங்களுக்காக மூலப் பக்கத்தை பாதுகாப்பாக பெற முடியவில்லை.",
    "en": "The source page couldn't be safely retrieved for security reasons.",
}

_INSUFFICIENT_TOOL_UNSUPPORTED = {
    "ta": "இந்த வகை கணக்கீட்டிற்கு எந்த deterministic tool-ம் இப்போது இல்லை.",
    "en": "There's no deterministic tool for this kind of calculation yet.",
}

_INSUFFICIENT_TOOL_INPUT_INVALID = {
    "ta": "கொடுக்கப்பட்ட உள்ளீட்டை tool-ஆல் புரிந்துகொள்ள முடியவில்லை.",
    "en": "The tool couldn't understand the input as given.",
}

_INSUFFICIENT_TOOL_RATE_LIMITED = {
    "ta": "இந்த tool தற்போது அதிக பயன்பாட்டில் உள்ளது. சிறிது நேரம் கழித்து முயற்சிக்கவும்.",
    "en": "This tool is getting too many requests right now. Please try again shortly.",
}

_INSUFFICIENT_TOOL_TIMEOUT_OR_FAILED = {
    "ta": "கணக்கீட்டை முடிக்க முடியவில்லை. மீண்டும் முயற்சிக்கவும்.",
    "en": "The calculation couldn't be completed. Please try again.",
}

_BY_REASON = {
    "trusted_web_unavailable": _INSUFFICIENT_WEB_UNAVAILABLE,
    "tool_unavailable": _INSUFFICIENT_TOOL_UNAVAILABLE,
    "rag_scope_unavailable": _INSUFFICIENT_RAG,
    "rag_insufficient_evidence": _INSUFFICIENT_RAG,
    "memory_unavailable": _INSUFFICIENT_MEMORY,
    "memory_consent_required": _INSUFFICIENT_MEMORY,
    "model_assignment_unavailable": _INSUFFICIENT_MODEL_UNAVAILABLE,
    "web_provider_unavailable": _INSUFFICIENT_WEB_UNAVAILABLE,
    "web_quota_exceeded": _INSUFFICIENT_WEB_QUOTA,
    "web_no_trusted_source": _INSUFFICIENT_WEB_NO_TRUSTED_SOURCE,
    "web_evidence_insufficient": _INSUFFICIENT_WEB_EVIDENCE,
    "web_fetch_blocked": _INSUFFICIENT_WEB_FETCH_BLOCKED,
    "tool_disabled": _INSUFFICIENT_TOOL_UNAVAILABLE,
    "tool_unsupported": _INSUFFICIENT_TOOL_UNSUPPORTED,
    "tool_input_invalid": _INSUFFICIENT_TOOL_INPUT_INVALID,
    "tool_rate_limited": _INSUFFICIENT_TOOL_RATE_LIMITED,
    "tool_timeout": _INSUFFICIENT_TOOL_TIMEOUT_OR_FAILED,
    "tool_execution_failed": _INSUFFICIENT_TOOL_TIMEOUT_OR_FAILED,
}


def refusal_text(*, answer_language: str) -> str:
    return _REFUSAL_TEXT.get(answer_language, _REFUSAL_TEXT["ta"])


def insufficient_text(*, answer_language: str, reason_codes: tuple[str, ...] = ()) -> str:
    for code in reason_codes:
        templates = _BY_REASON.get(code)
        if templates:
            return templates.get(answer_language, templates["ta"])
    return _INSUFFICIENT_GENERIC.get(answer_language, _INSUFFICIENT_GENERIC["ta"])


__all__ = ["insufficient_text", "refusal_text"]
