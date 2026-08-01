from core_model.document_workspace.repeated_elements import detect_repeated_elements


def _page(number, header="Confidential Draft", body=None, footer=None):
    body = body if body is not None else f"Unique paragraph content specific to page {number}."
    # Padding lines push `body` outside the boundary-detection window so
    # only `header`/`footer` are ever candidates for cross-page repetition.
    lines = [header, body, f"padding line one {number}", f"padding line two {number}"]
    if footer:
        lines.append(footer)
    return (number, "\n".join(lines))


def test_no_suggestions_for_single_page():
    assert detect_repeated_elements([_page(1)]) == []


def test_repeated_header_detected_across_pages():
    pages = [_page(i, body=f"unique body {i}") for i in range(1, 6)]
    suggestions = detect_repeated_elements(pages)
    assert len(suggestions) == 1
    assert suggestions[0]["element_type"] == "header"
    assert suggestions[0]["candidate_text"] == "confidential draft"
    assert suggestions[0]["pages"] == [1, 2, 3, 4, 5]


def test_varying_page_numbers_are_never_falsely_merged():
    # Each page has a *different* page-number line -- cross-page recurrence
    # detection must never merge distinct numbers into one bogus
    # "repeated" suggestion (per-page page-number detection is handled
    # separately by `cleanup_suggestions.suggest_page_number_lines`).
    pages = [(i, f"Confidential Draft\nbody text {i}\n- {i} -") for i in range(1, 6)]
    suggestions = detect_repeated_elements(pages)
    assert all(s["element_type"] != "page_number" for s in suggestions)
    header_suggestion = next(s for s in suggestions if s["element_type"] == "header")
    assert header_suggestion["candidate_text"] == "confidential draft"


def test_constant_page_number_text_is_classified_as_page_number_type():
    # A degenerate but real case: the same literal numeric-looking string
    # recurs identically on every page (e.g. a static watermark).
    pages = [(i, f"Confidential Draft\nbody text {i}\n- 1 -") for i in range(1, 6)]
    suggestions = detect_repeated_elements(pages)
    types = {s["element_type"] for s in suggestions}
    assert "page_number" in types


def test_infrequent_line_is_not_flagged():
    pages = [_page(1), _page(2), _page(3, header="A different header entirely")]
    suggestions = detect_repeated_elements(pages, min_page_occurrences=3)
    assert suggestions == []


def test_never_returns_a_destructive_action_field():
    pages = [_page(i) for i in range(1, 5)]
    suggestions = detect_repeated_elements(pages)
    for suggestion in suggestions:
        assert suggestion["recommended_action"] in ("accept_removal", "review")
        assert "delete" not in suggestion
