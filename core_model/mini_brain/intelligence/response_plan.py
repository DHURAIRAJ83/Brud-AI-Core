"""Response Plan Generator -- assembles the final structured plan.

Per MB-03's own future-compatibility requirement, a future model must
receive only four things: Validated Context, Validated Knowledge,
Validated Workflow, and this plan itself -- nothing else. This
function is the single place that shape gets assembled, so a future
MB-04 integration has exactly one contract to read, not five.
"""

from __future__ import annotations

from typing import Any


def _suggested_response_type(rules: dict[str, Any], knowledge_plan: dict[str, Any]) -> str:
    if rules["blocked"]:
        return "training_boundary_notice"
    if "needs_clarification" in rules["flags"]:
        return "clarify_question"
    if "insufficient_knowledge" in rules["flags"]:
        return "insufficient_knowledge"
    if knowledge_plan["primary_knowledge"]:
        return "explain_with_primary_knowledge"
    return "explain_with_supporting_knowledge"


def build_response_plan(
    *,
    question_analysis: dict[str, Any],
    context: dict[str, Any],
    workflow: dict[str, Any],
    knowledge_plan: dict[str, Any],
    rules: dict[str, Any],
    confidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "suggested_response_type": _suggested_response_type(rules, knowledge_plan),
        "validated_context": {
            "matched_items": context["matched_item_titles"],
            "documentation_references": context["documentation_references"],
        },
        "validated_knowledge": {
            "primary": knowledge_plan["primary_knowledge"],
            "supporting": knowledge_plan["supporting_knowledge"],
            "priority_order": knowledge_plan["priority_order"],
        },
        "validated_workflow": {
            "current_step": workflow["current_step"],
            "previous_steps": workflow["previous_steps"],
            "next_steps": workflow["next_steps"],
            "dependencies": workflow["dependencies"],
        },
        "disclaimers": rules["disclaimers"],
        "confidence_band": confidence["band"],
        "intent": question_analysis["intent"],
        "question_type": question_analysis["question_type"],
    }
