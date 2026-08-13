"""MB-05.1: Knowledge Gap Analyzer -- important topics with ZERO
keyword hits anywhere in the dataset, each with an explicit WHY. A
fixed, disclosed reference list of "important" topics, deliberately
broader/flatter than Coverage Analyzer's per-domain taxonomy (a
dataset can have zero hits for a topic that isn't even in its primary
domain -- that is exactly the kind of gap this module exists to
surface).
"""

from __future__ import annotations

from typing import Any

IMPORTANT_TOPICS: dict[str, tuple[str, ...]] = {
    "Geometry": ("geometry", "triangle", "polygon", "euclidean"),
    "Astronomy": ("astronomy", "planet", "galaxy", "solar system", "orbit"),
    "Compiler": ("compiler", "lexer", "parser", "abstract syntax tree", "bytecode"),
    "Operating System": ("operating system", "kernel", "process scheduling", "file system", "memory management"),
    "Machine Learning": ("machine learning", "neural network", "gradient descent", "training data"),
    "Networking": ("tcp", "networking", "socket", "http protocol", "dns"),
    "Security": ("encryption", "cybersecurity", "vulnerability", "authentication"),
    "Statistics": ("standard deviation", "regression", "probability distribution", "hypothesis test"),
}


def _record_text(record: dict[str, Any]) -> str:
    parts = [record.get("instruction"), record.get("input_text"), record.get("output_text")]
    return "\n".join(part for part in parts if part).lower()


def analyze_knowledge_gaps(
    records: list[dict[str, Any]], *, topics: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    topics = topics if topics is not None else IMPORTANT_TOPICS
    texts = [_record_text(record) for record in records]

    missing: list[dict[str, str]] = []
    covered: list[dict[str, Any]] = []
    for topic, keywords in topics.items():
        hits = sum(1 for text in texts if any(keyword in text for keyword in keywords))
        if hits == 0:
            missing.append({"topic": topic, "reason": f"0 records mention any of: {', '.join(keywords)}"})
        else:
            covered.append({"topic": topic, "record_hits": hits})

    return {
        "missing_topics": missing, "covered_topics": covered, "gap_count": len(missing),
        "coverage_ratio": round(len(covered) / len(topics), 3) if topics else None,
    }
