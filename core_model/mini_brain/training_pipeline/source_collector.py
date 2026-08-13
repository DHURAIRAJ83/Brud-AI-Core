"""MB-18: Source Collector -- pure. Stages 2 and 3 both live here since
both are "validate and summarize a list of already-fetched upstream
sessions" concerns. Never assumes a session is usable -- Stage 2 only
accepts MB-16 sessions already `status == 'admin_approved'`; Stage 3
only accepts MB-17 sessions with a final approved decision.
"""

from __future__ import annotations

from typing import Any


def collect_datasets(*, dataset_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    accepted = [s for s in dataset_sessions if s["status"] == "admin_approved"]
    rejected = [s["public_id"] for s in dataset_sessions if s["status"] != "admin_approved"]
    total_records = sum(s.get("record_count", 0) for s in accepted)

    return {
        "accepted_session_public_ids": [s["public_id"] for s in accepted],
        "rejected_session_public_ids": rejected,
        "accepted_count": len(accepted), "rejected_count": len(rejected),
        "total_record_count": total_records,
        "ready": len(accepted) > 0,
        "disclosure": "only MB-16 sessions already certified (status='admin_approved') are ever accepted",
    }


def collect_rag_memory(*, rag_memory_entries: list[dict[str, Any]]) -> dict[str, Any]:
    approved_decisions = {"approve"}
    accepted = [m for m in rag_memory_entries if m.get("admin_decision") in approved_decisions]
    rejected = [
        m["public_id"] for m in rag_memory_entries if m.get("admin_decision") not in approved_decisions
    ]
    grounded_count = sum(1 for m in accepted if not m.get("hallucination_flag"))

    return {
        "accepted_memory_public_ids": [m["public_id"] for m in accepted],
        "rejected_memory_public_ids": rejected,
        "accepted_count": len(accepted), "rejected_count": len(rejected),
        "grounded_count": grounded_count,
        "ready": True,
        "disclosure": "only MB-17 RAG memory entries with a final admin_decision='approve' are ever accepted -- a training session with zero approved queries is still valid, just carries no grounded-evidence signal",
    }
