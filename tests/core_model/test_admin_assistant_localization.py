import pytest

from core_model.admin_assistant.localization import (
    MESSAGE_CATALOG,
    catalog_message,
    localize,
    to_tanglish,
)


def test_to_tanglish_known_words() -> None:
    assert to_tanglish("இந்த") == "indha"
    assert to_tanglish("இன்னும்") == "innum"
    assert to_tanglish("இருக்கு") == "irukku"


def test_to_tanglish_empty_string() -> None:
    assert to_tanglish("") == ""


def test_to_tanglish_pure_english_is_unchanged() -> None:
    text = "Hugging Face dataset checkpoint-v12"
    assert to_tanglish(text) == text


def test_to_tanglish_preserves_placeholders_and_technical_terms() -> None:
    sentence = (
        "இது provider {target_public_id}-க்கு ஒரு {credential_type} credential "
        "reference-ஐ கட்டமைக்கும்."
    )
    result = to_tanglish(sentence)
    assert "{target_public_id}" in result
    assert "{credential_type}" in result
    assert "credential reference" in result
    assert "provider" in result


def test_to_tanglish_output_is_latin_script_only_for_tamil_runs() -> None:
    sentence = "இந்த dataset இன்னும் training-ku ready illa."
    result = to_tanglish(sentence)
    tamil_range = range(0x0B80, 0x0C00)
    assert not any(ord(ch) in tamil_range for ch in result)


def test_to_tanglish_geminated_consonants_stay_unvoiced() -> None:
    # "இருக்கு" -> the second 'க' in the "க்க" cluster must stay "k",
    # never voice to "g" -- geminated stops are always unvoiced.
    assert "kku" in to_tanglish("இருக்கு")
    assert "gku" not in to_tanglish("இருக்கு")


@pytest.mark.parametrize(
    "token",
    [
        "PHASE_10_COMPLETE_WITH_LIMITATIONS",
        "training_approved",
        "licence_unknown",
        "checkpoint-v12",
        "Hugging Face",
        "Apache-2.0",
        "/api/admin/dataset-discovery",
        "schema_version",
    ],
)
def test_to_tanglish_preserves_machine_readable_tokens_embedded_in_tamil(token: str) -> None:
    sentence = f"இந்த status {token} ஆக உள்ளது, இதை மாற்ற வேண்டாம்."
    result = to_tanglish(sentence)
    assert token in result


def test_localize_english() -> None:
    bilingual = {"en": "Hello", "ta": "வணக்கம்"}
    assert localize(bilingual, "english") == "Hello"


def test_localize_tamil() -> None:
    bilingual = {"en": "Hello", "ta": "வணக்கம்"}
    assert localize(bilingual, "tamil") == "வணக்கம்"


def test_localize_tamil_falls_back_to_english_when_missing() -> None:
    bilingual = {"en": "Hello"}
    assert localize(bilingual, "tamil") == "Hello"


def test_localize_tanglish_derives_from_tamil() -> None:
    bilingual = {"en": "This is not ready.", "ta": "இது தயாராக இல்லை."}
    result = localize(bilingual, "tanglish")
    assert result == to_tanglish(bilingual["ta"])
    tamil_range = range(0x0B80, 0x0C00)
    assert not any(ord(ch) in tamil_range for ch in result)


def test_localize_tanglish_falls_back_to_english_when_no_tamil() -> None:
    bilingual = {"en": "Hello only"}
    assert localize(bilingual, "tanglish") == "Hello only"


def test_localize_rejects_auto_as_unresolved() -> None:
    with pytest.raises(ValueError, match="concrete"):
        localize({"en": "x", "ta": "y"}, "auto")


def test_catalog_message_all_entries_have_en_and_ta() -> None:
    for key, entry in MESSAGE_CATALOG.items():
        assert "en" in entry and entry["en"], key
        assert "ta" in entry and entry["ta"], key


def test_catalog_message_renders_all_three_concrete_languages() -> None:
    for key in MESSAGE_CATALOG:
        english = catalog_message(key, "english")
        tamil = catalog_message(key, "tamil")
        tanglish = catalog_message(key, "tanglish")
        assert english and tamil and tanglish
        tamil_range = range(0x0B80, 0x0C00)
        assert not any(ord(ch) in tamil_range for ch in tanglish)
