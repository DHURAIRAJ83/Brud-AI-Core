"""Phase 20 Step 12 -- `WebEvidenceSelectionService`.

Selects only bounded, relevant evidence from already-fetched/verified
Web pages. Excerpts are short and necessary (never the full page body
-- Step 12's own "do not persist or expose large copyrighted content"
rule), and `support_type` is a bounded term-overlap heuristic
(`directly_supports`/`partially_supports`/`background_context`) -- the
fourth value, `contradicts`, is never assigned here; the orchestrator
(`TrustedWebAnswerService`) downgrades a specific item to `contradicts`
only after `detect_conflict()` has identified it as one half of a
genuine numeric/date conflict, keeping "is this evidence relevant" and
"do multiple sources disagree" as two separate, individually testable
concerns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

MAX_EVIDENCE_ITEMS = 5
_WORD_RE = re.compile(r"[a-zA-Z஀-௿]{3,}")
_STOPWORDS = frozenset(
    {"the", "and", "for", "are", "was", "were", "what", "how", "does", "with", "this", "that"}
)


@dataclass(frozen=True)
class EvidenceItem:
    evidence_id: str
    source_url: str
    source_title: str
    supporting_excerpt: str
    support_type: str
    freshness_status: str
    verification_level: str
    source_trust_level: str


def _significant_terms(text: str) -> set[str]:
    return {word.lower() for word in _WORD_RE.findall(text) if word.lower() not in _STOPWORDS}


def _bounded_excerpt(text: str, query_terms: set[str], max_chars: int) -> str:
    text = " ".join(text.split())
    if len(text) <= max_chars:
        return text
    lowered = text.lower()
    best_start = 0
    for term in query_terms:
        idx = lowered.find(term)
        if idx != -1:
            best_start = max(0, idx - max_chars // 4)
            break
    excerpt = text[best_start : best_start + max_chars]
    return excerpt.strip() + ("…" if best_start + max_chars < len(text) else "")


def select_evidence(
    *,
    query: str,
    candidates: list[dict[str, object]],
    max_excerpt_chars: int,
    max_items: int = MAX_EVIDENCE_ITEMS,
) -> list[EvidenceItem]:
    """`candidates` items carry: evidence_id, source_url, source_title,
    text, freshness_status, verification_level, source_trust_level."""

    query_terms = _significant_terms(query)
    scored: list[tuple[float, dict[str, object]]] = []
    for candidate in candidates:
        text = str(candidate["text"])
        terms = _significant_terms(text)
        overlap = len(query_terms & terms)
        ratio = overlap / max(1, len(query_terms))
        scored.append((ratio, candidate))

    scored.sort(key=lambda pair: pair[0], reverse=True)

    selected: list[EvidenceItem] = []
    for ratio, candidate in scored[:max_items]:
        if ratio >= 0.5:
            support_type = "directly_supports"
        elif ratio > 0:
            support_type = "partially_supports"
        else:
            support_type = "background_context"
        text = str(candidate["text"])
        excerpt = _bounded_excerpt(text, query_terms, max_excerpt_chars)
        selected.append(
            EvidenceItem(
                evidence_id=str(candidate["evidence_id"]),
                source_url=str(candidate["source_url"]),
                source_title=str(candidate["source_title"]),
                supporting_excerpt=excerpt,
                support_type=support_type,
                freshness_status=str(candidate["freshness_status"]),
                verification_level=str(candidate["verification_level"]),
                source_trust_level=str(candidate["source_trust_level"]),
            )
        )
    return selected


__all__ = ["EvidenceItem", "MAX_EVIDENCE_ITEMS", "select_evidence"]
