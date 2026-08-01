from core_model.document_workspace.extraction_decision import (
    decide_extraction_method,
    has_repeated_garbage,
)


def test_empty_embedded_text_needs_ocr_when_image_available():
    decision = decide_extraction_method("", has_renderable_image=True)
    assert decision["method"] == "ocr"
    assert decision["reason"] == "no_embedded_text"


def test_empty_embedded_text_falls_back_to_embedded_without_image():
    decision = decide_extraction_method("", has_renderable_image=False)
    assert decision["method"] == "embedded"
    assert "ocr_unavailable_no_image" in decision["reason"]


def test_sufficient_tamil_text_stays_embedded():
    text = "இது ஒரு நல்ல தமிழ் வாக்கியம். இது போதுமான அளவு உரையைக் கொண்டுள்ளது."
    decision = decide_extraction_method(text, has_renderable_image=True)
    assert decision["method"] == "embedded"
    assert decision["signals"]["tamil_ratio"] > 0.5


def test_below_minimum_length_needs_ocr():
    decision = decide_extraction_method("Hi", has_renderable_image=True, min_text_length=20)
    assert decision["method"] == "ocr"
    assert decision["reason"] == "below_minimum_text_length"


def test_high_replacement_glyph_ratio_needs_ocr():
    text = "����� hello world this has enough characters to pass length"
    decision = decide_extraction_method(text, has_renderable_image=True)
    assert decision["method"] == "ocr"
    assert decision["reason"] == "high_replacement_glyph_ratio"


def test_low_lexical_content_suggests_hybrid():
    text = "!@#$ %^&* ()_+ -=[] {}|; ':\",./<>? " * 3
    decision = decide_extraction_method(text, has_renderable_image=True, min_text_length=5)
    assert decision["method"] == "hybrid"
    assert decision["reason"] == "low_lexical_content"


def test_has_repeated_garbage_detects_noise():
    assert has_repeated_garbage("hello......... world") is True
    assert has_repeated_garbage("hello world") is False
