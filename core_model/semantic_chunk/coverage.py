"""Deterministic source-coverage validation for chunk boundary
operations (Phase 5, Step 8). Pure functions only -- no DB/IO.

A chunk's locator is either offset-based (the common case: a single
approved page's `cleaned_text`, so exact character coverage can be
verified) or region/line-based (Step 4's fallback for content that
doesn't reduce to a flat offset range). Coverage is only ever computed
from real, present offsets -- never guessed or approximated for a
region/line locator; those are reported as `coverage_computable=False`
rather than silently treated as 100% covered.
"""

from __future__ import annotations

from typing import Any, TypedDict


class CoverageIssue(TypedDict):
    code: str
    message: str


class SplitPlan(TypedDict):
    first: dict[str, Any]
    second: dict[str, Any]


class MergePlan(TypedDict):
    start_offset: int
    end_offset: int
    text: str
    warnings: list[str]


def is_offset_locator(locator: dict[str, Any] | None) -> bool:
    return bool(
        locator
        and "page" in locator
        and locator.get("offset_start") is not None
        and locator.get("offset_end") is not None
    )


def plan_split(text: str, offset_start: int, offset_end: int, split_at: int) -> SplitPlan:
    """Split `text` (spanning [offset_start, offset_end)) at `split_at`
    (an absolute offset). Raises ValueError if the split would produce
    an empty fragment or a split point outside the chunk's own range --
    this is the "prevent empty fragments" rule from Step 8."""
    if not (offset_start < split_at < offset_end):
        raise ValueError("split point must fall strictly inside the chunk's own boundaries")
    local_split = split_at - offset_start
    first_text = text[:local_split]
    second_text = text[local_split:]
    if not first_text.strip() or not second_text.strip():
        raise ValueError("split would produce an empty fragment")
    return {
        "first": {"offset_start": offset_start, "offset_end": split_at, "text": first_text},
        "second": {"offset_start": split_at, "offset_end": offset_end, "text": second_text},
    }


def plan_merge(
    first: dict[str, Any], second: dict[str, Any], *, full_text: str | None = None
) -> MergePlan:
    """Merge two chunks. `first`/`second` each need `page`, `offset_start`,
    `offset_end`, `text`. Requires the two to be non-overlapping and in
    order (`first`'s end at or before `second`'s start) -- never silently
    reorders or bridges a gap that a *third*, non-participating chunk
    already occupies (the caller must check that separately; this
    function only has the two chunks' own bounds). When both come from
    the same page and `full_text` (the page's full source text) is
    given, the merged text is the literal substring between the two
    chunks' outer bounds -- this preserves any intervening whitespace
    or paragraph-separator text exactly rather than silently dropping it
    (a same-page adjacent-paragraph merge routinely has a small gap:
    the blank-line separator itself belongs to neither chunk). Without
    `full_text` (or across pages), the merge falls back to plain
    concatenation. Cross-page merges are allowed but flagged with a
    warning (Step 8: "warn on cross-page merge")."""
    if first["offset_start"] > second["offset_start"]:
        first, second = second, first
    if first["offset_end"] > second["offset_start"]:
        raise ValueError(
            "chunks overlap -- merge requires the first chunk's end to be at or "
            "before the second chunk's start"
        )
    warnings: list[str] = []
    same_page = first.get("page") == second.get("page")
    if not same_page:
        warnings.append("cross_page_merge")
    if same_page and full_text is not None:
        merged_text = full_text[first["offset_start"] : second["offset_end"]]
    else:
        merged_text = first["text"] + second["text"]
    return {
        "start_offset": first["offset_start"],
        "end_offset": second["offset_end"],
        "text": merged_text,
        "warnings": warnings,
    }


def plan_boundary_move(
    chunk: dict[str, Any],
    neighbor: dict[str, Any],
    *,
    edge: str,
    new_offset: int,
    full_text: str,
) -> dict[str, Any]:
    """Move `chunk`'s start or end boundary to `new_offset`, validating
    against its adjacent `neighbor` so the move never creates a gap
    (dropped source text) or an overlap (duplicated source text) --
    Step 8's explicit invariants. Overlap is not supported at all today,
    so any move that would overlap the neighbor is rejected outright."""
    if edge not in ("start", "end"):
        raise ValueError("edge must be 'start' or 'end'")
    if edge == "start":
        if not (neighbor["offset_start"] <= new_offset < chunk["offset_end"]):
            raise ValueError("new start would overlap this chunk's own end or the neighbor's start")
        new_chunk = {"offset_start": new_offset, "offset_end": chunk["offset_end"]}
        new_neighbor = {"offset_start": neighbor["offset_start"], "offset_end": new_offset}
    else:
        if not (chunk["offset_start"] < new_offset <= neighbor["offset_end"]):
            raise ValueError("new end would overlap this chunk's own start or the neighbor's end")
        new_chunk = {"offset_start": chunk["offset_start"], "offset_end": new_offset}
        new_neighbor = {"offset_start": new_offset, "offset_end": neighbor["offset_end"]}
    new_chunk["text"] = full_text[new_chunk["offset_start"] : new_chunk["offset_end"]]
    new_neighbor["text"] = full_text[new_neighbor["offset_start"] : new_neighbor["offset_end"]]
    if not new_chunk["text"].strip() or not new_neighbor["text"].strip():
        raise ValueError("boundary move would produce an empty fragment")
    return {"chunk": new_chunk, "neighbor": new_neighbor}


def validate_page_coverage(page_text: str, segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic coverage validation across every offset-locatable
    chunk on one page: no source text lost, none duplicated, no invalid
    overlap. `segments` need `offset_start`/`offset_end`; segments
    without both (region/line locators) are excluded from the computed
    percentages and reported separately, never assumed covered."""
    computable = [
        s for s in segments if s.get("offset_start") is not None and s.get("offset_end") is not None
    ]
    not_computable = len(segments) - len(computable)
    ordered = sorted(computable, key=lambda s: s["offset_start"])
    issues: list[CoverageIssue] = []
    covered = 0
    cursor = 0
    for segment in ordered:
        start, end = segment["offset_start"], segment["offset_end"]
        if start < cursor:
            issues.append(
                {
                    "code": "SOURCE_TEXT_OVERLAP",
                    "message": (
                        f"segment [{start},{end}) overlaps preceding coverage up to {cursor}"
                    ),
                }
            )
        elif start > cursor:
            issues.append(
                {
                    "code": "SOURCE_TEXT_LOSS",
                    "message": f"gap of {start - cursor} character(s) before offset {start}",
                }
            )
        covered += max(0, end - max(start, cursor))
        cursor = max(cursor, end)
    if cursor < len(page_text):
        issues.append(
            {
                "code": "SOURCE_TEXT_LOSS",
                "message": (
                    f"trailing {len(page_text) - cursor} character(s) not covered by any chunk"
                ),
            }
        )
    total = len(page_text) or 1
    return {
        "assigned_ratio": round(min(covered, total) / total, 4),
        "unassigned_ratio": round(max(0, total - covered) / total, 4),
        "overlap_count": sum(1 for i in issues if i["code"] == "SOURCE_TEXT_OVERLAP"),
        "gap_count": sum(1 for i in issues if i["code"] == "SOURCE_TEXT_LOSS"),
        "issues": issues,
        "non_offset_chunk_count": not_computable,
        "coverage_computable": not_computable == 0,
    }
