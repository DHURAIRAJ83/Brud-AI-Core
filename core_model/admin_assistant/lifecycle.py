"""Pure derived-state mapping for Admin Assistant proposals (Phase 8).

`admin_approvals.status` keeps its original 5-value CHECK constraint
(`pending, approved, rejected, cancelled, expired`) unchanged -- this
module computes Phase 8's richer conceptual lifecycle from that column
plus `execution_status` and `expires_at`, entirely at read time.
Nothing here is stored, so a lifecycle state can never drift from the
columns that are actually the source of truth.

Since a proposal's preview/stale-check snapshot is always generated
synchronously inside `AdminAssistantService.propose()` (there is no
separate "draft, then generate preview later" step), the conceptual
`draft` and `preview_ready` states described in the task collapse into
one real state: `awaiting_confirmation`.
"""

from __future__ import annotations

from datetime import datetime

LIFECYCLE_STATES = (
    "awaiting_confirmation",
    "confirmed",
    "executing",
    "completed",
    "failed",
    "cancelled",
    "expired",
    "rejected",
)


def derive_lifecycle_state(
    *,
    status: str,
    execution_status: str,
    expires_at: datetime | None,
    now: datetime,
) -> str:
    if status == "pending":
        if expires_at is not None and now >= expires_at:
            return "expired"
        return "awaiting_confirmation"
    if status == "rejected":
        return "rejected"
    if status == "cancelled":
        return "cancelled"
    if status == "expired":
        return "expired"
    if status == "approved":
        if execution_status == "succeeded":
            return "completed"
        if execution_status == "failed":
            return "failed"
        if execution_status == "pending":
            return "executing"
        return "confirmed"
    return "unknown"
