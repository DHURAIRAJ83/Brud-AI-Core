"""MB-11: Knowledge Factory Planner -- pure. Recommends which content
types (from a fixed, disclosed list) would close the gaps Coverage
Analyzer and Dataset Evolution Analyzer already found. Recommends
only -- never sources, generates, or ingests a single document.
"""

from __future__ import annotations

from typing import Any

CONTENT_TYPES = (
    "Books", "PDF", "Documentation", "Tutorials", "Examples", "Exercises", "Conversation", "FAQ",
    "Code Samples", "Benchmarks", "Reasoning Tasks", "Evaluation Sets", "Testing Dataset",
    "Instruction Dataset", "Conversation Dataset", "Synthetic Dataset", "Human Verified Dataset",
)


def plan_knowledge_factory(
    *, coverage_summary: dict[str, Any], weak_domains: list[str], missing_domains: list[str],
    advanced_overall_score: float,
) -> dict[str, Any]:
    recommendations: list[dict[str, str]] = []

    if coverage_summary["critical_gap_count"] > 0 or missing_domains:
        recommendations.append({
            "content_type": "Documentation",
            "why": f"{coverage_summary['critical_gap_count']} dimension(s) at Critical Gap and {len(missing_domains)} missing domain(s) -- foundational reference material closes this fastest",
        })
        recommendations.append({
            "content_type": "Tutorials",
            "why": "missing domains need worked, sequential explanations, not just reference facts",
        })
        recommendations.append({
            "content_type": "Books",
            "why": "for domains with zero coverage, longer-form source material gives the widest topic breadth per source",
        })

    if coverage_summary["by_difficulty"]["classification"] in {"Needs Expansion", "Critical Gap"}:
        recommendations.append({
            "content_type": "Exercises",
            "why": "difficulty distribution is imbalanced -- exercises let the difficulty band be targeted directly",
        })
        recommendations.append({
            "content_type": "Reasoning Tasks",
            "why": "difficulty imbalance often means a lack of multi-step reasoning content specifically",
        })

    if coverage_summary["by_knowledge_level"]["classification"] in {"Needs Expansion", "Critical Gap"}:
        recommendations.append({
            "content_type": "Examples",
            "why": "curriculum sequencing is weak -- worked examples bridge foundational and advanced content",
        })
        recommendations.append({
            "content_type": "Code Samples",
            "why": "concrete code samples are a low-ambiguity way to establish a missing prerequisite",
        })

    if coverage_summary["by_dataset_type"]["classification"] in {"Needs Expansion", "Critical Gap"}:
        recommendations.append({
            "content_type": "Instruction Dataset",
            "why": "record-type diversity is low -- instruction-formatted records are Brud AI's most common training shape",
        })
        recommendations.append({
            "content_type": "Conversation Dataset",
            "why": "record-type diversity is low -- multi-turn conversation records exercise a different training path than single-turn instructions",
        })

    if advanced_overall_score < 60.0:
        recommendations.append({
            "content_type": "Benchmarks",
            "why": f"advanced quality score {advanced_overall_score} is below 60 -- better measurement is needed before more content is trusted",
        })
        recommendations.append({
            "content_type": "Evaluation Sets",
            "why": "a low quality score with no dedicated evaluation set makes future regressions hard to detect",
        })

    if weak_domains:
        recommendations.append({
            "content_type": "FAQ",
            "why": f"{len(weak_domains)} weak domain(s) -- FAQ-style records are the fastest way to cover common questions per domain",
        })
        recommendations.append({
            "content_type": "Human Verified Dataset",
            "why": "any content sourced for a currently-weak domain should be human-verified before being trusted for training",
        })

    if not recommendations:
        recommendations.append({
            "content_type": "Testing Dataset",
            "why": "no coverage gap was found -- a dedicated testing dataset is the lowest-risk way to confirm that before doing anything else",
        })

    return {
        "recommendations": recommendations,
        "content_type_count": len(recommendations),
        "available_content_types": list(CONTENT_TYPES),
    }
