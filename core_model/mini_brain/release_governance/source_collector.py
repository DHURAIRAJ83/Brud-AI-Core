"""MB-20: Source Collector -- pure. Stages 2-5 of the workflow all live
here since each is a "validate and summarize an already-fetched
upstream session" concern. Never assumes a session is usable -- each
function only accepts the upstream phase's own final, certified state.
"""

from __future__ import annotations

from typing import Any


def collect_dataset_evidence(*, dataset_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [s for s in dataset_sessions if s["status"] == "admin_approved"]
    rejected = [s["public_id"] for s in dataset_sessions if s["status"] != "admin_approved"]
    return {
        "accepted_session_public_ids": [s["public_id"] for s in accepted],
        "rejected_session_public_ids": rejected,
        "accepted_count": len(accepted), "rejected_count": len(rejected),
        "ready": len(accepted) > 0,
        "disclosure": "only MB-16 sessions already certified (status='admin_approved') are ever accepted",
    }


def collect_rag_evidence(*, rag_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [s for s in rag_sessions if s.get("admin_decision") == "approve"]
    rejected = [s["public_id"] for s in rag_sessions if s.get("admin_decision") != "approve"]
    return {
        "accepted_session_public_ids": [s["public_id"] for s in accepted],
        "rejected_session_public_ids": rejected,
        "accepted_count": len(accepted), "rejected_count": len(rejected),
        "ready": True,
        "disclosure": "only MB-17 sessions with a final admin_decision='approve' are ever accepted; zero accepted sessions is still valid",
    }


def collect_training_package(*, package_session: dict[str, Any] | None) -> dict[str, Any]:
    if package_session is None:
        return {
            "accepted": False, "session_public_id": None,
            "disclosure": "no MB-18 training package session was supplied",
        }
    accepted = (
        package_session["status"] == "admin_approved"
        and bool(package_session.get("package_directory"))
        and package_session.get("package_manifest", {}).get("artifact_count", 0) > 0
    )
    return {
        "accepted": accepted, "session_public_id": package_session["public_id"] if accepted else None,
        "rejected_session_public_id": None if accepted else package_session["public_id"],
        "disclosure": "only an MB-18 session that is admin_approved with a real, non-empty built package is ever accepted",
    }


def collect_evaluation_report(*, evaluation_session: dict[str, Any] | None) -> dict[str, Any]:
    if evaluation_session is None:
        return {
            "accepted": False, "session_public_id": None,
            "disclosure": "no MB-19 evaluation session was supplied",
        }
    accepted = evaluation_session["status"] == "admin_approved"
    return {
        "accepted": accepted, "session_public_id": evaluation_session["public_id"] if accepted else None,
        "rejected_session_public_id": None if accepted else evaluation_session["public_id"],
        "disclosure": "only an MB-19 session that is admin_approved is ever accepted",
    }
