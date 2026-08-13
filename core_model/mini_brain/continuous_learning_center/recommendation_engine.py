"""MB-09: Learning Recommendation Engine -- pure. Recommends exactly
one of the six actions the task spec names, from already-computed
evidence only. Never executes anything -- the admin decides, and even
an approved recommendation only hands off to MB-06/MB-07's own,
separately admin-gated workflows.
"""

from __future__ import annotations

from typing import Any

ACTIONS = (
    "No Action", "Collect More Data", "Local Draft", "External Provider Consensus",
    "RAG Evaluation", "Training Candidate",
)
LARGE_QUEUE_THRESHOLD = 3


def recommend_next_action(
    *, queue: list[dict[str, Any]], dataset_evolution_recommendation: str,
    provider_consensus: dict[str, Any] | None,
) -> dict[str, Any]:
    evidence = {
        "queue_length": len(queue), "dataset_evolution_recommendation": dataset_evolution_recommendation,
        "provider_consensus_confidence": provider_consensus.get("confidence") if provider_consensus else None,
    }

    if not queue:
        return {
            "action": "No Action", "why": "the learning queue is empty -- no recurring weaknesses to address",
            "evidence": evidence,
        }

    critical_items = [item for item in queue if item["priority"] == "Critical"]

    if provider_consensus and provider_consensus.get("confidence") == "High":
        return {
            "action": "Training Candidate",
            "why": "provider consensus reached High confidence on queued topics -- content is ready to be considered for training, pending admin approval",
            "evidence": evidence,
        }

    if dataset_evolution_recommendation in {"replace", "split"} and critical_items:
        return {
            "action": "RAG Evaluation",
            "why": f"dataset evolution recommends '{dataset_evolution_recommendation}' and {len(critical_items)} critical queue item(s) exist -- evaluate via RAG before considering training",
            "evidence": evidence,
        }

    if critical_items:
        return {
            "action": "External Provider Consensus",
            "why": f"{len(critical_items)} critical queue item(s) need externally-sourced, cross-checked ground truth before a local draft can be trusted",
            "evidence": evidence,
        }

    if len(queue) >= LARGE_QUEUE_THRESHOLD:
        return {
            "action": "Local Draft",
            "why": f"{len(queue)} queue item(s) (>= {LARGE_QUEUE_THRESHOLD}) is enough structured demand to prepare a local draft outline",
            "evidence": evidence,
        }

    return {
        "action": "Collect More Data",
        "why": "queue items exist but are below the threshold for drafting -- keep observing before committing effort",
        "evidence": evidence,
    }
