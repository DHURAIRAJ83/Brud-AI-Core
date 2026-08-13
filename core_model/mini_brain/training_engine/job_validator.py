"""MB-22: Job Validator -- pure. Validates the two hard prerequisites
the task spec's own Steps 2-3 require: the linked MB-20 release-
governance session must be admin_approved, and the linked MB-18
training package session must itself be admin_approved with a real,
non-empty built package. Neither function ever fetches these sessions
itself -- the service layer does that and passes the already-fetched
dicts in.
"""

from __future__ import annotations

from typing import Any


def validate_release_approval(*, release_session: dict[str, Any] | None) -> dict[str, Any]:
    if release_session is None:
        return {"valid": False, "reason": "no MB-20 release-governance session was supplied", "session_public_id": None}
    approved = release_session.get("status") == "admin_approved"
    return {
        "valid": approved, "session_public_id": release_session["public_id"] if approved else None,
        "reason": None if approved else f"MB-20 session status is '{release_session.get('status')}', not 'admin_approved'",
        "disclosure": "only an MB-20 release-governance session that is admin_approved is ever accepted",
    }


def validate_training_package(*, package_session: dict[str, Any] | None) -> dict[str, Any]:
    if package_session is None:
        return {"valid": False, "reason": "no MB-18 training package session was supplied", "session_public_id": None}
    approved = (
        package_session.get("status") == "admin_approved"
        and bool(package_session.get("package_directory"))
        and package_session.get("package_manifest", {}).get("artifact_count", 0) > 0
    )
    return {
        "valid": approved, "session_public_id": package_session["public_id"] if approved else None,
        "reason": None if approved else "MB-18 session is not admin_approved with a real, non-empty built package",
        "disclosure": "only an MB-18 session that is admin_approved with a real, non-empty built package is ever accepted",
    }
