"""Phase 19 Step 31 -- ambiguity supplemental pattern registry: closes
the Phase 18 spec's own "அதை apply செய்" mixed Tamil-English
unclear-pronoun gap, without classifying every mixed-language request
as ambiguous or touching Phase 17's sealed policy."""

import pytest

from core_model.public_chat.ambiguity_supplemental_patterns import (
    SUPPLEMENTAL_AMBIGUITY_PATTERNS_CHECKSUM_SHA256,
    SUPPLEMENTAL_AMBIGUITY_PATTERNS_VERSION,
    evaluate_supplemental_ambiguity,
)

POSITIVE_CASES = (
    "அதை apply செய்",
    "இதை check பண்ணு",
    "athai apply seiyunga",
    "idhai check pannunga",
)

NEGATIVE_CASES = (
    "இந்த ஆவணத்தை apply செய்",  # names its subject -- not ambiguous
    "தமிழில் பெயர்ச்சொல் என்றால் என்ன?",  # normal Tamil question
    "what is the latest python version",  # plain English
    "Python latest stable version என்ன?",  # mixed but unambiguous
    "987654 × 12345 எவ்வளவு?",  # mixed, clear calculation request
    "how do I apply for a passport",  # English, unambiguous
    "இந்த படிவத்தை எப்படி நிரப்புவது",  # pure Tamil, names its subject
)


def test_version_and_checksum_are_stable_strings() -> None:
    assert SUPPLEMENTAL_AMBIGUITY_PATTERNS_VERSION == "v1"
    assert len(SUPPLEMENTAL_AMBIGUITY_PATTERNS_CHECKSUM_SHA256) == 64


@pytest.mark.parametrize("text", POSITIVE_CASES)
def test_known_unclear_pronoun_phrasings_are_matched(text: str) -> None:
    result = evaluate_supplemental_ambiguity(text)
    assert result.matched is True
    assert result.reason_code == "AMBIGUOUS_MIXED_LANGUAGE_UNCLEAR_PRONOUN_SUPPLEMENTAL"


@pytest.mark.parametrize("text", NEGATIVE_CASES)
def test_unambiguous_mixed_or_single_language_requests_are_never_matched(text: str) -> None:
    result = evaluate_supplemental_ambiguity(text)
    assert result.matched is False


def test_not_every_mixed_language_request_is_classified_ambiguous() -> None:
    """Explicit regression for the spec's own invariant: mixed-language
    input alone must never be sufficient to trigger this pattern."""

    mixed_but_clear = [
        "Python latest stable version என்ன?",
        "987654 × 12345 எவ்வளவு?",
        "இந்த ஆவணத்தை apply செய்",
    ]
    for text in mixed_but_clear:
        assert evaluate_supplemental_ambiguity(text).matched is False
