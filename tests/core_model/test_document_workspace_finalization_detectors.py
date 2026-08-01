"""Coverage for the 9 finalization-pass cleanup detectors (Task
Finalization §11/§12): 5 per-page detectors in cleanup_suggestions.py and
4 content-pattern cross-page detectors in repeated_elements.py."""

from core_model.document_workspace.cleanup_suggestions import (
    suggest_duplicate_paragraphs,
    suggest_email_addresses,
    suggest_noise_lines,
    suggest_phone_numbers,
    suggest_web_urls,
)
from core_model.document_workspace.repeated_elements import detect_repeated_elements


def _page(number: int, body: str) -> tuple[int, str]:
    return (number, body)


class TestPerPageDetectors:
    def test_web_url_detected_and_never_removed_silently(self):
        text = "See our source at https://example.org/policy for attribution."
        suggestions = suggest_web_urls(text)
        assert len(suggestions) == 1
        assert suggestions[0]["suggestion_type"] == "web_url"
        assert suggestions[0]["proposed_text"] == suggestions[0]["original_text"]
        assert suggestions[0]["risk_level"] == "medium"

    def test_no_web_url_in_plain_text(self):
        assert suggest_web_urls("This paragraph has no links in it at all.") == []

    def test_email_address_detected(self):
        suggestions = suggest_email_addresses("Contact admin@example.com for questions.")
        assert len(suggestions) == 1
        assert suggestions[0]["original_text"] == "admin@example.com"

    def test_no_email_from_ordinary_at_sign_usage(self):
        # "@" alone (e.g. a social handle without a domain) must not be
        # mistaken for a confirmed email address.
        assert suggest_email_addresses("Follow @examplehandle for updates.") == []

    def test_phone_number_detected_for_a_plausible_indian_number(self):
        suggestions = suggest_phone_numbers("Call us at +91 98765 43210 for support.")
        assert len(suggestions) == 1

    def test_short_numeric_sequence_is_not_classified_as_a_phone_number(self):
        # An ordinary numeric lesson/measurement (e.g. "12-34") must not be
        # misclassified as a phone number just because it has a separator.
        assert suggest_phone_numbers("The result of the equation is 12-34.") == []

    def test_noise_line_detected_for_scanner_artifacts(self):
        suggestions = suggest_noise_lines("###???***\nReal sentence here.")
        assert any(s["suggestion_type"] == "noise_line" for s in suggestions)

    def test_no_noise_line_for_ordinary_prose(self):
        assert suggest_noise_lines("This is a completely ordinary sentence.") == []

    def test_duplicate_paragraph_detected_within_a_page(self):
        paragraph = "This is a long enough paragraph to exceed the minimum duplicate length."
        filler = "Some other unrelated paragraph goes here for contrast."
        text = f"{paragraph}\n\n{filler}\n\n{paragraph}"
        suggestions = suggest_duplicate_paragraphs(text)
        assert len(suggestions) == 1
        assert suggestions[0]["suggestion_type"] == "duplicate_paragraph"

    def test_paragraphs_on_the_same_topic_but_different_text_are_not_flagged(self):
        text = (
            "Tamil grammar has several noun cases used in sentence construction.\n\n"
            "Tamil verbs also conjugate for tense, person, and number in speech."
        )
        assert suggest_duplicate_paragraphs(text) == []


class TestCrossPageContentPatternDetectors:
    def test_copyright_notice_is_always_review_never_auto_removed(self):
        pages = [_page(i, f"© 2026 Example Publisher\nbody text {i}") for i in range(1, 6)]
        suggestions = detect_repeated_elements(pages)
        copyright_suggestions = [s for s in suggestions if s["element_type"] == "copyright_notice"]
        assert len(copyright_suggestions) == 1
        assert copyright_suggestions[0]["recommended_action"] == "review"

    def test_navigation_text_detected_across_pages(self):
        pages = [_page(i, f"Table of Contents\nbody text {i}") for i in range(1, 6)]
        suggestions = detect_repeated_elements(pages)
        assert any(s["element_type"] == "navigation_text" for s in suggestions)

    def test_watermark_text_detected_and_never_auto_removed(self):
        pages = [_page(i, f"body text {i}\nConfidential") for i in range(1, 6)]
        suggestions = detect_repeated_elements(pages)
        watermark_suggestions = [s for s in suggestions if s["element_type"] == "watermark_text"]
        assert len(watermark_suggestions) == 1
        assert watermark_suggestions[0]["recommended_action"] == "review"

    def test_ordinary_repeated_heading_is_not_misclassified_as_watermark_or_logo(self):
        # A genuine, meaningful repeated chapter heading must still classify
        # as an ordinary header, not get swept into watermark/logo -- the
        # exact false-positive the task explicitly warns against.
        pages = [_page(i, f"Chapter One Overview\nbody text {i}") for i in range(1, 6)]
        suggestions = detect_repeated_elements(pages)
        assert suggestions[0]["element_type"] == "header"

    def test_logo_marker_detected_only_for_explicit_vocabulary(self):
        pages = [_page(i, f"Logo\nbody text {i}") for i in range(1, 6)]
        suggestions = detect_repeated_elements(pages)
        logo_suggestions = [s for s in suggestions if s["element_type"] == "logo_text"]
        assert len(logo_suggestions) == 1
        assert logo_suggestions[0]["confidence"] <= 0.5
        assert logo_suggestions[0]["recommended_action"] == "review"
