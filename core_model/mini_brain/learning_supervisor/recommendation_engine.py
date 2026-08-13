"""MB-06: Learning Recommendation Engine -- deterministic, rule-based.
Every recommendation carries WHY (the triggering fact), Evidence (the
exact source numbers), and Confidence (high/medium/low, itself a
disclosed fixed rule -- never a learned or probabilistic score).
"""

from __future__ import annotations

from typing import Any


def _rec(*, action: str, why: str, evidence: Any, confidence: str) -> dict[str, Any]:
    return {"action": action, "why": why, "evidence": evidence, "confidence": confidence}


def generate_learning_recommendations(
    *,
    dataset_readiness: dict[str, Any],
    advanced_report: dict[str, Any] | None,
    rag_report: dict[str, Any] | None,
    training_result: dict[str, Any] | None,
    comparison: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    recommendations: list[dict[str, Any]] = []

    if dataset_readiness.get("status") == "Not Ready":
        recommendations.append(_rec(
            action="Improve dataset before retraining",
            why="dataset training readiness was 'Not Ready'",
            evidence=dataset_readiness.get("reasons", []),
            confidence="high",
        ))

    if advanced_report:
        if advanced_report.get("conflicts", {}).get("conflict_count", 0) > 0:
            recommendations.append(_rec(
                action="Resolve dataset conflicts before retraining",
                why="the dataset contains questions with contradictory answers",
                evidence={"conflict_count": advanced_report["conflicts"]["conflict_count"]},
                confidence="high",
            ))
        bias = advanced_report.get("bias", {})
        for dimension, entry in bias.items():
            if entry.get("verdict") == "Heavy Bias" and dimension == "language_balance":
                dominant = entry.get("dominant")
                recommendations.append(_rec(
                    action=f"Collect more non-{dominant} language data" if dominant else "Balance language distribution",
                    why=f"language balance is 'Heavy Bias' toward {dominant}",
                    evidence={"dominant_share": entry.get("dominant_share")},
                    confidence="medium",
                ))
        for gap in advanced_report.get("knowledge_gaps", {}).get("missing_topics", []):
            recommendations.append(_rec(
                action=f"Add training data covering {gap['topic']}",
                why=gap["reason"],
                evidence={"topic": gap["topic"]},
                confidence="medium",
            ))

    if rag_report and rag_report.get("production_rag_readiness") in ("blocked", "not_ready"):
        recommendations.append(_rec(
            action="Investigate RAG evaluation issues before proceeding",
            why=(
                f"the RAG Sandbox report classified production readiness as "
                f"'{rag_report['production_rag_readiness']}'"
            ),
            evidence={
                "blocking_reasons": rag_report.get("blocking_reasons", []),
                "threshold_evaluation": rag_report.get("threshold_evaluation", []),
            },
            confidence="high" if rag_report["production_rag_readiness"] == "blocked" else "medium",
        ))

    if training_result:
        if training_result.get("failed"):
            recommendations.append(_rec(
                action="Retrain",
                why="the training job ended in a failed state",
                evidence={"job_status": training_result.get("job_status")},
                confidence="high",
            ))
        for indicator in training_result.get("indicators", []):
            if indicator.startswith("overfitting_signal"):
                recommendations.append(_rec(
                    action="Reduce training steps or add regularization, then retrain",
                    why=indicator,
                    evidence={"train_validation_gap": training_result.get("train_validation_gap")},
                    confidence="medium",
                ))
            elif indicator.startswith("underfitting_signal"):
                recommendations.append(_rec(
                    action="Increase training steps or learning rate, then retrain",
                    why=indicator,
                    evidence={"loss_improvement_ratio": training_result.get("loss_improvement_ratio")},
                    confidence="medium",
                ))
            elif indicator.startswith("divergence_signal"):
                recommendations.append(_rec(
                    action="Lower the learning rate and retrain",
                    why=indicator,
                    evidence={"diverging": True},
                    confidence="high",
                ))

    if comparison:
        if comparison.get("regression_count", 0) > 0:
            regressions = [c for c in comparison["comparisons"] if c["classification"] == "regression"]
            recommendations.append(_rec(
                action="Benchmark regression detected -- do not release without review",
                why=f"{comparison['regression_count']} metric(s) regressed relative to the previous production model",
                evidence=regressions,
                confidence="high",
            ))
        if comparison.get("requested_categories_without_real_data"):
            recommendations.append(_rec(
                action="Add benchmark fixtures for the missing categories",
                why="some requested comparison categories have no real fixture-based evaluation data in this environment",
                evidence={"missing_categories": comparison["requested_categories_without_real_data"]},
                confidence="low",
            ))

    if not recommendations:
        recommendations.append(_rec(
            action="Safe for release review",
            why="no blocking dataset, RAG, training, or benchmark issues were found",
            evidence={"checked": ["dataset_readiness", "advanced_report", "rag_report", "training_result", "comparison"]},
            confidence="medium",
        ))

    return recommendations
