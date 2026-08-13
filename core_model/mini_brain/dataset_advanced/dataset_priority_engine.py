"""MB-05.1: Dataset Priority Engine -- ranks findings from every other
dataset_advanced module into Critical/High/Medium/Low, each with WHY,
Impact, and Priority. Purely a synthesis over already-computed
results -- never re-derives anything, never executes anything.
"""

from __future__ import annotations

from typing import Any

_PRIORITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def _item(*, priority: str, issue: str, why: str, impact: str) -> dict[str, str]:
    return {"priority": priority, "issue": issue, "why": why, "impact": impact}


def rank_priorities(
    *, conflicts: dict[str, Any], bias: dict[str, Any], curriculum: dict[str, Any],
    knowledge_gaps: dict[str, Any], risk: dict[str, Any],
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    if risk["risk_item_count"] > 0:
        has_critical = any(item["severity"] == "critical" for item in risk["risk_items"])
        items.append(_item(
            priority="Critical" if has_critical else "High",
            issue=f"{risk['risk_item_count']} PII/secret finding(s) detected",
            why=risk["reason"],
            impact="legal/privacy exposure if this data is used for training or RAG without redaction",
        ))

    if conflicts["conflict_count"] > 0:
        items.append(_item(
            priority="High" if conflicts["conflict_score"] > 0.05 else "Medium",
            issue=f"{conflicts['conflict_count']} conflicting answer group(s)",
            why=conflicts["reason"],
            impact="a model trained on this data may learn contradictory answers to the same question",
        ))

    for dimension_name, entry in bias.items():
        if entry["verdict"] == "Heavy Bias":
            items.append(_item(
                priority="Medium",
                issue=f"Heavy bias in {dimension_name}",
                why=entry["reason"],
                impact="the resulting model may underperform on underrepresented segments",
            ))

    for topic in curriculum["topics"]:
        if topic["verdict"] == "Missing Prerequisite":
            items.append(_item(
                priority="Medium",
                issue=f"{topic['subtopic']}: missing prerequisite content",
                why=topic["reason"],
                impact="learners/model see advanced content without foundational grounding",
            ))
        elif topic["verdict"] == "Broken Sequence":
            items.append(_item(
                priority="Low",
                issue=f"{topic['subtopic']}: broken learning sequence",
                why=topic["reason"],
                impact="difficulty progression for this subtopic cannot be verified",
            ))

    for gap in knowledge_gaps["missing_topics"]:
        items.append(_item(
            priority="Low",
            issue=f"Missing topic: {gap['topic']}",
            why=gap["reason"],
            impact="the dataset cannot teach or answer questions about this topic at all",
        ))

    items.sort(key=lambda item: _PRIORITY_ORDER[item["priority"]])
    return items
