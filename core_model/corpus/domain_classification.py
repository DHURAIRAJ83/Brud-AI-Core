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


def classify_domain(text: str) -> dict[str, Any]:
    lowered = text.lower()
    evidence: dict[str, list[str]] = {}
    for domain, keywords in _DOMAIN_KEYWORDS.items():
        hits = [keyword for keyword in keywords if keyword.lower() in lowered]
        if hits:
            evidence[domain] = hits

    if not evidence:
        return {
            "primary_domain": "general",
            "secondary_domains": [],
            "rule_evidence": {},
            "confidence": 0.3,
            "classifier_version": CLASSIFIER_VERSION,
        }

    ranked = sorted(evidence.items(), key=lambda item: len(item[1]), reverse=True)
    primary_domain = ranked[0][0]
    secondary_domains = [domain for domain, _ in ranked[1:4]]
    confidence = min(1.0, 0.4 + 0.15 * len(ranked[0][1]))

    return {
        "primary_domain": primary_domain,
        "secondary_domains": secondary_domains,
        "rule_evidence": evidence,
        "confidence": confidence,
        "classifier_version": CLASSIFIER_VERSION,
    }
