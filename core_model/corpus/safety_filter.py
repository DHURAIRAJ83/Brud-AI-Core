"""Corpus safety filtering.

The presence of safety-related educational text does not automatically
mean it must be deleted -- this module always classifies a match into
one of five behavior classes (descriptive, educational, historical,
preventive, operational_harmful) before deciding a status, reusing
Phase 16's ``core_model.rag.injection_filter`` pattern-detection
approach unchanged for the underlying category matching.
"""

from __future__ import annotations

import re
from typing import Any

_CATEGORY_PATTERNS: dict[str, re.Pattern[str]] = {
    "explicit_violence": re.compile(
        r"\b(graphic violence|brutal attack|torture scene)\b", re.IGNORECASE
    ),
    "self_harm": re.compile(
        r"\b(self[- ]harm|suicide method|how to end my life)\b", re.IGNORECASE
    ),
    "illegal_instructions": re.compile(r"\b(how to (rob|steal|hack into))\b", re.IGNORECASE),
    "weapon_construction": re.compile(
        r"\b(how to (build|make) a (bomb|gun|explosive))\b", re.IGNORECASE
    ),
    "malware_instructions": re.compile(
        r"\b(write (a )?(virus|malware|ransomware) code)\b", re.IGNORECASE
    ),
    "credential_theft": re.compile(
        r"\b(how to (steal|phish) (passwords|credentials))\b", re.IGNORECASE
    ),
    "hate_harassment": re.compile(
        r"\b(hate speech|racial slur|harass\w* campaign)\b", re.IGNORECASE
    ),
    "sexual_content": re.compile(
        r"\b(explicit sexual content|sexually explicit)\b", re.IGNORECASE
    ),
    "exploitative_content": re.compile(
        r"\b(child exploitation|human trafficking instructions)\b", re.IGNORECASE
    ),
    "high_risk_medical": re.compile(
        r"\b(self[- ]medicate with|lethal dose of)\b", re.IGNORECASE
    ),
    "high_risk_financial": re.compile(
        r"\b(guaranteed investment scheme|evade taxes by)\b", re.IGNORECASE
    ),
}

# Markers that shift an otherwise-flagged match toward a non-operational
# behavior class -- never a full semantic classifier, just bounded,
# explicit context words.
_DESCRIPTIVE_MARKERS = ("described", "depicted", "in the novel", "in the story")
_EDUCATIONAL_MARKERS = (
    "for educational purposes", "students should understand", "this lesson explains",
)
_HISTORICAL_MARKERS = ("historically", "in ancient times", "during the war", "in history")
_PREVENTIVE_MARKERS = ("to prevent", "warning signs of", "how to avoid", "seek help if")


def classify_behavior(text: str, matched_category: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in _PREVENTIVE_MARKERS):
        return "preventive"
    if any(marker in lowered for marker in _HISTORICAL_MARKERS):
        return "historical"
    if any(marker in lowered for marker in _EDUCATIONAL_MARKERS):
        return "educational"
    if any(marker in lowered for marker in _DESCRIPTIVE_MARKERS):
        return "descriptive"
    return "operational_harmful"


def assess_safety(text: str) -> dict[str, Any]:
    findings = []
    for category, pattern in _CATEGORY_PATTERNS.items():
        if pattern.search(text):
            behavior_class = classify_behavior(text, category)
            findings.append({"category": category, "behavior_class": behavior_class})

    if not findings:
        return {"status": "safe", "findings": []}

    operational = [f for f in findings if f["behavior_class"] == "operational_harmful"]
    status = "blocked" if operational else "flagged"
    return {"status": status, "findings": findings}
