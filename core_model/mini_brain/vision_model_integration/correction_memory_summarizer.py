"""MB-15: Correction Memory summary -- pure. Aggregates already-
recorded correction-memory rows (one row per admin correction, written
by the service, never here) into counts by action and the most
frequent wrong-label -> correct-label pairs, for the Admin Review and
Reports sub-tabs. Never modifies a correction record -- the memory
table itself is permanent and insert-only.
"""

from __future__ import annotations

from typing import Any


def summarize_corrections(*, corrections: list[dict[str, Any]]) -> dict[str, Any]:
    action_counts: dict[str, int] = {}
    label_pair_counts: dict[str, int] = {}
    for correction in corrections:
        action_counts[correction["action"]] = action_counts.get(correction["action"], 0) + 1
        if correction.get("wrong_label") and correction.get("correct_label"):
            pair = f"{correction['wrong_label']} -> {correction['correct_label']}"
            label_pair_counts[pair] = label_pair_counts.get(pair, 0) + 1

    top_pairs = sorted(label_pair_counts.items(), key=lambda item: item[1], reverse=True)[:10]
    return {
        "total_corrections": len(corrections),
        "action_counts": action_counts,
        "most_frequent_wrong_to_correct_labels": [{"pair": pair, "count": count} for pair, count in top_pairs],
    }
