from core_model.admin_assistant.language_preference import (
    RESOLUTION_SOURCES,
    RESPONSE_LANGUAGES,
    dominant_language_for_mixed,
    resolve_response_language,
    to_short_code,
)

TAMIL_MESSAGE = "இந்த தரவுத்தொகுப்பு பயிற்சிக்கு தயாராக உள்ளதா?"
ENGLISH_MESSAGE = "Is this dataset ready for training?"
TANGLISH_MESSAGE = "Indha dataset training-ku ready-a irukku?"
MIXED_MESSAGE = "தரவுத்தொகுப்பு readyஆ trainingக்கு உள்ளது dataset file"


def test_request_override_wins_over_everything() -> None:
    resolved = resolve_response_language(
        message_text=TAMIL_MESSAGE,
        request_override="english",
        saved_preference="tamil",
        session_preference="tanglish",
    )
    assert resolved.resolved_language == "english"
    assert resolved.configured_mode == "english"
    assert resolved.source == "request_override"
    assert resolved.detected_input_language is None


def test_saved_preference_overrides_message_language() -> None:
    resolved = resolve_response_language(
        message_text=TAMIL_MESSAGE, saved_preference="english", session_preference="tanglish"
    )
    assert resolved.resolved_language == "english"
    assert resolved.source == "saved_admin_preference"


def test_session_preference_used_only_without_saved_preference() -> None:
    resolved = resolve_response_language(message_text=TAMIL_MESSAGE, session_preference="tanglish")
    assert resolved.resolved_language == "tanglish"
    assert resolved.source == "session_preference"


def test_auto_saved_preference_falls_through_to_detection() -> None:
    resolved = resolve_response_language(message_text=ENGLISH_MESSAGE, saved_preference="auto")
    assert resolved.configured_mode == "auto"
    assert resolved.resolved_language == "english"
    assert resolved.source == "auto_detection"
    assert resolved.detected_input_language == "en"


def test_auto_detects_tamil() -> None:
    resolved = resolve_response_language(message_text=TAMIL_MESSAGE, saved_preference="auto")
    assert resolved.resolved_language == "tamil"
    assert resolved.detected_input_language == "ta"


def test_auto_detects_tanglish() -> None:
    resolved = resolve_response_language(message_text=TANGLISH_MESSAGE, saved_preference="auto")
    assert resolved.resolved_language == "tanglish"
    assert resolved.detected_input_language == "tgl"


def test_auto_detects_mixed_and_picks_dominant_language() -> None:
    resolved = resolve_response_language(message_text=MIXED_MESSAGE, saved_preference="auto")
    assert resolved.detected_input_language == "mixed"
    assert resolved.resolved_language in RESPONSE_LANGUAGES[:3]


def test_auto_with_empty_message_falls_back_to_tamil_default() -> None:
    resolved = resolve_response_language(message_text="", saved_preference="auto")
    assert resolved.detected_input_language == "unknown"
    assert resolved.resolved_language == "tamil"
    assert resolved.source == "default"


def test_no_preference_at_all_defaults_to_auto_mode() -> None:
    resolved = resolve_response_language(message_text=ENGLISH_MESSAGE)
    assert resolved.configured_mode == "auto"
    assert resolved.resolved_language == "english"


def test_invalid_saved_preference_is_ignored_and_falls_back_to_auto() -> None:
    resolved = resolve_response_language(message_text=ENGLISH_MESSAGE, saved_preference="klingon")
    assert resolved.configured_mode == "auto"
    assert resolved.source == "auto_detection"


def test_to_short_code_mapping() -> None:
    assert to_short_code("tamil") == "ta"
    assert to_short_code("english") == "en"
    assert to_short_code("tanglish") == "tgl"


def test_dominant_language_for_mixed_tamil_dominant() -> None:
    classification = {
        "tamil_script_ratio": 0.6, "latin_script_ratio": 0.3, "tanglish_lexicon_hits": [],
    }
    assert dominant_language_for_mixed(classification) == "tamil"


def test_dominant_language_for_mixed_latin_dominant_with_tanglish_hits() -> None:
    classification = {
        "tamil_script_ratio": 0.2, "latin_script_ratio": 0.5, "tanglish_lexicon_hits": ["irukku"],
    }
    assert dominant_language_for_mixed(classification) == "tanglish"


def test_dominant_language_for_mixed_latin_dominant_without_tanglish_hits() -> None:
    classification = {
        "tamil_script_ratio": 0.2, "latin_script_ratio": 0.5, "tanglish_lexicon_hits": [],
    }
    assert dominant_language_for_mixed(classification) == "english"


def test_resolution_sources_and_response_languages_are_the_documented_sets() -> None:
    assert set(RESOLUTION_SOURCES) == {
        "request_override", "saved_admin_preference", "session_preference",
        "auto_detection", "default",
    }
    assert set(RESPONSE_LANGUAGES) == {"tamil", "english", "tanglish", "auto"}
