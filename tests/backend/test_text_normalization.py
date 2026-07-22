import unicodedata

from backend.services.text_normalization import normalize_text


def test_unicode_whitespace_and_tamil_combining_marks_are_preserved() -> None:
    decomposed = unicodedata.normalize("NFD", "தமிழ்")
    result = normalize_text(f"  {decomposed}\r\n\r\n\r\nஉரை  ", "ta")
    assert result.normalized == unicodedata.normalize("NFC", result.normalized)
    assert "தமிழ்" in result.normalized
    assert "\n\n\n" not in result.normalized
    assert result.changed


def test_english_tanglish_and_mixed_comparison_forms() -> None:
    english = normalize_text("  HELLO   World ", "en")
    tanglish = normalize_text("  Vanakkam  Nanba ", "tgl")
    mixed = normalize_text("Hello வணக்கம் 👋", "mixed")
    assert english.normalized == "HELLO World" and english.comparison_form == "hello world"
    assert tanglish.normalized == "Vanakkam Nanba"
    assert tanglish.comparison_form == "vanakkam nanba"
    assert "Hello" in mixed.normalized and "வணக்கம்" in mixed.normalized and "👋" in mixed.normalized


def test_zero_width_replacement_and_language_warnings() -> None:
    result = normalize_text("\u200bEnglish �", "ta")
    codes = {warning["code"] for warning in result.warnings}
    assert "\u200b" not in result.normalized
    assert {"replacement_character", "language_script_mismatch"} <= codes
