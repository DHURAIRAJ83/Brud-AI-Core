"""MB-05.1: Advanced Dataset Score -- Coverage, Consistency, Conflict,
Bias, Difficulty, Curriculum, Knowledge Gap, Risk, and an explicit
UNWEIGHTED-mean Overall. Every score states its own formula, the
actual numbers used, and a one-line reason -- same discipline as
MB-05's own `score_engine.py`.
"""

from __future__ import annotations

from typing import Any

_BALANCE_VERDICT_PENALTY = {"Balanced": 0, "Slight Bias": 15, "Heavy Bias": 40}
_CURRICULUM_VERDICT_WEIGHT = {"Good Sequence": 1.0, "Missing Prerequisite": 0.3, "Broken Sequence": 0.0}


def _entry(*, score: float, formula: str, calculation: str, reason: str) -> dict[str, Any]:
    return {"score": max(0, min(100, round(score))), "formula": formula, "calculation": calculation, "reason": reason}


def compute_advanced_scores(
    *, conflicts: dict[str, Any], bias: dict[str, Any], coverage: dict[str, Any],
    difficulty: dict[str, Any], curriculum: dict[str, Any], knowledge_gaps: dict[str, Any],
    risk: dict[str, Any],
) -> dict[str, Any]:
    coverage_pcts = [d["coverage_percent"] for d in coverage.values()]
    coverage_score = _entry(
        score=sum(coverage_pcts) / len(coverage_pcts) if coverage_pcts else 0.0,
        formula="mean(coverage_percent for every domain in the reference taxonomy)",
        calculation=f"mean({coverage_pcts}) = {round(sum(coverage_pcts) / len(coverage_pcts), 1) if coverage_pcts else 0}",
        reason="how much of the illustrative topic taxonomy this dataset actually covers",
    )

    curriculum_topics = curriculum["topics"]
    curriculum_weights = [_CURRICULUM_VERDICT_WEIGHT[t["verdict"]] for t in curriculum_topics]
    curriculum_score = _entry(
        score=(sum(curriculum_weights) / len(curriculum_weights) * 100) if curriculum_weights else 100.0,
        formula="mean(1.0 for Good Sequence, 0.3 for Missing Prerequisite, 0.0 for Broken Sequence) * 100",
        calculation=f"mean({curriculum_weights}) * 100 = {round((sum(curriculum_weights) / len(curriculum_weights) * 100) if curriculum_weights else 100.0, 1)}",
        reason="how well difficulty progression is represented across covered subtopics",
    )
    consistency_score = curriculum_score  # same underlying signal, exposed under its own required name too

    conflict_score = _entry(
        score=(1 - conflicts["conflict_score"]) * 100,
        formula="(1 - conflict_score) * 100",
        calculation=f"(1 - {conflicts['conflict_score']}) * 100 = {round((1 - conflicts['conflict_score']) * 100, 1)}",
        reason="share of questions with a single, non-contradictory answer",
    )

    bias_penalties = [_BALANCE_VERDICT_PENALTY[entry["verdict"]] for entry in bias.values()]
    bias_score = _entry(
        score=100 - (sum(bias_penalties) / len(bias_penalties) if bias_penalties else 0),
        formula="100 - mean(0 for Balanced, 15 for Slight Bias, 40 for Heavy Bias across all 5 dimensions)",
        calculation=f"100 - mean({bias_penalties}) = {round(100 - (sum(bias_penalties) / len(bias_penalties) if bias_penalties else 0), 1)}",
        reason="how evenly language/instruction/conversation/domain/category are distributed",
    )

    dist = difficulty["distribution"]
    total_difficulty = sum(dist.values()) or 1
    difficulty_dominant_share = max(dist.values()) / total_difficulty if dist else 0.0
    difficulty_score = _entry(
        score=(1 - difficulty_dominant_share) * 100,
        formula="(1 - dominant_difficulty_share) * 100",
        calculation=f"(1 - {round(difficulty_dominant_share, 3)}) * 100 = {round((1 - difficulty_dominant_share) * 100, 1)}",
        reason="a healthy dataset has a mix of difficulty levels, not everything in one band",
    )

    knowledge_gap_score = _entry(
        score=(knowledge_gaps["coverage_ratio"] or 0.0) * 100,
        formula="covered_important_topics / total_important_topics * 100",
        calculation=f"{knowledge_gaps['coverage_ratio']} * 100 = {round((knowledge_gaps['coverage_ratio'] or 0.0) * 100, 1)}",
        reason="share of the fixed important-topics reference list with at least one matching record",
    )

    risk_score = _entry(
        score=(1 - min(risk["risk_score"], 1.0)) * 100,
        formula="(1 - min(risk_score, 1.0)) * 100",
        calculation=f"(1 - min({risk['risk_score']}, 1.0)) * 100 = {round((1 - min(risk['risk_score'], 1.0)) * 100, 1)}",
        reason="fewer PII/secret findings per record means a safer dataset",
    )

    components = {
        "coverage": coverage_score, "consistency": consistency_score, "conflict": conflict_score,
        "bias": bias_score, "difficulty": difficulty_score, "curriculum": curriculum_score,
        "knowledge_gap": knowledge_gap_score, "risk": risk_score,
    }
    overall_value = sum(c["score"] for c in components.values()) / len(components)
    overall = _entry(
        score=overall_value,
        formula="unweighted mean of all 8 component scores -- no hidden weights",
        calculation=f"mean({[c['score'] for c in components.values()]}) = {round(overall_value, 1)}",
        reason="a single overall figure, transparently the plain average of every component above",
    )

    return {**components, "overall": overall}
