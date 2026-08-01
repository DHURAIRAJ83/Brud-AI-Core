"""Deterministic, rule-based intent classification for the Admin
Assistant (Phase 8) -- never an LLM call. A small, explicit, bilingual
keyword lexicon, same spirit as `core_model.rag.language_routing`'s
Tanglish lexicon: bounded and auditable rather than a black box.

Every read-only capability (page help, pending-work summary,
navigation) must be answerable without an LLM at all (plan.md section
6) -- this module is what decides *which* deterministic capability a
free-text message maps to, before any LLM is considered.
"""

from __future__ import annotations

from dataclasses import dataclass

from core_model.admin_assistant.dashboard_registry import DASHBOARD_PAGES

INTENTS = ("greeting", "help", "pending_work", "navigation", "open_ended")

_GREETING_WORDS = ("hi", "hello", "hey", "vanakkam", "வணக்கம்", "vanakam", "helo")

_HELP_WORDS = (
    "help", "guide", "how do", "explain", "what is", "what does", "purpose", "tutorial",
    "உதவி", "எப்படி", "விளக்கு", "வழிகாட்டி", "epdi", "eppadi", "purinjikitu",
)

_PENDING_WORK_WORDS = (
    "pending", "status", "overview", "summary", "todo", "queue", "blocked", "blocker",
    "நிலுவை", "கண்ணோட்டம்", "சுருக்கம்", "தடை",
)

_NAVIGATION_WORDS = (
    "take me", "show me", "go to", "open the", "navigate", "செல்", "திற", "காட்டு", "kondupo",
)

# Short-message threshold: a bare page-name mention ("Corpus Builder",
# "Datasets") is treated as an implicit help request only when the whole
# message is brief -- inside a longer analytical question, mentioning a
# page name is not itself a help request.
_SHORT_MESSAGE_TOKEN_LIMIT = 6


@dataclass(frozen=True)
class IntentResult:
    intent: str
    matched_page_id: str | None
    matched_keywords: tuple[str, ...]


def _token_count(message: str) -> int:
    return len([token for token in message.split() if token.strip()])


def _hits(message_lower: str, lexicon: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(word for word in lexicon if word in message_lower)


def _matching_page_id(message_lower: str) -> str | None:
    for page in DASHBOARD_PAGES:
        for label in (page.title.get("en", ""), page.title.get("ta", ""), page.nav_key):
            if label and label.lower() in message_lower:
                return page.page_id
    return None


def classify_intent(message: str) -> IntentResult:
    message_lower = message.lower()
    token_count = _token_count(message)
    matched_page_id = _matching_page_id(message_lower)

    greeting_hits = _hits(message_lower, _GREETING_WORDS)
    if greeting_hits and token_count <= 4:
        return IntentResult("greeting", matched_page_id, greeting_hits)

    navigation_hits = _hits(message_lower, _NAVIGATION_WORDS)
    if navigation_hits and matched_page_id is not None:
        return IntentResult("navigation", matched_page_id, navigation_hits)

    pending_hits = _hits(message_lower, _PENDING_WORK_WORDS)
    if pending_hits:
        return IntentResult("pending_work", matched_page_id, pending_hits)

    help_hits = _hits(message_lower, _HELP_WORDS)
    if help_hits or (matched_page_id is not None and token_count <= _SHORT_MESSAGE_TOKEN_LIMIT):
        return IntentResult("help", matched_page_id, help_hits)

    return IntentResult("open_ended", matched_page_id, ())
