"""MB-04C: Capability Selector -- deterministic categorization of a
question into one of 8 capability categories, used to pick a
Generation Strategy. Reuses MB-03's own intent (a strong, specific
domain signal, read via the Response Plan -- never re-derived) first;
falls back to a local, MB-04C-owned coding-keyword scan (same
independent-detection pattern MB-04A already established for its own
"coding" template category, since MB-03 has no coding intent); falls
back last to whether any Knowledge Core matches were actually found.
"""

from __future__ import annotations

CATEGORIES = (
    "simple_question", "knowledge_question", "coding", "workflow",
    "architecture", "dataset", "training", "rag",
)

# MB-03's own domain-specific intents map onto a capability category.
_DOMAIN_INTENT_MAP: dict[str, str] = {
    "dataset": "dataset",
    "training": "training",
    "tokenizer": "training",
    "instruction_tuning": "training",
    "evaluation": "training",
    "model_registry": "workflow",
    "inference_runtime": "architecture",
    "rag": "rag",
    "knowledge_routing": "rag",
    "workflow": "workflow",
    "architecture": "architecture",
    "admin_dashboard": "knowledge_question",
    "configuration": "knowledge_question",
    "documentation": "knowledge_question",
}

# A fresh, MB-04C-owned coding-keyword list -- not imported from
# MB-04A's own (separately-purposed) coding-template detector, to keep
# this module fully independent of MB-04A's internals.
_CODING_KEYWORDS = (
    "code", "function", "python", "javascript", "typescript", "endpoint",
    "api", "bug", "implement", "class ", "method", "script", "sql", "regex",
    "syntax", "compile", "exception", "traceback", "variable", "loop", "algorithm",
)


def _has_coding_signal(question: str) -> bool:
    text = question.lower()
    return any(keyword in text for keyword in _CODING_KEYWORDS)


def select_capability_category(*, intent: str, question: str, has_knowledge: bool) -> str:
    if intent in _DOMAIN_INTENT_MAP:
        return _DOMAIN_INTENT_MAP[intent]
    if _has_coding_signal(question):
        return "coding"
    if has_knowledge:
        return "knowledge_question"
    return "simple_question"
