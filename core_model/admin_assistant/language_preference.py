"""Phase 10A: pure Admin Assistant response-language resolution.

Reuses `core_model.rag.language_routing.classify_language()` unchanged
-- this module never re-implements language detection, it only maps
that classifier's short output categories (`ta`/`en`/`tgl`/`mixed`/
`unknown`) onto this phase's own full-word response-language
vocabulary (`tamil`/`english`/`tanglish`/`auto`), exactly the same
bridge-function pattern Phase 10's
`core_model.data_discovery.requirement_language_from_category` already
established for a different vocabulary pair.

See docs/admin_assistant/phase10a_language_preference_plan.md section 3.
"""

from __future__ import annotations

from dataclasses import dataclass

from core_model.rag.language_routing import classify_language

RESPONSE_LANGUAGES = ("tamil", "english", "tanglish", "auto")
CONCRETE_RESPONSE_LANGUAGES = ("tamil", "english", "tanglish")

# Every value the "source" field of a `ResolvedLanguage` can take --
# mirrors the task's exact resolution-priority chain: request_override
# -> saved_admin_preference -> session_preference -> auto_language_
# detection -> tamil_default. "auto_detection" and "default" are two
# distinct terminal outcomes of being in `configured_mode == "auto"`:
# the former means the message classified as something other than
# "unknown"; the latter means it did not, and the tamil fallback
# applied.
RESOLUTION_SOURCES = (
    "request_override", "saved_admin_preference", "session_preference",
    "auto_detection", "default",
)

_CATEGORY_TO_RESPONSE_LANGUAGE = {"ta": "tamil", "en": "english", "tgl": "tanglish"}

_RESPONSE_LANGUAGE_TO_SHORT_CODE = {"tamil": "ta", "english": "en", "tanglish": "tgl"}

# "Unknown input falls back to Tamil" -- the task's own explicit rule.
UNKNOWN_INPUT_FALLBACK_LANGUAGE = "tamil"


@dataclass(frozen=True)
class ResolvedLanguage:
    configured_mode: str
    resolved_language: str
    source: str
    detected_input_language: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            "configured_mode": self.configured_mode,
            "resolved_language": self.resolved_language,
            "source": self.source,
            "detected_input_language": self.detected_input_language,
        }


def to_short_code(resolved_language: str) -> str:
    """Bridges a resolved concrete response language to the classifier's
    own short-code vocabulary (never valid for `"auto"` -- callers must
    resolve first)."""

    return _RESPONSE_LANGUAGE_TO_SHORT_CODE[resolved_language]


def dominant_language_for_mixed(classification: dict[str, object]) -> str:
    """A "mixed" classification (both Tamil and Latin script present
    above threshold) still needs one concrete response language --
    whichever script dominates by ratio wins; a Latin-script tie is
    broken toward Tanglish when the bounded Tanglish lexicon actually
    matched something, otherwise English."""

    tamil_ratio = classification["tamil_script_ratio"]
    latin_ratio = classification["latin_script_ratio"]
    if tamil_ratio >= latin_ratio:
        return "tamil"
    if classification["tanglish_lexicon_hits"]:
        return "tanglish"
    return "english"


def response_language_from_category(
    category: str, classification: dict[str, object]
) -> str:
    if category == "mixed":
        return dominant_language_for_mixed(classification)
    return _CATEGORY_TO_RESPONSE_LANGUAGE.get(category, UNKNOWN_INPUT_FALLBACK_LANGUAGE)


def detect_response_language(message_text: str) -> tuple[str, dict[str, object]]:
    classification = classify_language(message_text)
    category = classification["language_category"]
    return response_language_from_category(category, classification), classification


def resolve_response_language(
    *,
    message_text: str = "",
    request_override: str | None = None,
    saved_preference: str | None = None,
    session_preference: str | None = None,
) -> ResolvedLanguage:
    """Implements the exact priority order from plan.md section 3:
    request_override -> saved_admin_preference -> session_preference ->
    auto_language_detection -> tamil_default. `request_override` is
    accepted here purely as a resolution input -- callers are
    responsible for never silently persisting it as the saved
    preference (see `docs/admin_assistant/phase10a_language_preference_plan.md`
    section 3)."""

    if request_override in RESPONSE_LANGUAGES:
        configured_mode = request_override
        mode_source = "request_override"
    elif saved_preference in RESPONSE_LANGUAGES:
        configured_mode = saved_preference
        mode_source = "saved_admin_preference"
    elif session_preference in RESPONSE_LANGUAGES:
        configured_mode = session_preference
        mode_source = "session_preference"
    else:
        configured_mode = "auto"
        mode_source = "default"

    if configured_mode != "auto":
        return ResolvedLanguage(
            configured_mode=configured_mode,
            resolved_language=configured_mode,
            source=mode_source,
            detected_input_language=None,
        )

    resolved_language, classification = detect_response_language(message_text)
    detected_category = classification["language_category"]
    source = "default" if detected_category == "unknown" else "auto_detection"
    return ResolvedLanguage(
        configured_mode="auto",
        resolved_language=resolved_language,
        source=source,
        detected_input_language=detected_category,
    )
