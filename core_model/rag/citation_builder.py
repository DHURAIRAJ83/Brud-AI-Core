"""Deterministic citation-map construction and answer-citation parsing.

Citations are built from retrieval evidence, never invented by the
model. The model may only reference citation IDs that were placed in
its own context; any other referenced ID is rejected, never resolved
heuristically to an unrelated chunk.
"""

from __future__ import annotations

import re
from typing import Any

_CITATION_REFERENCE_PATTERN = re.compile(r"\[?S(\d+)\]?")


def build_citation_map(selected_chunks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """``selected_chunks`` already rank-ordered. Returns ``{"S1": {...}, ...}``."""

    citation_map: dict[str, dict[str, Any]] = {}
    for index, chunk in enumerate(selected_chunks, start=1):
        label = f"S{index}"
        citation_map[label] = {
            "citation_label": label,
            "chunk_public_id": chunk["chunk_public_id"],
            "source_public_id": chunk["source_public_id"],
            "source_version_public_id": chunk["source_version_public_id"],
            "title": chunk.get("title", ""),
            "location": chunk.get("location", ""),
            "rank": chunk.get("rank", index),
            "content_checksum_sha256": chunk.get("content_checksum_sha256", ""),
        }
    return citation_map


def extract_cited_labels(answer_text: str) -> list[str]:
    """Deterministic parse of ``S1``/``[S1]``-style references from
    generated text, in order of first appearance, duplicates removed."""

    seen: list[str] = []
    for match in _CITATION_REFERENCE_PATTERN.finditer(answer_text):
        label = f"S{match.group(1)}"
        if label not in seen:
            seen.append(label)
    return seen


def resolve_citations(
    cited_labels: list[str], citation_map: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Returns ``{"resolved": [...], "unknown_labels": [...]}``. Never
    heuristically resolves an unknown label to an unrelated chunk."""

    resolved: list[dict[str, Any]] = []
    unknown: list[str] = []
    for label in cited_labels:
        entry = citation_map.get(label)
        if entry is None:
            unknown.append(label)
        else:
            resolved.append(entry)
    return {"resolved": resolved, "unknown_labels": unknown}
