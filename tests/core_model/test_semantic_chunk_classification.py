from core_model.semantic_chunk.classification import suggest_chunk_type


def test_short_line_before_longer_text_suggests_heading():
    suggestions = suggest_chunk_type(
        "Chapter One", next_text="This is a much longer paragraph that follows the heading."
    )
    types = {s["suggested_type"] for s in suggestions}
    assert "heading" in types


def test_example_prefix_suggests_example():
    suggestions = suggest_chunk_type("எடுத்துக்காட்டு: இது ஒரு வாக்கியம்.")
    types = {s["suggested_type"] for s in suggestions}
    assert "example" in types
    example = next(s for s in suggestions if s["suggested_type"] == "example")
    assert example["confidence"] > 0


def test_numbered_lines_suggest_list():
    text = "1. First item\n2. Second item\n3. Third item"
    suggestions = suggest_chunk_type(text)
    types = {s["suggested_type"] for s in suggestions}
    assert "list" in types


def test_term_meaning_pairs_suggest_dictionary_entry():
    text = "vanakkam - hello\nnandri - thank you\nporum - enough"
    suggestions = suggest_chunk_type(text)
    types = {s["suggested_type"] for s in suggestions}
    assert "dictionary_entry" in types


def test_plain_paragraph_yields_no_confident_suggestion():
    text = "This is just an ordinary paragraph of regular prose with no special markers at all."
    suggestions = suggest_chunk_type(text)
    types = {s["suggested_type"] for s in suggestions}
    assert "list" not in types
    assert "dictionary_entry" not in types
    assert "example" not in types


def test_empty_text_yields_no_suggestions():
    assert suggest_chunk_type("") == []


def test_every_suggestion_carries_a_reason_and_confidence():
    suggestions = suggest_chunk_type("எடுத்துக்காட்டு: sample")
    for suggestion in suggestions:
        assert suggestion["reason"]
        assert 0 < suggestion["confidence"] <= 1
