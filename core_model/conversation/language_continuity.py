"""Language continuity decisions for chat orchestration.

Priority order: explicit current-turn language request, then an active
confirmed language-preference memory, then the most recent user turn's
detected language. Tanglish is never folded into English. Tamil is
never forced when the user has requested English.
"""

from __future__ import annotations

from core_model.rag.language_routing import classify_language


def decide_language(
    *,
    current_request_text: str,
    explicit_language_request: str | None,
    confirmed_language_preference: str | None,
    recent_user_turn_texts: list[str],
) -> dict[str, object]:
    if explicit_language_request:
        return {
            "language_category": explicit_language_request,
            "source": "explicit_current_turn_request",
        }

    if confirmed_language_preference:
        return {
            "language_category": confirmed_language_preference,
            "source": "confirmed_memory_preference",
        }

    detected = classify_language(current_request_text)
    if detected["language_category"] != "unknown":
        return {
            "language_category": detected["language_category"],
            "source": "current_request_detection",
        }

    for text in reversed(recent_user_turn_texts):
        detected = classify_language(text)
        if detected["language_category"] != "unknown":
            return {
                "language_category": detected["language_category"],
                "source": "recent_turn_fallback",
            }

    return {"language_category": "unknown", "source": "no_signal_available"}


def language_switched(previous_language: str | None, decided_language: str) -> bool:
    return (
        previous_language is not None
        and previous_language != "unknown"
        and previous_language != decided_language
    )
