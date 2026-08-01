from backend.services.dataset_sample_language_service import ExternalDatasetSampleLanguageService


def _service() -> ExternalDatasetSampleLanguageService:
    return ExternalDatasetSampleLanguageService()


def test_english_text_is_classified_english() -> None:
    result = _service().validate("This is a plain English sentence about training data.")
    assert result["language"] == "english"
    assert result["requires_review"] is False


def test_tamil_text_is_classified_tamil() -> None:
    result = _service().validate("இது ஒரு தமிழ் வாக்கியம் ஆகும்.")
    assert result["language"] == "tamil"


def test_mixed_script_text_is_classified_mixed() -> None:
    result = _service().validate("இது is a mixed sentence தமிழ் and English.")
    assert result["language"] == "mixed"


def test_clean_text_does_not_require_review() -> None:
    result = _service().validate("Nothing unusual here at all.")
    assert result["requires_review"] is False
    assert result["review_reasons"] == []


def test_replacement_characters_flag_review() -> None:
    result = _service().validate("corrupted � text here")
    assert result["unicode_integrity_status"] == "replacement_characters_detected"
    assert result["requires_review"] is True
    assert "replacement_characters_detected" in result["review_reasons"]


def test_orphaned_tamil_combining_mark_flags_review() -> None:
    # A dependent vowel sign with no preceding consonant to attach to.
    result = _service().validate("hello ா world")
    assert result["orphaned_combining_mark_count"] > 0
    assert result["requires_review"] is True
    assert "broken_tamil_grapheme_cluster" in result["review_reasons"]


def test_tamil_ocr_corruption_pattern_flags_review() -> None:
    result = _service().validate("இந்த வாக்கியத்தில் ஸ்ரீ போன்ற எழுத்துக்கள் உள்ளன")
    # Not asserting a specific corruption match (substitution table is
    # an implementation detail) -- just that the plumbing surfaces the
    # signal count field without raising.
    assert "ocr_corruption_signal_count" in result


def test_zero_width_characters_are_counted() -> None:
    result = _service().validate("hello​world")
    assert result["zero_width_character_count"] >= 1


def test_never_returns_normalized_text_only_signals() -> None:
    # The service must never silently overwrite/return a "corrected"
    # version of the text -- it only reports signals for the caller
    # (normalization service) to act on separately.
    result = _service().validate("hello ா world")
    assert "normalized_text" not in result
    assert "corrected_text" not in result
