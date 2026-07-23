"""Fixed, versioned, hand-composed instruction evaluation fixtures.

Every fixture is (prompt_text, expected_language, format_category). There is
never a model-generated "expected answer" here — ground truth for these
deterministic checks is structural (language, format), not a literal string
to match.
"""

from __future__ import annotations

FIXTURE_VERSION = "phase12-instruction-eval-v1"

# (prompt_text, expected_language, format_category)
TAMIL_FIXTURES = (
    ("தமிழில் பதிலளிக்கவும்: நீங்கள் யார்?", "ta", "answer_in_language"),
    ("சுருக்கமாக விளக்குங்கள்: மழை ஏன் பெய்கிறது?", "ta", "short_explanation"),
    ("வரையறு: நூலகம் என்றால் என்ன?", "ta", "definition"),
    ("இந்த வாக்கியத்தை கேள்வியாக மாற்றவும்: இன்று மழை பெய்கிறது.", "ta", "simple_transformation"),
    ("எண்களை தமிழில் எழுதவும்: 1, 2, 3.", "ta", "punctuation_and_numerals"),
)

ENGLISH_FIXTURES = (
    ("Say hello in one short sentence.", "en", "simple_instruction"),
    ("List two colors, one per line.", "en", "short_structured_answer"),
)

TANGLISH_FIXTURES = (
    ("Naanga eppadi irukom nu tamil la sollu.", "tgl", "requested_tamil_answer"),
    (
        "Ungaluku tamil theriyuma? tanglish la reply pannunga.",
        "tgl", "requested_tanglish_answer",
    ),
    (
        "Vanakkam nu ithu correct spelling thana? confirm pannunga.",
        "tgl", "common_spelling_variant",
    ),
)

MIXED_FIXTURES = (
    ("இந்த laptop-ஐ எப்படி configure பண்ணுவது?", "mixed", "technical_terms_in_tamil_question"),
    ("தமிழில் பதில் சொல்லுங்கள், ஆங்கிலம் வேண்டாம்.", "mixed", "language_preservation_request"),
)

FORMAT_FIXTURES = (
    (
        "Answer in exactly one line: what is the capital concept of gravity?",
        "en", "one_line_answer",
    ),
    ("List three fruits as a numbered list.", "en", "numbered_response"),
    ("Translate 'thank you' into Tamil.", "en", "translation_direction"),
)


def all_fixtures() -> dict[str, tuple[tuple[str, str, str], ...]]:
    return {
        "ta": TAMIL_FIXTURES,
        "en": ENGLISH_FIXTURES + FORMAT_FIXTURES,
        "tgl": TANGLISH_FIXTURES,
        "mixed": MIXED_FIXTURES,
    }
