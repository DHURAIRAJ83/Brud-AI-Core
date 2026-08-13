"""MB-10: Research Request Builder -- pure. Turns a topic and
already-gathered evidence (typically MB-09's own learning queue/
roadmap entries) into a structured research request. Never fetches
anything itself and never contacts a provider.
"""

from __future__ import annotations

from typing import Any


def build_research_request(
    *, topic: str, evidence: dict[str, Any], priority: str | None = None,
) -> dict[str, Any]:
    questions = [
        f"What are the core, well-established facts about {topic}?",
        f"What common misconceptions exist about {topic}?",
        f"What sources are authoritative for {topic}?",
    ]
    return {
        "topic": topic,
        "questions": questions,
        "evidence": evidence,
        "priority": priority,
        "status": "prepared",
    }
