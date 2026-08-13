"""MB-10: Research Quality Engine -- pure. Combines already-computed
per-provider evidence/citation signals with the already-computed
aggregate agreement/conflict/duplicate scores into the task spec's
seven named dimensions plus an Overall Quality figure. Never
recomputes evidence, citations, agreement, conflicts, or duplicates
itself -- those come from `evidence_validator`, `citation_analyzer`,
`provider_consensus_engine`, `conflict_resolver`, and
`duplicate_resolver` respectively.
"""

from __future__ import annotations

from typing import Any

_COMPLETE_SCORE = 100.0
_INCOMPLETE_SCORE = 40.0


def score_provider(*, provider: str, evidence_result: dict[str, Any], citation_result: dict[str, Any]) -> dict[str, Any]:
    completeness_score = _INCOMPLETE_SCORE if evidence_result["missing_facts"] else _COMPLETE_SCORE
    trust_score = round(
        (evidence_result["evidence_score"] + citation_result["citation_score"] + completeness_score) / 3, 1,
    )
    return {
        "provider": provider,
        "evidence_score": evidence_result["evidence_score"],
        "citation_score": citation_result["citation_score"],
        "completeness_score": completeness_score,
        "trust_score": trust_score,
    }


def score_overall(
    *, provider_scores: list[dict[str, Any]], agreement_score: float, conflict_score: float,
    duplicate_score: float,
) -> dict[str, Any]:
    if provider_scores:
        avg_evidence = round(sum(p["evidence_score"] for p in provider_scores) / len(provider_scores), 1)
        avg_citation = round(sum(p["citation_score"] for p in provider_scores) / len(provider_scores), 1)
        avg_completeness = round(sum(p["completeness_score"] for p in provider_scores) / len(provider_scores), 1)
        avg_trust = round(sum(p["trust_score"] for p in provider_scores) / len(provider_scores), 1)
    else:
        avg_evidence = avg_citation = avg_completeness = avg_trust = 0.0

    overall_quality = round(
        sum([avg_evidence, agreement_score, conflict_score, duplicate_score, avg_citation, avg_completeness, avg_trust]) / 7,
        1,
    )

    return {
        "evidence_score": avg_evidence,
        "agreement_score": agreement_score,
        "conflict_score": conflict_score,
        "duplicate_score": duplicate_score,
        "citation_score": avg_citation,
        "completeness_score": avg_completeness,
        "trust_score": avg_trust,
        "overall_quality": overall_quality,
        "per_provider": provider_scores,
    }
