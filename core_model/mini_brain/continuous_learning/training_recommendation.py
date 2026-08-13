"""MB-08: Training Recommendation Engine -- pure. Classifies the
overall cycle into one of four actions -- No Training / Fine Tune /
Continue Training / Full Retraining -- from real, already-computed
evidence only (failure rate, hallucination rate, weak-topic severity,
and the Knowledge Gap Registry's own real
`eligible_for_training_assessment` case count). This is advisory only:
it recommends an action and cites evidence, it never starts one --
MB-06 Learning Supervisor remains the only component that can actually
submit a training request, and only after a separate, explicit admin
decision there.

Thresholds are fixed and disclosed, not empirically validated against
a real training outcome in this project -- same honesty standard as
every other threshold in this engagement.
"""

from __future__ import annotations

from typing import Any

NO_TRAINING_FAILURE_RATE = 0.05
NO_TRAINING_HALLUCINATION_RATE = 0.05
FULL_RETRAIN_FAILURE_RATE = 0.35
FULL_RETRAIN_HALLUCINATION_RATE = 0.30
SEVERE_WEAKNESS_THRESHOLD = 60.0
FULL_RETRAIN_SEVERE_TOPIC_COUNT = 3
CONTINUE_TRAINING_ELIGIBLE_CASE_COUNT = 5
CONTINUE_TRAINING_WEAK_TOPIC_COUNT = 2


def recommend_training_action(
    *, failure_rate: float | None, hallucination_rate: float | None,
    weak_topics: list[dict[str, Any]], training_eligible_case_count: int,
) -> dict[str, Any]:
    failure_rate = failure_rate or 0.0
    hallucination_rate = hallucination_rate or 0.0
    weak = [t for t in weak_topics if t["classification"] == "Weak"]
    severe_weak = [t for t in weak if t["weakness_index"] >= SEVERE_WEAKNESS_THRESHOLD]

    evidence = {
        "failure_rate": failure_rate, "hallucination_rate": hallucination_rate,
        "weak_topic_count": len(weak), "severe_weak_topic_count": len(severe_weak),
        "training_eligible_case_count": training_eligible_case_count,
    }

    if (
        failure_rate >= FULL_RETRAIN_FAILURE_RATE
        and hallucination_rate >= FULL_RETRAIN_HALLUCINATION_RATE
        and len(severe_weak) >= FULL_RETRAIN_SEVERE_TOPIC_COUNT
    ):
        return {
            "action": "Full Retraining",
            "why": (
                f"failure_rate {failure_rate} >= {FULL_RETRAIN_FAILURE_RATE} and "
                f"hallucination_rate {hallucination_rate} >= {FULL_RETRAIN_HALLUCINATION_RATE} and "
                f"{len(severe_weak)} severe weak topic(s) >= {FULL_RETRAIN_SEVERE_TOPIC_COUNT}"
            ),
            "evidence": evidence,
        }

    if (
        training_eligible_case_count >= CONTINUE_TRAINING_ELIGIBLE_CASE_COUNT
        or len(weak) >= CONTINUE_TRAINING_WEAK_TOPIC_COUNT
    ):
        return {
            "action": "Continue Training",
            "why": (
                f"{training_eligible_case_count} case(s) already eligible for training assessment "
                f"and/or {len(weak)} weak topic(s) present -- below Full Retraining severity"
            ),
            "evidence": evidence,
        }

    if failure_rate <= NO_TRAINING_FAILURE_RATE and hallucination_rate <= NO_TRAINING_HALLUCINATION_RATE and not weak:
        return {
            "action": "No Training",
            "why": (
                f"failure_rate {failure_rate} <= {NO_TRAINING_FAILURE_RATE} and "
                f"hallucination_rate {hallucination_rate} <= {NO_TRAINING_HALLUCINATION_RATE} and no weak topics"
            ),
            "evidence": evidence,
        }

    return {
        "action": "Fine Tune",
        "why": (
            f"failure_rate {failure_rate} and hallucination_rate {hallucination_rate} are elevated "
            "but below Full Retraining/Continue Training thresholds"
        ),
        "evidence": evidence,
    }
