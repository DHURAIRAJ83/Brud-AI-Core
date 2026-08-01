"""Phase 19 Step 7 -- deterministic canonical-question generation.

Wraps `core_model.rag.query_normalization.normalize_query()` verbatim
(NFC unicode -> whitespace collapse -> punctuation normalize -> Latin-
only lowercase -> Tanglish/technical-term alias expansion). No
semantic rewriting, no translation, no volatile-entity substitution --
"latest Python version" and "Python version means what" must stay
distinguishable after this step; only `KnowledgeGapClusteringService`'s
domain/intent-bucketed similarity pass decides whether two canonical
questions describe the same case, never keyword overlap alone.
"""

from __future__ import annotations

from dataclasses import dataclass

from core_model.rag.query_normalization import QueryNormalizationConfig, normalize_query

# A small, versioned set of Tanglish tokens the existing alias-map
# mechanism already supports -- reused, not a new normalization
# strategy. Kept intentionally short: only common Tanglish spellings
# that would otherwise fragment an identical Tamil-script question.
_TANGLISH_ALIASES = {
    "enna": "என்ன",
    "eppadi": "எப்படி",
    "epdi": "எப்படி",
    "na": "என்றால்",
    "sollu": "சொல்லு",
    "vendum": "வேண்டும்",
}

_CONFIG = QueryNormalizationConfig(lowercase_latin=True, tanglish_aliases=_TANGLISH_ALIASES)


@dataclass(frozen=True)
class CanonicalResult:
    canonical_question: str
    normalization_version: str
    applied_transformations: tuple[str, ...]


class KnowledgeGapCanonicalizationService:
    def canonicalize(self, redacted_text: str, *, language_category: str) -> CanonicalResult:
        result = normalize_query(redacted_text, language_category=language_category, config=_CONFIG)
        return CanonicalResult(
            canonical_question=str(result["normalized_query"]),
            normalization_version=str(result["normalization_version"]),
            applied_transformations=tuple(result["applied_transformations"]),  # type: ignore[arg-type]
        )


__all__ = ["CanonicalResult", "KnowledgeGapCanonicalizationService"]
