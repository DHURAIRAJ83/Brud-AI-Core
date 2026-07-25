"""Tokenizer-training corpus sufficiency analysis -- pure functions
only. Reuses Phase 11's own Tamil/Latin script detection patterns
rather than redefining them."""

from __future__ import annotations

import string
from dataclasses import dataclass
from typing import Any

from core_model.training.dataset_profile import LATIN_PATTERN, TAMIL_PATTERN

SUFFICIENCY_STATES = ("insufficient", "experimental", "candidate", "production_candidate")

_DIGIT_CHARACTERS = set(string.digits)
_PUNCTUATION_CHARACTERS = set(string.punctuation) | set("।॥௳௴௵௶௷௸௺")


@dataclass(frozen=True)
class SufficiencyThresholds:
    """Configurable, transparent thresholds -- never hardcoded inline
    so a tiny verification corpus can never be silently classified as
    production-ready by accident."""

    experimental_min_characters: int = 20_000
    experimental_min_records: int = 50
    candidate_min_characters: int = 500_000
    candidate_min_records: int = 2_000
    production_min_characters: int = 20_000_000
    production_min_records: int = 100_000
    minimum_script_diversity_categories: int = 2


DEFAULT_SUFFICIENCY_THRESHOLDS = SufficiencyThresholds()


def character_category_counts(text: str) -> dict[str, int]:
    tamil = len(TAMIL_PATTERN.findall(text))
    english = len(LATIN_PATTERN.findall(text))
    digits = sum(1 for ch in text if ch in _DIGIT_CHARACTERS)
    punctuation = sum(1 for ch in text if ch in _PUNCTUATION_CHARACTERS)
    return {"tamil": tamil, "english": english, "digits": digits, "punctuation": punctuation}


def classify_sufficiency(
    *,
    total_characters: int,
    total_records: int,
    script_categories_present: int,
    thresholds: SufficiencyThresholds = DEFAULT_SUFFICIENCY_THRESHOLDS,
) -> str:
    """Never claims `production_candidate` from a tiny corpus -- every
    threshold is explicit and configurable, and script diversity is a
    hard requirement alongside raw size."""

    if script_categories_present < thresholds.minimum_script_diversity_categories:
        return "insufficient"
    if (
        total_characters >= thresholds.production_min_characters
        and total_records >= thresholds.production_min_records
    ):
        return "production_candidate"
    if (
        total_characters >= thresholds.candidate_min_characters
        and total_records >= thresholds.candidate_min_records
    ):
        return "candidate"
    if (
        total_characters >= thresholds.experimental_min_characters
        and total_records >= thresholds.experimental_min_records
    ):
        return "experimental"
    return "insufficient"


def build_sufficiency_report(
    records: list[dict[str, Any]],
    *,
    thresholds: SufficiencyThresholds = DEFAULT_SUFFICIENCY_THRESHOLDS,
) -> dict[str, Any]:
    """``records`` is a list of ``{"text": str, "language_category": str,
    "domain": str, "style": str, "source": str, "licence_family": str}``
    rows already filtered to eligible content by the caller -- this
    function never applies eligibility rules itself, only reports on
    what it is given."""

    total_characters = 0
    total_utf8_bytes = 0
    total_words = 0
    unique_characters: set[str] = set()
    tamil_characters = 0
    english_characters = 0
    digit_count = 0
    punctuation_count = 0
    script_counts: dict[str, int] = {}
    domain_distribution: dict[str, int] = {}
    style_distribution: dict[str, int] = {}
    source_distribution: dict[str, int] = {}
    licence_distribution: dict[str, int] = {}

    for record in records:
        text = record.get("text", "")
        total_characters += len(text)
        total_utf8_bytes += len(text.encode("utf-8"))
        total_words += len(text.split())
        unique_characters.update(text)
        categories = character_category_counts(text)
        tamil_characters += categories["tamil"]
        english_characters += categories["english"]
        digit_count += categories["digits"]
        punctuation_count += categories["punctuation"]
        # Real Phase 19/20 language-category classification (ta/en/tgl/
        # mixed/...), not re-derived from Unicode script ranges alone --
        # script ranges cannot distinguish Tanglish (Latin-script Tamil)
        # from genuine English.
        language_category = record.get("language_category", "unknown")
        script_counts[language_category] = script_counts.get(language_category, 0) + 1
        for key, distribution in (
            ("domain", domain_distribution),
            ("style", style_distribution),
            ("source", source_distribution),
            ("licence_family", licence_distribution),
        ):
            value = record.get(key, "unknown")
            distribution[value] = distribution.get(value, 0) + 1

    script_categories_present = sum(
        1 for key in ("ta", "en", "tgl", "mixed") if script_counts.get(key, 0) > 0
    )
    sufficiency_state = classify_sufficiency(
        total_characters=total_characters,
        total_records=len(records),
        script_categories_present=script_categories_present,
        thresholds=thresholds,
    )
    return {
        "total_records": len(records),
        "total_characters": total_characters,
        "total_utf8_bytes": total_utf8_bytes,
        "total_words": total_words,
        "unique_character_count": len(unique_characters),
        "tamil_character_count": tamil_characters,
        "english_character_count": english_characters,
        "digit_count": digit_count,
        "punctuation_count": punctuation_count,
        "tamil_only_record_count": script_counts.get("ta", 0),
        "english_only_record_count": script_counts.get("en", 0),
        "tanglish_record_count": script_counts.get("tgl", 0),
        "mixed_record_count": script_counts.get("mixed", 0),
        "language_distribution": script_counts,
        "domain_distribution": domain_distribution,
        "style_distribution": style_distribution,
        "source_distribution": source_distribution,
        "licence_distribution": licence_distribution,
        "sufficiency_state": sufficiency_state,
    }
