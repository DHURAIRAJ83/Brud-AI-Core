"""MB-23: Runtime Report Generator -- pure assembly only. Builds a
closing report for one session (mirroring MB-18 through MB-22's own
report-generator precedent) and a separate aggregate runtime-analytics
summary -- every field is a direct pass-through of an already-computed
count or already-persisted record; nothing is re-derived or inferred.
"""

from __future__ import annotations

from typing import Any


def generate_session_report(
    *, session_public_id: str, message_count: int, used_rag_count: int, used_vision_count: int,
    used_tool_count: int, signal_counts_by_type: dict[str, int], satisfaction_score: float | None,
    unresolved_count: int, started_at: str | None, ended_at: str | None,
) -> dict[str, Any]:
    return {
        "session_public_id": session_public_id, "message_count": message_count,
        "used_rag_count": used_rag_count, "used_vision_count": used_vision_count,
        "used_tool_count": used_tool_count, "signal_counts_by_type": signal_counts_by_type,
        "satisfaction_score": satisfaction_score, "unresolved_count": unresolved_count,
        "started_at": started_at, "ended_at": ended_at,
        "no_automatic_learning_occurred": True, "no_automatic_training_occurred": True,
        "disclosure": (
            "a summary of this session's own already-recorded counts -- nothing here is re-derived "
            "or inferred beyond simple counting"
        ),
    }


def generate_runtime_analytics_summary(
    *, total_sessions: int, total_messages: int, total_signals_by_type: dict[str, int],
    top_candidates: list[dict[str, Any]], generated_at: str,
) -> dict[str, Any]:
    return {
        "total_sessions": total_sessions, "total_messages": total_messages,
        "total_signals_by_type": total_signals_by_type, "top_candidates": top_candidates,
        "generated_at": generated_at,
        "no_automatic_learning_occurred": True, "no_automatic_training_occurred": True,
        "clustering_is_heuristic": True, "ranking_is_heuristic": True,
        "disclosure": (
            "an aggregate summary of already-recorded counts -- the clustering and ranking that fed "
            "top_candidates are heuristic, not a calibrated model, and admin review remains mandatory "
            "before any candidate is acted on"
        ),
    }
