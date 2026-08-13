"""MB-08: Dataset Recommendation Engine -- pure. Recommends dataset
FORMATS per weak domain, each with a WHY grounded in real evidence
from the knowledge-gap and weak-topic stages. Never recommends a
specific document, source, or URL -- only a format category and the
reason a domain needs more of it. Never creates, downloads, or
modifies anything -- Dataset Studio remains the only place a dataset
is actually built.
"""

from __future__ import annotations

from typing import Any

SEVERE_WEAKNESS_THRESHOLD = 60.0


def recommend_datasets(
    *, weak_topics: list[dict[str, Any]], missing_documentation_domains: list[str],
    missing_workflow_domains: list[str],
) -> dict[str, Any]:
    documentation_domains = set(missing_documentation_domains)
    workflow_domains = set(missing_workflow_domains)

    recommendations = []
    for topic in weak_topics:
        if topic["classification"] != "Weak":
            continue
        domain = topic["domain"]
        formats: list[dict[str, str]] = []
        if domain in documentation_domains:
            formats.append({
                "format": "Documentation", "why": f"'{domain}' has cases citing missing retrievable documentation",
            })
            formats.append({
                "format": "PDFs", "why": f"structured reference material would give '{domain}' retrievable evidence",
            })
        if domain in workflow_domains:
            formats.append({
                "format": "QA pairs", "why": f"'{domain}' has cases where the model itself lacks domain understanding, not just missing evidence",
            })
            formats.append({
                "format": "Conversations", "why": f"realistic dialogue examples would demonstrate '{domain}' workflows the model currently fails",
            })
        if topic["weakness_index"] >= SEVERE_WEAKNESS_THRESHOLD:
            formats.append({
                "format": "Books", "why": f"'{domain}' weakness index ({topic['weakness_index']}) is severe -- deeper reference material is warranted",
            })
        if not formats:
            formats.append({
                "format": "QA pairs",
                "why": f"'{domain}' is classified Weak (weakness_index={topic['weakness_index']}) with {topic['case_count']} case(s) but no more specific documentation/workflow signal",
            })
        recommendations.append({
            "domain": domain, "weakness_index": topic["weakness_index"], "case_count": topic["case_count"],
            "recommended_formats": formats,
        })

    return {
        "recommendations": recommendations,
        "domains_needing_data": [r["domain"] for r in recommendations],
    }
