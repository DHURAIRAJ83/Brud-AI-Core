"""Phase 12 Step 15 language and script validation.

Reuses `core_model.corpus.language_detection.assess_language()`
(Tamil/Latin script ratios, Tanglish lexicon hits, numeric/code
detection) and `core_model.corpus.unicode_normalization` (replacement-
character/mojibake/escaped-unicode detection, Tamil combining-mark
preservation) unchanged -- never a second language or Unicode-
integrity implementation.

Never silently corrects ambiguous Tamil text: a deterministic,
always-safe normalization (NFC, zero-width-character removal) may
still be applied to produce a *derived* candidate, but any sign of
OCR-pattern corruption or a broken grapheme cluster in the *original*
text flags `requires_review=True` rather than being auto-corrected
into the record that downstream code trusts.
"""

from __future__ import annotations

import re
from typing import Any

from core_model.corpus.language_detection import assess_language
from core_model.corpus.tamil_normalization import (
    apply_tamil_ocr_substitutions,
    remove_stray_zero_width_characters,
)
from core_model.corpus.unicode_normalization import assess_unicode_integrity

_LANGUAGE_CATEGORY_MAP = {
    "ta": "tamil",
    "en": "english",
    "tgl": "tanglish",
    "mixed": "mixed",
    "unknown": "unknown",
    "numeric": "other",
    "code": "other",
}

# A Tamil vowel sign or virama appearing at the very start of the text
# or immediately after whitespace/punctuation has no preceding base
# consonant to attach to -- a classic broken-grapheme OCR artifact.
_ORPHANED_COMBINING_MARK_PATTERN = re.compile(r"(?:^|[\s.,!?;:\"'()])[ா-்]")


class ExternalDatasetSampleLanguageService:
    def validate(self, text: str) -> dict[str, Any]:
        assessment = assess_language(text)
        language = _LANGUAGE_CATEGORY_MAP.get(assessment["language_category"], "unknown")

        integrity = assess_unicode_integrity(text)
        orphaned_marks = len(_ORPHANED_COMBINING_MARK_PATTERN.findall(text))
        _, ocr_substitution_count = apply_tamil_ocr_substitutions(text)
        _, zero_width_removed_count = remove_stray_zero_width_characters(text)

        review_reasons: list[str] = []
        if integrity["status"] != "valid":
            review_reasons.append(integrity["status"])
        if orphaned_marks > 0:
            review_reasons.append("broken_tamil_grapheme_cluster")
        if ocr_substitution_count > 0:
            review_reasons.append("tamil_ocr_corruption_pattern")

        return {
            "language": language,
            "confidence": assessment["confidence"],
            "tamil_script_ratio": assessment["tamil_script_ratio"],
            "latin_script_ratio": assessment["latin_script_ratio"],
            "tanglish_lexical_evidence": assessment["tanglish_lexical_evidence"],
            "symbol_ratio": assessment["symbol_ratio"],
            "unicode_integrity_status": integrity["status"],
            "replacement_character_count": integrity["replacement_character_count"],
            "mojibake_count": integrity["mojibake_count"],
            "orphaned_combining_mark_count": orphaned_marks,
            "ocr_corruption_signal_count": ocr_substitution_count,
            "zero_width_character_count": zero_width_removed_count,
            "requires_review": bool(review_reasons),
            "review_reasons": review_reasons,
        }
