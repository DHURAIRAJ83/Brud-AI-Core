"""MB-10: Research Report Generator -- pure assembly only. Merges
every stage's already-computed output into the single document the
admin reviews. Never recomputes anything; every field is a direct
pass-through of an earlier stage's own real output.
"""

from __future__ import annotations

from typing import Any


def generate_research_report(
    *,
    session_public_id: str,
    research_request: dict[str, Any],
    mode: str | None,
    selected_providers: list[dict[str, Any]],
    consensus_report: dict[str, Any] | None,
    quality_report: dict[str, Any] | None,
    dataset_draft: dict[str, Any] | None,
    recommendation: dict[str, Any] | None,
    rag_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "session_public_id": session_public_id,
        "research_request": research_request,
        "mode": mode,
        "selected_providers": selected_providers,
        "consensus_report": consensus_report,
        "quality_report": quality_report,
        "dataset_draft": dataset_draft,
        "recommendation": recommendation,
        "rag_report": rag_report,
        "ready_for_admin_review": dataset_draft is not None,
    }
