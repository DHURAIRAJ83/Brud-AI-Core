"""Memory access filtering -- applied BEFORE ranking, never after.

Never retrieves: another participant's memory, deleted memory, revoked
memory, expired memory, awaiting-confirmation memory, unconfirmed
assistant-inferred memory, or blocked memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

_RETRIEVABLE_STATUSES = {"active"}


@dataclass(frozen=True)
class MemoryRetrievalFilters:
    participant_scope_key: str
    allowed_categories: tuple[str, ...] = ()
    allowed_purposes: tuple[str, ...] = ()
    now_epoch: float = 0.0


def candidate_is_retrievable(
    candidate: dict[str, Any], filters: MemoryRetrievalFilters
) -> tuple[bool, str | None]:
    if candidate["participant_scope_key"] != filters.participant_scope_key:
        return False, "cross_participant_denied"
    if candidate["status"] not in _RETRIEVABLE_STATUSES:
        return False, f"status_{candidate['status']}_excluded"
    if candidate.get("confidence_type") == "assistant_inferred" and not candidate.get("confirmed"):
        return False, "unconfirmed_assistant_inferred"
    if filters.allowed_categories and candidate["category"] not in filters.allowed_categories:
        return False, "category_not_in_profile"
    if filters.allowed_purposes and candidate["purpose"] not in filters.allowed_purposes:
        return False, "purpose_not_in_profile"
    expires_at_epoch = candidate.get("expires_at_epoch")
    if expires_at_epoch is not None and expires_at_epoch <= filters.now_epoch:
        return False, "expired"
    valid_from_epoch = candidate.get("valid_from_epoch")
    if valid_from_epoch is not None and valid_from_epoch > filters.now_epoch:
        return False, "not_yet_valid"
    return True, None


def apply_access_filters(
    candidates: list[dict[str, Any]], filters: MemoryRetrievalFilters
) -> dict[str, list[dict[str, Any]]]:
    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for candidate in candidates:
        ok, reason = candidate_is_retrievable(candidate, filters)
        if ok:
            accepted.append(candidate)
        else:
            excluded.append({**candidate, "exclusion_reason": reason})
    return {"accepted": accepted, "excluded": excluded}
