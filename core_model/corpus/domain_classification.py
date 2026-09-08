"""Deterministic, rule-based domain classification.

Corpus organization metadata only -- never an expert certification of
subject-matter accuracy, and never a call to an external AI API. Every
decision is backed by explicit keyword/pattern evidence that is
persisted alongside the classification.
"""

from __future__ import annotations

from typing import Any

CLASSIFIER_VERSION = "v1"

# Bounded, explicit keyword evidence per domain -- English and
# transliterated-Tamil (Tanglish) markers only, never a machine-learned
# embedding classifier. Order matters: earlier domains win ties.
_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "grammar": ("grammar", "conjugation", "vibhakti", "verb form", "tense"),
    "dictionary": ("meaning:", "definition:", "synonym", "பொருள்"),
    "education": ("lesson", "exercise", "textbook", "syllabus", "பாடம்"),
    "literature": ("poem", "novel", "short story", "verse", "இலக்கியம்"),
    "conversation": ("hello", "how are you", "vanakkam", "நீங்கள் எப்படி"),
    "translation": ("translate", "translation", "மொழிபெயர்"),
    "government": ("government", "ministry", "notification", "gazette", "அரசு"),
    "history": ("history", "century", "dynasty", "ancient", "வரலாறு"),
    "science": ("hypothesis", "experiment", "physics", "chemistry", "biology"),
    "mathematics": ("equation", "theorem", "calculus", "algebra", "கணிதம்"),
    "technology": ("software", "computer", "algorithm", "internet", "தொழில்நுட்பம்"),
    "agriculture": ("crop", "farming", "irrigation", "விவசாயம்"),
    "business": ("invoice", "revenue", "marketing", "business", "வணிகம்"),
    "health_general": ("symptom", "treatment", "hospital", "health", "மருத்துவம்"),
    "law_general": ("statute", "court", "legal", "law", "சட்டம்"),
    "religion_cultural": ("temple", "festival", "ritual", "religion", "கோவில்"),
    "children": ("children's story", "kids", "fairy tale", "குழந்தைகள்"),
    "faq": ("frequently asked", "faq", "q:", "question:"),
    "safety": ("warning:", "danger", "hazard", "safety instructions"),
    "code": ("def ", "function ", "import ", "class "),
}


def classify_domain(
    text: str,
    llm_suggestion: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Classify domain taxonomy combining heuristic rules + LLM reasoning."""
    lowered = text.lower()
    evidence: dict[str, list[str]] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        hits = [keyword for keyword in keywords if keyword.lower() in lowered]
        if hits:
            evidence[domain] = hits

    if not evidence and not llm_suggestion:
        return {
            "primary_domain": "general",
            "secondary_domains": [],
            "rule_evidence": {},
            "confidence": 0.3,
            "review_required": True,
            "classifier_version": CLASSIFIER_VERSION,
            "method": "heuristic_default"
        }

    if evidence:
        ranked = sorted(evidence.items(), key=lambda item: len(item[1]), reverse=True)
        primary_domain = ranked[0][0]
        secondary_domains = [domain for domain, _ in ranked[1:4]]
        confidence = min(1.0, 0.4 + 0.15 * len(ranked[0][1]))
        method = "heuristic"
    else:
        primary_domain = llm_suggestion.get("primary_domain", "general") if llm_suggestion else "general"
        secondary_domains = llm_suggestion.get("secondary_domains", []) if llm_suggestion else []
        confidence = float(llm_suggestion.get("confidence", 0.7)) if llm_suggestion else 0.5
        method = "llm_advisor"

    # Merge LLM advisory suggestion if available
    if llm_suggestion and evidence:
        llm_domain = llm_suggestion.get("primary_domain")
        if llm_domain and llm_domain == primary_domain:
            confidence = min(1.0, confidence + 0.15)
            method = "heuristic+llm_consensus"
        elif llm_domain and llm_domain in secondary_domains:
            method = "heuristic+llm_partial"
        else:
            confidence = max(0.4, confidence - 0.1)
            method = "heuristic+llm_disagreement"

    review_required = confidence < 0.80

    return {
        "primary_domain": primary_domain,
        "secondary_domains": secondary_domains,
        "rule_evidence": evidence,
        "confidence": round(confidence, 2),
        "review_required": review_required,
        "review_reason": "Low confidence classification (<0.80)" if review_required else None,
        "classifier_version": CLASSIFIER_VERSION,
        "method": method,
    }
