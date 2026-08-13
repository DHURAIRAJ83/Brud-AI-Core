"""MB-09: Knowledge Roadmap -- pure assembly. Builds a forward-looking
view from already-computed evidence only: permanent learning-memory
history, the current cycle's strong/weak domains, and the learning
queue. Never predicts a number it cannot derive from real inputs.
"""

from __future__ import annotations

from typing import Any


def build_roadmap(
    *, memory_entry_count: int, current_weak_domains: list[str], current_strong_domains: list[str],
    queue: list[dict[str, Any]],
) -> dict[str, Any]:
    high_priority_topics = [item["topic"] for item in queue if item["priority"] in {"Critical", "High"}]
    return {
        "current_strengths": current_strong_domains,
        "current_weaknesses": current_weak_domains,
        "missing_knowledge": high_priority_topics,
        "future_priorities": [item["topic"] for item in queue],
        "expected_improvement": (
            f"addressing all {len(queue)} queued topic(s) would resolve the "
            f"{len(current_weak_domains)} currently weak domain(s) this cycle observed"
            if queue else "no queued topics -- no improvement projected this cycle"
        ),
        "next_recommended_datasets": [
            {"topic": item["topic"], "formats": item["suggested_dataset_type"]} for item in queue[:5]
        ],
        "cycles_in_memory": memory_entry_count,
    }
