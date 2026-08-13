"""MB-23: Query Classifier -- pure. A lightweight, disclosed-heuristic
categorizer used only for MB-23's own topic bookkeeping (clustering,
candidate topics) -- it never decides how a message is actually
routed or answered. The real routing decision is made independently
by `KnowledgeRoutingClassificationService` / `PublicChatRoutingService`
(Phase 18-20); this module only reads the raw query text a second
time, after the fact, to derive a stable topic key and a coarse
category for MB-23's own analytics.
"""

from __future__ import annotations

import re
from typing import Any

_VISION_KEYWORDS = ("image", "photo", "picture", "screenshot", "diagram", "看", "படம்")
_TOOL_KEYWORDS = ("calculate", "convert", "how many days", "what time", "sum of", "average of")
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "do", "does", "did", "please", "can", "you",
    "i", "me", "my", "to", "of", "in", "on", "for", "and", "or", "what", "how", "why", "when",
})


def classify_query(*, text: str) -> dict[str, Any]:
    lowered = text.lower()
    if any(keyword in lowered for keyword in _VISION_KEYWORDS):
        category = "vision"
    elif any(keyword in lowered for keyword in _TOOL_KEYWORDS):
        category = "tool"
    elif "?" in text:
        category = "factual"
    else:
        category = "other"
    return {
        "category": category,
        "disclosure": "a coarse, keyword-based heuristic for MB-23's own topic bookkeeping only -- never used to route or answer the message itself",
    }


def normalize_topic_key(*, text: str, max_words: int = 8) -> str:
    lowered = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    words = [w for w in lowered.split() if w and w not in _STOPWORDS]
    if not words:
        words = [w for w in lowered.split() if w]
    return " ".join(words[:max_words]) or "unclassified"
