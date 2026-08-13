"""MB-10: Dataset Draft Builder -- pure. Assembles the final draft
from already-computed inputs (a topic, an outline, and -- for
Multi-Provider Consensus mode -- the already-computed quality report
and traceable provider outputs). MB-10 never creates a final dataset;
Dataset Studio remains the only place a dataset record is actually
written. Every draft is hard-coded `"verified": False`, structurally
impossible to omit.
"""

from __future__ import annotations

from typing import Any

_STRUCTURE_TEMPLATE = (
    "Introduction to {topic}", "Core concepts of {topic}", "Common questions about {topic}",
    "Worked examples in {topic}",
)


def build_dataset_draft(
    *, topic: str, mode: str, quality_report: dict[str, Any] | None = None,
    traceable_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    structure = [section.format(topic=topic) for section in _STRUCTURE_TEMPLATE]
    return {
        "topic": topic,
        "mode": mode,
        "structure": structure,
        "required_topics": [topic],
        "sources": traceable_sources or [],
        "quality_summary": quality_report,
        "verified": False,
        "status": "needs_admin_review",
        "disclosure": (
            "draft only -- no dataset record has been created anywhere; Dataset Studio remains "
            "the only place a dataset is actually built, and only after explicit admin approval"
        ),
    }
