"""MB-04A: deterministic language detection -- Tamil / English /
Tanglish / Mixed. No AI, no model call, no external library: purely
Unicode-range counting (Tamil script is U+0B80-U+0BFF) plus a fixed
keyword list of common Tanglish (Latin-script Tamil) words.

This is a rule-based signal, not a linguistic classifier -- the
Tanglish keyword list is necessarily incomplete (see module docstring
in the MB-04A report for the honestly-disclosed coverage limits).
"""

from __future__ import annotations

import re
from typing import Any

_TAMIL_RANGE = (0x0B80, 0x0BFF)

# A deliberately practical, not exhaustive, set of common
# Latin-script Tamil (Tanglish) words -- everyday connectors plus
# Brud-domain vocabulary likely to appear in Admin questions.
TANGLISH_SIGNAL_WORDS = frozenset({
    "epadi", "eppadi", "pannalam", "pannunga", "panren", "panra", "pannanum",
    "pannuvom", "panniten", "venum", "vendum", "vendaam", "venaam",
    "irukku", "irukka", "irukkanum", "iruku", "illa", "illai", "illainu",
    "seyya", "seiya", "seiyanum", "sollunga", "sollu", "solra", "kudu",
    "kudukka", "kudunga", "edhu", "yedhu", "enna", "yenna", "ippo", "ippove",
    "apparam", "appuram", "mattum", "matum", "ellam", "ellaam", "romba",
    "rompa", "nalla", "korachu", "konjam", "kunjam", "thevai",
    "thevaiya", "mudiyuma", "mudiyum", "mudiyala", "epo", "evlo", "evalo",
    "yaaru", "yaru", "enga", "engeyum", "epadiya", "seri", "sari", "aama",
    "aamam", "illainga", "vaanga", "poga", "pogalam", "paaru", "paakalam",
    "theriyuma", "theriyum", "puriyuthu", "puriyala",
})

_WORD_RE = re.compile(r"[A-Za-z']+")

TAMIL_DOMINANCE_THRESHOLD = 0.6
MIXED_DOMINANCE_SPLIT = 0.5


def _tamil_char_count(text: str) -> int:
    lo, hi = _TAMIL_RANGE
    return sum(1 for ch in text if lo <= ord(ch) <= hi)


def _latin_char_count(text: str) -> int:
    return sum(1 for ch in text if ch.isalpha() and ch.isascii())


def _tanglish_signal_words(text: str) -> list[str]:
    words = {w.lower() for w in _WORD_RE.findall(text)}
    return sorted(words & TANGLISH_SIGNAL_WORDS)


def detect_language(text: str) -> dict[str, Any]:
    """Returns a full analysis dict -- never just a label -- so
    downstream callers (and tests, and the report) can see exactly
    why a classification was made."""

    tamil_chars = _tamil_char_count(text)
    latin_chars = _latin_char_count(text)
    total_alpha = tamil_chars + latin_chars
    tamil_ratio = (tamil_chars / total_alpha) if total_alpha else 0.0
    tanglish_words = _tanglish_signal_words(text)

    # Tanglish words are Tamil-language content spelled in Latin
    # script -- counting only raw Tamil-Unicode characters would
    # undercount true Tamil-language dominance in a mixed sentence
    # that leans heavily Tanglish. effective_tamil_ratio folds each
    # matched Tanglish word's own letter-count in as Tamil-language
    # weight, purely by counting characters -- still zero NLP/AI.
    tanglish_char_weight = sum(len(w) for w in tanglish_words)
    effective_tamil_ratio = (
        (tamil_chars + tanglish_char_weight) / total_alpha if total_alpha else 0.0
    )

    if total_alpha == 0:
        language = "english"
    elif tamil_ratio >= TAMIL_DOMINANCE_THRESHOLD:
        language = "tamil"
    elif tamil_ratio > 0:
        language = "mixed"
    else:
        language = "tanglish" if tanglish_words else "english"

    return {
        "language": language,
        "tamil_char_count": tamil_chars,
        "latin_char_count": latin_chars,
        "tamil_ratio": round(tamil_ratio, 3),
        "effective_tamil_ratio": round(min(effective_tamil_ratio, 1.0), 3),
        "tanglish_signal_words": tanglish_words,
    }


def resolve_output_language(analysis: dict[str, Any]) -> str:
    """Collapses the 4-way detection into the 2 languages the model
    can actually be asked to answer in: "tamil" or "english".

    Tamil input -> Tamil. Tanglish input -> Tamil (per MB-04A spec).
    English input -> English. Mixed input -> whichever script is more
    represented (>50% split on the same tamil_ratio signal)."""

    language = analysis["language"]
    if language == "tamil" or language == "tanglish":
        return "tamil"
    if language == "english":
        return "english"
    # mixed -- dominance is decided on effective_tamil_ratio (Tamil
    # script + Tanglish-word weight), not raw script ratio alone.
    return "tamil" if analysis["effective_tamil_ratio"] > MIXED_DOMINANCE_SPLIT else "english"
