"""Context Resolver -- pure relevance scoring over a candidate set of
Knowledge Core items already fetched by the service layer. Scoring is
a plain keyword-match count against title/description/keywords/tags,
case-insensitive -- not TF-IDF, not embeddings, not any learned
weighting. Ties are broken by title for a stable, reproducible order.

A multi-word candidate (e.g. "model registry") matches when every one
of its words appears somewhere in the item's text, not necessarily as
one contiguous phrase -- otherwise "model registry" would never match
an item titled "Model Release Registry", which is exactly the kind of
false negative a deterministic-only matcher must not silently accept.
This is still pure substring counting, not fuzzy/semantic matching: a
word must appear verbatim, just not glued to its neighbors.
"""

from __future__ import annotations

from typing import Any


def _keyword_matches(keyword: str, haystack: str) -> bool:
    words = keyword.lower().split()
    return all(word in haystack for word in words)


def score_items(
    items: list[dict[str, Any]], subject_candidates: list[str],
) -> list[dict[str, Any]]:
    if not subject_candidates:
        return []
    scored = []
    for item in items:
        haystack = " ".join([
            item.get("title", ""), item.get("description", ""),
            " ".join(item.get("keywords", [])), " ".join(item.get("tags", [])),
        ]).lower()
        score = sum(1 for kw in subject_candidates if _keyword_matches(kw, haystack))
        if score > 0:
            scored.append({"item": item, "relevance_score": score, "domain_key": item.get("domain_key")})
    scored.sort(key=lambda entry: (-entry["relevance_score"], entry["item"]["title"]))
    return scored


def build_context(scored_items: list[dict[str, Any]]) -> dict[str, Any]:
    matched_item_titles = [entry["item"]["title"] for entry in scored_items]
    documentation_references = sorted({
        doc for entry in scored_items for doc in entry["item"].get("related_documentation", [])
    })
    return {
        "matched_item_titles": matched_item_titles,
        "documentation_references": documentation_references,
        "matched_item_count": len(matched_item_titles),
    }
