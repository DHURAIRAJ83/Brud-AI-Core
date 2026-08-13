"""MB-05.1: Dataset Bias Analyzer -- Balanced / Slight Bias / Heavy
Bias across 5 dimensions, from a single, shared, explainable
"dominant share" formula. No hidden weights: the same
dominant-share-of-total rule applies to every dimension, with fixed,
disclosed thresholds.
"""

from __future__ import annotations

from typing import Any

BALANCED_MAX_SHARE = 0.5
SLIGHT_BIAS_MAX_SHARE = 0.75


def _verdict_for_distribution(counts: dict[str, int]) -> dict[str, Any]:
    total = sum(counts.values())
    if not total:
        return {"verdict": "Balanced", "dominant": None, "dominant_share": 0.0, "reason": "no data available for this dimension"}

    dominant_key, dominant_count = max(counts.items(), key=lambda kv: kv[1])
    share = dominant_count / total

    if share <= BALANCED_MAX_SHARE:
        verdict = "Balanced"
    elif share <= SLIGHT_BIAS_MAX_SHARE:
        verdict = "Slight Bias"
    else:
        verdict = "Heavy Bias"

    return {
        "verdict": verdict,
        "dominant": dominant_key,
        "dominant_share": round(share, 3),
        "reason": f"'{dominant_key}' accounts for {round(share * 100, 1)}% of records (threshold: Balanced <= {BALANCED_MAX_SHARE * 100:.0f}%, Slight Bias <= {SLIGHT_BIAS_MAX_SHARE * 100:.0f}%)",
    }


def analyze_bias(
    *, records: list[dict[str, Any]], language_counts: dict[str, int],
    record_type_counts: dict[str, int], domain_topic_scores: dict[str, float],
) -> dict[str, Any]:
    category_counts: dict[str, int] = {}
    for record in records:
        category = (record.get("metadata") or {}).get("topic") or (record.get("metadata") or {}).get("category")
        if category:
            category_counts[category] = category_counts.get(category, 0) + 1

    chat_records = sum(1 for r in records if r.get("record_type") == "chat")
    non_chat_records = len(records) - chat_records

    nonzero_topics = {topic: score for topic, score in domain_topic_scores.items() if score > 0}

    return {
        "language_balance": _verdict_for_distribution(language_counts),
        "instruction_balance": _verdict_for_distribution(record_type_counts),
        "conversation_balance": _verdict_for_distribution({"chat": chat_records, "non_chat": non_chat_records}),
        "domain_balance": _verdict_for_distribution(nonzero_topics),
        "category_balance": _verdict_for_distribution(category_counts),
    }
