"""MB-05: Domain Classifier -- deterministic, keyword/structure/
language-based classification into exactly one of 14 categories.
Genuinely new: nothing in the existing codebase classifies a Dataset
Studio source into a topic domain like this. No AI, no embeddings --
every decision is a literal keyword match, a record_type proportion,
or a language percentage, in a fixed priority order, always with a
stated reason.

Priority (most specific signal wins): topic keyword coverage across
records, then record_type structural dominance, then language
dominance, then "General" as the final fallback.
"""

from __future__ import annotations

from typing import Any

CATEGORIES = (
    "General", "Tamil", "English", "Math", "Science", "History", "Programming",
    "Reasoning", "Conversation", "Instruction", "Coding", "RAG", "Training", "Mixed",
)

_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Math": ("equation", "algebra", "geometry", "calculus", "theorem", "integral", "derivative", "matrix", "probability distribution", "trigonometry"),
    "Science": ("physics", "chemistry", "biology", "molecule", "organism", "chemical reaction", "hypothesis", "gravity", "photosynthesis", "ecosystem"),
    "History": ("century", "empire", "revolution", "dynasty", "ancient", "medieval", "historical", "colonial", "independence movement"),
    "Programming": ("algorithm", "data structure", "time complexity", "software engineering", "compiler", "runtime environment", "design pattern"),
    "Coding": ("function(", "def ", "import ", "class ", "variable", "syntax error", "python", "javascript", "```", "compile"),
    "Reasoning": ("therefore", "because", "logically", "deduce", "infer", "conclusion", "premise", "if...then", "step by step reasoning"),
    "RAG": ("retrieval", "citation", "chunk", "embedding", "knowledge base", "context window", "source document", "retrieved passage"),
}

_RECORD_TYPE_TO_CATEGORY: dict[str, str] = {
    "pretrain": "Training",
    "chat": "Conversation",
    "instruction": "Instruction",
    "translation": "Mixed",
    "tanglish_pair": "Mixed",
    "safety": "Instruction",
    "preference": "Instruction",
}

MIN_TOPIC_HIT_RATIO = 0.15
MIN_RECORD_TYPE_DOMINANCE = 0.6
MIN_LANGUAGE_DOMINANCE = 70.0
MAX_COMBINED_MINOR_LANGUAGE_SHARE = 90.0


def _record_text(record: dict[str, Any]) -> str:
    parts = [record.get("instruction"), record.get("input_text"), record.get("output_text")]
    return "\n".join(part for part in parts if part).lower()


def classify_domain(
    *, records: list[dict[str, Any]], language_percentages: dict[str, float], record_type_counts: dict[str, int],
) -> dict[str, Any]:
    total = len(records)
    if total == 0:
        return {"category": "General", "reason": "no records to classify", "topic_scores": {}}

    topic_hits = {topic: 0 for topic in _TOPIC_KEYWORDS}
    for record in records:
        text = _record_text(record)
        for topic, keywords in _TOPIC_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                topic_hits[topic] += 1

    topic_ratios = {topic: count / total for topic, count in topic_hits.items()}
    topic_scores = {topic: round(ratio * 100, 1) for topic, ratio in topic_ratios.items()}

    best_topic = max(topic_ratios, key=lambda t: topic_ratios[t])
    if topic_ratios[best_topic] >= MIN_TOPIC_HIT_RATIO:
        return {
            "category": best_topic,
            "reason": (
                f"{topic_scores[best_topic]}% of records contain {best_topic} keywords, "
                f"at or above the {MIN_TOPIC_HIT_RATIO * 100:.0f}% threshold"
            ),
            "topic_scores": topic_scores,
        }

    total_typed = sum(record_type_counts.values()) or 1
    dominant_type, dominant_count = max(
        record_type_counts.items(), key=lambda kv: kv[1], default=(None, 0),
    )
    if dominant_type and dominant_count / total_typed >= MIN_RECORD_TYPE_DOMINANCE:
        mapped = _RECORD_TYPE_TO_CATEGORY.get(dominant_type)
        if mapped:
            share = round(dominant_count / total_typed * 100, 1)
            return {
                "category": mapped,
                "reason": (
                    f"{share}% of records are record_type '{dominant_type}', at or above the "
                    f"{MIN_RECORD_TYPE_DOMINANCE * 100:.0f}% threshold"
                ),
                "topic_scores": topic_scores,
            }

    tamil_pct = language_percentages.get("tamil", 0.0)
    english_pct = language_percentages.get("english", 0.0)
    if tamil_pct >= MIN_LANGUAGE_DOMINANCE:
        return {"category": "Tamil", "reason": f"{tamil_pct}% of records are Tamil-language", "topic_scores": topic_scores}
    if english_pct >= MIN_LANGUAGE_DOMINANCE:
        return {"category": "English", "reason": f"{english_pct}% of records are English-language", "topic_scores": topic_scores}
    if (tamil_pct + english_pct) < MAX_COMBINED_MINOR_LANGUAGE_SHARE:
        return {
            "category": "Mixed",
            "reason": (
                f"no single language dominates (Tamil {tamil_pct}%, English {english_pct}%, "
                f"remainder split across Tanglish/mixed/unknown)"
            ),
            "topic_scores": topic_scores,
        }

    return {
        "category": "General",
        "reason": "no topic keyword, record-type, or language signal reached its threshold",
        "topic_scores": topic_scores,
    }
