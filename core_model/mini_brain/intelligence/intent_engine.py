"""Intent Engine -- deterministic keyword-based intent classification.

Exactly the 16 intents MB-03 specifies. Each intent has a fixed
trigger-keyword list; the question is scored against every intent by
counting keyword hits, and the highest-scoring intent wins. Ties are
broken by declaration order below (earlier wins), and a zero-score
question is classified `unknown` -- never guessed, never defaulted to
a plausible-sounding intent it didn't actually match.

This is intentionally the same shape as `decide_language()` in
`core_model/conversation/` and `AdminAssistantChatService`'s own
"deterministic path first" intent classification -- reused
architecture, not a new pattern invented for this phase.
"""

from __future__ import annotations

from typing import Any

INTENTS = (
    "dataset", "training", "tokenizer", "instruction_tuning", "evaluation",
    "model_registry", "inference_runtime", "rag", "knowledge_routing",
    "admin_dashboard", "configuration", "workflow", "architecture",
    "documentation", "general_guidance", "unknown",
)

# Ordered deliberately: more specific intents first, so a question
# mentioning both "dataset" and "tokenizer" (e.g. "does tokenizer
# training need a dataset version?") is scored on keyword count, not
# declaration order, but ties fall to the earlier (here: more
# specific) entry.
_INTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "tokenizer": ("tokenizer", "sentencepiece", "bpe", "vocab", "vocabulary"),
    "instruction_tuning": ("instruction tuning", "instruction-tuning", "sft", "fine-tune", "fine tune", "label masking"),
    "evaluation": ("evaluation", "evaluate", "fixture", "chat-readiness", "chat readiness", "benchmark"),
    "model_registry": ("model registry", "release candidate", "model release", "model card", "rollback"),
    "inference_runtime": ("inference runtime", "runtime profile", "assignment", "canary", "load model", "chat lab"),
    "rag": ("rag", "retrieval", "knowledge space", "embedding", "chunk", "citation", "vector index", "keyword index"),
    "knowledge_routing": ("knowledge routing", "route", "routing", "public chat", "trusted web", "knowledge gap"),
    "training": ("training", "pretraining", "pretrain", "checkpoint", "training worker"),
    "dataset": ("dataset", "sample", "corpus", "import", "duplicate", "quarantine", "licence", "license"),
    "admin_dashboard": ("dashboard", "page", "sidebar", "nav", "navigation", "widget", "ui", "button", "menu"),
    "configuration": ("config", "configuration", "setting", "settings", "env", "environment variable"),
    "workflow": ("workflow", "step", "next step", "process", "pipeline", "stage"),
    "architecture": ("architecture", "folder structure", "repository layer", "service layer", "pattern", "design"),
    "documentation": ("documentation", "docs", "readme", "doc file", "report"),
    "general_guidance": ("how do i", "how to", "what should i", "recommend", "best practice", "guidance", "help me"),
}


def detect_intent(question: str) -> dict[str, Any]:
    text = question.lower()
    scores: dict[str, int] = {}
    for intent, keywords in _INTENT_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in text)
        if hits:
            scores[intent] = hits

    if not scores:
        return {"intent": "unknown", "confidence_signal": 0, "matched_keywords": [], "scores": {}}

    best_intent = max(scores, key=lambda name: (scores[name], -list(_INTENT_KEYWORDS).index(name)))
    matched = [kw for kw in _INTENT_KEYWORDS[best_intent] if kw in text]
    return {
        "intent": best_intent,
        "confidence_signal": scores[best_intent],
        "matched_keywords": matched,
        "scores": scores,
    }
