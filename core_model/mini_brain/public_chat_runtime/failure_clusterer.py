"""MB-23: Failure Clusterer -- pure. Groups an already-fetched list of
feedback-signal rows by their exact `topic_key` -- a disclosed
heuristic, never a semantic-similarity model. Two paraphrases that
`query_classifier.normalize_topic_key()` happens to normalize to
different keys will not be merged into the same cluster; this is
stated explicitly rather than silently implied to be smarter than it
is.
"""

from __future__ import annotations

from typing import Any

_SEVERITY_KEYS = ("low", "medium", "high")


def cluster_failures(*, signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    clusters: dict[str, dict[str, Any]] = {}

    for signal in signals:
        key = signal["topic_key"]
        cluster = clusters.setdefault(key, {
            "topic_key": key, "frequency": 0, "session_ids": set(),
            "severity_counts": {k: 0 for k in _SEVERITY_KEYS},
            "signal_type_counts": {}, "most_recent_at": None, "example_texts": [],
        })
        cluster["frequency"] += 1
        cluster["session_ids"].add(signal["session_id"])
        cluster["severity_counts"][signal["severity"]] = cluster["severity_counts"].get(signal["severity"], 0) + 1
        cluster["signal_type_counts"][signal["signal_type"]] = (
            cluster["signal_type_counts"].get(signal["signal_type"], 0) + 1
        )
        if signal["normalized_text"] not in cluster["example_texts"]:
            cluster["example_texts"].append(signal["normalized_text"])
        if cluster["most_recent_at"] is None or signal["created_at"] > cluster["most_recent_at"]:
            cluster["most_recent_at"] = signal["created_at"]

    results = []
    for cluster in clusters.values():
        results.append({
            "topic_key": cluster["topic_key"], "frequency": cluster["frequency"],
            "distinct_session_count": len(cluster["session_ids"]),
            "severity_counts": cluster["severity_counts"],
            "signal_type_counts": cluster["signal_type_counts"],
            "most_recent_at": cluster["most_recent_at"],
            "example_texts": cluster["example_texts"][:5],
        })

    results.sort(key=lambda c: (c["frequency"], c["distinct_session_count"]), reverse=True)
    return results
