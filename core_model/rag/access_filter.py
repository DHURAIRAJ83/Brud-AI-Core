"""Deterministic pre-retrieval access/source/licence filtering.

Filtering happens BEFORE scoring and context assembly — a blocked or
inaccessible chunk is excluded from the candidate pool entirely, never
merely hidden from citations after being scored and selected.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RetrievalFilters:
    source_public_ids: tuple[str, ...] = ()
    source_version_public_ids: tuple[str, ...] = ()
    dataset_version_public_ids: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    record_types: tuple[str, ...] = ()
    licence_statuses: tuple[str, ...] = ()
    approval_statuses: tuple[str, ...] = ("approved",)
    created_after: str | None = None
    created_before: str | None = None
    access_level: str | None = None


def candidate_is_accessible(
    candidate: dict[str, Any], filters: RetrievalFilters, *, require_approved_sources: bool
) -> tuple[bool, str | None]:
    """Returns ``(accessible, exclusion_reason)``. A blocked/rejected/
    quarantined/draft source is excluded whenever ``require_approved_sources``
    is True, regardless of any other filter passed in."""

    if require_approved_sources and candidate.get("approval_status") != "approved":
        return False, "source_not_approved"
    if candidate.get("licence_status") == "blocked":
        return False, "licence_blocked"
    if (
        filters.approval_statuses
        and candidate.get("approval_status") not in filters.approval_statuses
    ):
        return False, "approval_status_excluded"
    if (
        filters.licence_statuses
        and candidate.get("licence_status") not in filters.licence_statuses
    ):
        return False, "licence_status_excluded"
    if (
        filters.source_public_ids
        and candidate.get("source_public_id") not in filters.source_public_ids
    ):
        return False, "source_excluded"
    if (
        filters.source_version_public_ids
        and candidate.get("source_version_public_id") not in filters.source_version_public_ids
    ):
        return False, "source_version_excluded"
    if filters.languages and candidate.get("language") not in filters.languages:
        return False, "language_excluded"
    if filters.record_types and candidate.get("record_type") not in filters.record_types:
        return False, "record_type_excluded"
    if filters.created_after and candidate.get("created_at", "") < filters.created_after:
        return False, "created_before_range"
    if filters.created_before and candidate.get("created_at", "") > filters.created_before:
        return False, "created_after_range"
    if filters.access_level and candidate.get("access_level") not in (None, filters.access_level):
        return False, "access_level_excluded"
    return True, None


def apply_access_filters(
    candidates: list[dict[str, Any]], filters: RetrievalFilters, *, require_approved_sources: bool
) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for candidate in candidates:
        ok, reason = candidate_is_accessible(
            candidate, filters, require_approved_sources=require_approved_sources
        )
        if ok:
            accepted.append(candidate)
        else:
            excluded.append({**candidate, "exclusion_reason": reason})
    return {"accepted": accepted, "excluded": excluded}
