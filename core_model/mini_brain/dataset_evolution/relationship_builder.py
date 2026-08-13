"""MB-11: Knowledge Relationship Builder -- pure. Classifies
already-detected duplicate and conflict groups (from the existing
`ExternalDatasetDuplicateService.group_normalized_duplicates()`/
`.find_conflicts()`, reused unchanged over a normalized list of
"knowledge claims" the service assembles from MB-08/MB-09/MB-10
evidence) into duplicate/conflicting knowledge signals, and flags
weak/missing evidence and disconnected knowledge by comparing weak
domains against what the current dataset (via Coverage Analyzer) and
recent research (via MB-10) actually cover. Never re-detects
duplicates or conflicts itself.
"""

from __future__ import annotations

from typing import Any


def build_relationships(
    *,
    duplicate_groups: list[list[str]],
    conflict_groups: list[dict[str, Any]],
    weak_domains: list[str],
    covered_domains: list[str],
    research_backed_domains: list[str],
) -> dict[str, Any]:
    covered = set(covered_domains)
    research_backed = set(research_backed_domains)

    disconnected_knowledge = [d for d in weak_domains if d not in covered]
    missing_evidence = [d for d in weak_domains if d not in research_backed]
    weak_evidence = [
        d for d in weak_domains if d in research_backed and d not in covered
    ]

    return {
        "duplicate_knowledge_count": len(duplicate_groups),
        "duplicate_knowledge_groups": duplicate_groups,
        "conflicting_knowledge_count": len(conflict_groups),
        "conflicting_knowledge_groups": conflict_groups,
        "disconnected_knowledge": disconnected_knowledge,
        "missing_evidence": missing_evidence,
        "weak_evidence": weak_evidence,
        "broken_relationships": bool(conflict_groups) or bool(disconnected_knowledge),
        "relationship_health_score": round(
            max(0.0, 100.0 - len(duplicate_groups) * 10.0 - len(conflict_groups) * 15.0
                - len(disconnected_knowledge) * 5.0), 1,
        ),
    }
