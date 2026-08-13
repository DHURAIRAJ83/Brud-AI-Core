"""MB-05.1: Dataset Coverage Analyzer -- Covered / Weak / Missing
subtopics within each domain, against a fixed, disclosed reference
taxonomy. No AI, no semantic search: every match is a literal keyword
substring check, same discipline as MB-03's/MB-04A's/MB-05's own
keyword-based classifiers. The taxonomy is illustrative, not
exhaustive -- a real gap, disclosed here and in the completion report,
not hidden.
"""

from __future__ import annotations

from typing import Any

COVERAGE_TAXONOMY: dict[str, dict[str, tuple[str, ...]]] = {
    "Programming": {
        "Python": ("python", "pip install", "django", "flask"),
        "Java": ("java ", "jvm", "spring boot"),
        "JavaScript": ("javascript", "node.js", "react", "typescript"),
        "Go": ("golang", "goroutine"),
        "Rust": ("rust ", "cargo build", "borrow checker"),
        "Networking": ("tcp", "udp", "networking", "socket programming", "dns"),
        "Databases": ("sql query", "database", "postgres", "mysql"),
    },
    "Math": {
        "Algebra": ("algebra", "equation", "polynomial"),
        "Geometry": ("geometry", "triangle", "polygon"),
        "Calculus": ("calculus", "derivative", "integral"),
        "Statistics": ("standard deviation", "regression", "probability distribution"),
    },
    "Science": {
        "Physics": ("physics", "gravity", "thermodynamics"),
        "Chemistry": ("chemistry", "chemical reaction", "molecule"),
        "Biology": ("biology", "organism", "photosynthesis"),
        "Astronomy": ("astronomy", "planet", "galaxy", "solar system"),
    },
    "Computer Science": {
        "Operating Systems": ("operating system", "kernel", "process scheduling"),
        "Compilers": ("compiler", "lexer", "abstract syntax tree"),
        "Machine Learning": ("machine learning", "neural network", "gradient descent"),
        "Algorithms": ("algorithm", "time complexity", "data structure"),
    },
}

MIN_HITS_FOR_COVERED = 3
MIN_HITS_FOR_WEAK = 1
MAX_MATCHED_IDS_STORED = 50


def _record_text(record: dict[str, Any]) -> str:
    parts = [record.get("instruction"), record.get("input_text"), record.get("output_text")]
    return "\n".join(part for part in parts if part).lower()


def analyze_coverage(
    records: list[dict[str, Any]], *, taxonomy: dict[str, dict[str, tuple[str, ...]]] | None = None,
) -> dict[str, Any]:
    taxonomy = taxonomy if taxonomy is not None else COVERAGE_TAXONOMY
    texts = [(record.get("public_id"), _record_text(record)) for record in records]

    result: dict[str, Any] = {}
    for domain, subtopics in taxonomy.items():
        subtopic_results = {}
        for subtopic, keywords in subtopics.items():
            matched_ids = [pid for pid, text in texts if any(keyword in text for keyword in keywords)]
            hits = len(matched_ids)
            if hits >= MIN_HITS_FOR_COVERED:
                status = "Covered"
            elif hits >= MIN_HITS_FOR_WEAK:
                status = "Weak"
            else:
                status = "Missing"
            subtopic_results[subtopic] = {
                "status": status, "record_hits": hits, "matched_record_ids": matched_ids[:MAX_MATCHED_IDS_STORED],
            }
        covered_count = sum(1 for s in subtopic_results.values() if s["status"] == "Covered")
        coverage_percent = round(covered_count / len(subtopics) * 100, 1) if subtopics else 0.0
        result[domain] = {"subtopics": subtopic_results, "coverage_percent": coverage_percent}

    return result
