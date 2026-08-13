"""Knowledge Planner -- classifies already-matched Knowledge Core
items into Primary / Supporting / Optional / Excluded, deterministically.

Rules, in order (first match wins):
1. `status == "deprecated"` -> Excluded.
2. Domain matches the intent's expected domain AND relevance_score >= 2
   -> Primary.
3. Domain matches the intent's expected domain, OR the item is reachable
   from a Primary item via a relationship -> Supporting.
4. Everything else that was a search hit at all -> Optional.

No score is learned or tuned -- `relevance_score` is a plain keyword-hit
count computed by the caller before this function ever runs.
"""

from __future__ import annotations

from typing import Any

# Maps an Intent Engine intent to the Knowledge Core domain key it
# most directly corresponds to. Intents with no fixed domain (general
# guidance, workflow, configuration, unknown) intentionally map to
# None -- Knowledge Planner must not invent a domain match for them.
INTENT_TO_DOMAIN: dict[str, str | None] = {
    "dataset": "dataset_system",
    "training": "training_system",
    "tokenizer": "training_system",
    "instruction_tuning": "training_system",
    "evaluation": "training_system",
    "model_registry": "training_system",
    "inference_runtime": "training_system",
    "rag": "rag",
    "knowledge_routing": "rag",
    "admin_dashboard": "admin_dashboard",
    "architecture": "architecture",
    "documentation": None,
    "configuration": None,
    "workflow": None,
    "general_guidance": None,
    "unknown": None,
}


def plan_knowledge(
    items_with_scores: list[dict[str, Any]],
    *,
    intent: str,
    related_titles: set[str],
) -> dict[str, Any]:
    expected_domain = INTENT_TO_DOMAIN.get(intent)
    primary, supporting, optional, excluded = [], [], [], []

    for entry in items_with_scores:
        item = entry["item"]
        score = entry["relevance_score"]
        if item.get("status") == "deprecated":
            excluded.append(item["title"])
            continue
        domain_matches = expected_domain is not None and entry.get("domain_key") == expected_domain
        if domain_matches and score >= 2:
            primary.append((item["title"], score))
        elif domain_matches or item["title"] in related_titles:
            supporting.append((item["title"], score))
        else:
            optional.append((item["title"], score))

    primary.sort(key=lambda t: -t[1])
    supporting.sort(key=lambda t: -t[1])
    optional.sort(key=lambda t: -t[1])

    priority_order = [t for t, _ in primary] + [t for t, _ in supporting] + [t for t, _ in optional]

    return {
        "primary_knowledge": [t for t, _ in primary],
        "supporting_knowledge": [t for t, _ in supporting],
        "optional_knowledge": [t for t, _ in optional],
        "excluded_knowledge": excluded,
        "priority_order": priority_order,
        "expected_domain": expected_domain,
    }
