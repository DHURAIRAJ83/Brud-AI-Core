from core_model.document_workspace.cleanup_suggestions import (
    generate_cleanup_suggestions,
    suggest_broken_word_joins,
    suggest_duplicated_lines,
    suggest_page_number_lines,
    suggest_repeated_whitespace,
    suggest_replacement_glyph_warnings,
    suggest_suspicious_latin_in_tamil,
    suggest_unbalanced_punctuation,
)


def test_replacement_glyph_detected():
    suggestions = suggest_replacement_glyph_warnings("hello � world")
    assert len(suggestions) == 1
    assert suggestions[0]["suggestion_type"] == "replacement_glyph"


def test_no_replacement_glyph_returns_empty():
    assert suggest_replacement_glyph_warnings("hello world") == []


def test_repeated_whitespace_detected():
    suggestions = suggest_repeated_whitespace("hello    world")
    assert len(suggestions) == 1
    assert suggestions[0]["proposed_text"] == " "


def test_broken_word_join_suggested():
    suggestions = suggest_broken_word_joins("this is a bro-\nken word")
    assert len(suggestions) == 1
    assert suggestions[0]["proposed_text"] == "broken"


def test_suspicious_latin_in_tamil_word():
    suggestions = suggest_suspicious_latin_in_tamil("தமிழ்Aமொழி")
    assert len(suggestions) == 1
    assert suggestions[0]["suggestion_type"] == "suspicious_latin_in_tamil"


def test_no_suspicious_latin_for_pure_tamil():
    assert suggest_suspicious_latin_in_tamil("தமிழ் மொழி") == []


def test_duplicated_line_detected():
    suggestions = suggest_duplicated_lines("hello world\nhello world\nsomething else")
    assert len(suggestions) == 1
    assert suggestions[0]["original_text"] == "hello world"


def test_page_number_line_detected():
    suggestions = suggest_page_number_lines("Some heading\n\n- 12 -\nMore content")
    assert len(suggestions) == 1
    assert suggestions[0]["original_text"] == "- 12 -"


def test_unbalanced_punctuation_detected():
    suggestions = suggest_unbalanced_punctuation("this (is unbalanced")
    assert any(s["suggestion_type"] == "unbalanced_punctuation" for s in suggestions)


def test_balanced_punctuation_returns_empty():
    assert suggest_unbalanced_punctuation("this (is balanced)") == []


def test_generate_cleanup_suggestions_combines_all_detectors():
    text = "bro-\nken word\n\n- 3 -\nduplicate line\nduplicate line"
    suggestions = generate_cleanup_suggestions(text)
    types = {s["suggestion_type"] for s in suggestions}
    assert "broken_tamil_word" in types or "other" in types
    assert "likely_page_number" in types
    assert "duplicated_line" in types


def test_generate_cleanup_suggestions_empty_text():
    assert generate_cleanup_suggestions("") == []


def test_suggestions_never_mutate_input_and_are_deterministic():
    text = "hello    world with bro-\nken word"
    first = generate_cleanup_suggestions(text)
    second = generate_cleanup_suggestions(text)
    assert first == second
    assert text == "hello    world with bro-\nken word"
