"""Injection detection for conversation history, summaries, and memory
content entering chat orchestration context.

Reuses Phase 16's bounded, context-aware RAG injection filter unchanged
for the categories it already covers, and adds conversation-memory-
specific categories (changing memory policy, deleting logs, retrieving
another participant's data) that RAG evidence never needed to consider.
Memory and prior conversation text are always treated as data, never as
authority -- a match here means the item is excluded from context, not
that the request itself is rejected.
"""

from __future__ import annotations

import re

from core_model.rag.injection_filter import classify_injection_status, detect_injection_signals

_MEMORY_SPECIFIC_PATTERNS = {
    "change_memory_policy": re.compile(r"change (the )?memory policy", re.IGNORECASE),
    "delete_logs": re.compile(r"delete (the )?(logs|audit)", re.IGNORECASE),
    "cross_participant_retrieval": re.compile(
        r"retrieve (another|other) (user|participant)'?s? (data|memory)", re.IGNORECASE
    ),
    "store_secrets_directive": re.compile(
        r"store (this|these|my) (secret|password|api key)", re.IGNORECASE
    ),
}


def detect_conversation_injection_signals(text: str) -> dict[str, object]:
    base = detect_injection_signals(text)
    extra_matches = [
        name for name, pattern in _MEMORY_SPECIFIC_PATTERNS.items() if pattern.search(text)
    ]
    return {"matched_categories": sorted({*base["matched_categories"], *extra_matches})}


def classify_conversation_injection_status(
    matched_categories: list[str], *, policy: str = "block"
) -> str:
    return classify_injection_status(matched_categories, policy=policy)


def assess_context_item_injection(text: str) -> dict[str, object]:
    signals = detect_conversation_injection_signals(text)
    status = classify_conversation_injection_status(signals["matched_categories"])
    return {"injection_status": status, "matched_categories": signals["matched_categories"]}
