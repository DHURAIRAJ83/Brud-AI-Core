"""Deterministic language routing: script rules plus a bounded, explicit
Tanglish lexicon — never an external language-detection service.
Tanglish (Latin-script Tamil-in-transliteration) is always its own
category, never folded into English merely because it shares a script.
"""

from __future__ import annotations

from core_model.instruction_tuning.language_checks import script_ratios
from core_model.rag import LANGUAGE_CATEGORIES

DEFAULT_TANGLISH_LEXICON = frozenset(
    {
        "vanakkam", "eppadi", "epdi", "irukku", "irukkeenga", "nalla", "seri",
        "enna", "romba", "nanba", "sapadu", "sapteengala", "poren", "varen",
        "aama", "illa", "konjam", "vera", "semma", "yaaru", "eppo", "enga",
        "vandhu", "sollu", "sonna", "theriyum", "venum", "dhaan", "unga",
        "unakku", "namma", "ipo",
    }
)


def classify_language(
    text: str,
    *,
    tanglish_lexicon: frozenset[str] = DEFAULT_TANGLISH_LEXICON,
    min_script_ratio: float = 0.15,
) -> dict[str, object]:
    ratios = script_ratios(text)
    tamil_present = ratios["tamil_script_ratio"] >= min_script_ratio
    latin_present = ratios["latin_script_ratio"] >= min_script_ratio
    tokens = {token.lower().strip(".,!?;:\"'()") for token in text.split()}
    tanglish_hits = sorted(tokens & tanglish_lexicon)

    if not tamil_present and not latin_present:
        category = "unknown"
    elif tamil_present and latin_present:
        category = "mixed"
    elif tamil_present:
        category = "ta"
    else:
        category = "tgl" if tanglish_hits else "en"

    assert category in LANGUAGE_CATEGORIES
    return {
        "language_category": category,
        "tamil_script_ratio": ratios["tamil_script_ratio"],
        "latin_script_ratio": ratios["latin_script_ratio"],
        "tanglish_lexicon_hits": tanglish_hits,
    }


def routing_decision(language_category: str) -> dict[str, object]:
    """Describes what language routing should influence downstream — alias
    expansion, embedding model selection, keyword tokenization, reranking
    weights, answer-language policy — without applying any of it itself."""

    return {
        "language_category": language_category,
        "apply_tanglish_aliases": language_category in {"tgl", "mixed"},
        "answer_language_policy": (
            language_category if language_category != "unknown" else "en"
        ),
    }
