"""MB-21: Recommendation Builder -- pure. Produces suggested next
actions only -- never an approval decision, never an automatic dataset
or release action. For public-style stress testing, surfaces per-
category pass/fail observations and missing-knowledge topics. For data
acquisition, produces a handoff package pointer for MB-13/MB-16's own
human review workflow -- this module never inserts anything into
Dataset Studio itself.
"""

from __future__ import annotations

from typing import Any


def build_public_evaluation_recommendations(
    *, normalized_responses: list[dict[str, Any]], agreement_report: dict[str, Any],
) -> dict[str, Any]:
    observations = []
    missing_knowledge_topics = []
    for response in normalized_responses:
        if response["status"] != "success":
            observations.append({"provider_key": response["provider_key"], "result": "fail", "reason": response.get("error_message") or response["status"]})
            continue
        text_lower = (response.get("normalized_text") or "").lower()
        hedge_signal = any(p in text_lower for p in ("not sure", "don't have", "no information", "cannot confirm"))
        observations.append({"provider_key": response["provider_key"], "result": "hedge" if hedge_signal else "pass"})
        if hedge_signal:
            missing_knowledge_topics.append(response["provider_key"])

    suggested_dataset_improvements: list[str] = []
    suggested_rag_improvements: list[str] = []
    if agreement_report["failed_provider_count"] > 0:
        suggested_rag_improvements.append("investigate why some providers could not be reached -- verify provider configuration, not dataset content")
    if agreement_report["unsupported_claim_count"] > 0:
        suggested_dataset_improvements.append("some provider responses had no cross-provider corroboration -- consider adding source material covering those areas")
    if agreement_report["hallucination_warning_count"] > 0:
        suggested_rag_improvements.append("one or more providers indicated uncertainty -- consider expanding retrieval coverage for the tested topic")
    if not suggested_dataset_improvements and not suggested_rag_improvements:
        suggested_dataset_improvements.append("no specific gap was surfaced by this run -- this is not a certification of completeness")

    return {
        "observations": observations, "missing_knowledge_topics": missing_knowledge_topics,
        "suggested_dataset_improvements": suggested_dataset_improvements,
        "suggested_rag_improvements": suggested_rag_improvements,
        "disclosure": "suggestions only -- never an approval or an automatic action; a human admin decides what, if anything, to act on",
    }


def build_data_acquisition_handoff(*, normalized_responses: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [r for r in normalized_responses if r["status"] == "success" and r.get("normalized_text")]
    covered_sections: dict[str, int] = {}
    for response in successful:
        for section, present in (response.get("section_coverage") or {}).items():
            if present:
                covered_sections[section] = covered_sections.get(section, 0) + 1

    next_actions = [
        "an admin must manually review every candidate response below before any of it is used",
        "if accepted, use MB-13's own Language Intelligence tab to check the candidate text before drafting",
        "if accepted, use MB-16's own Multimodal Dataset Generator to draft real dataset records -- this phase never writes to Dataset Studio directly",
    ]

    return {
        "candidate_provider_count": len(successful), "covered_sections": covered_sections,
        "next_actions": next_actions,
        "disclosure": (
            "a handoff pointer only -- every candidate response remains unverified until a human admin "
            "reviews it through MB-13/MB-16's own existing governance workflows; nothing here is "
            "inserted into Dataset Studio automatically"
        ),
    }
