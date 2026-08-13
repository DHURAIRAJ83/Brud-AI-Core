"""MB-04A: prompt template selection -- deterministic lookup, never a
model call. Ten task-requested categories (Definition, How-to,
Troubleshooting, Architecture, Dataset, Training, RAG, Workflow,
Coding, Admin Dashboard) plus a Default fallback.

Selection prefers MB-03's own intent (a strong, specific domain
signal) first; falls back to a locally-scanned coding-keyword signal
(MB-03 has no "coding" intent of its own -- this is new, additive
detection living entirely in this module, not a change to MB-03);
falls back last to MB-03's question_type (the question's shape, not
its topic).
"""

from __future__ import annotations

TEMPLATES: dict[str, str] = {
    "definition": (
        "Explain clearly what the subject of the question is, using only the "
        "Knowledge provided below. Be precise and factual."
    ),
    "howto": (
        "Explain the concrete steps needed to accomplish what the Admin is asking, "
        "in the correct order, using only the Knowledge and Workflow provided below."
    ),
    "troubleshooting": (
        "Diagnose the likely cause described in the question and explain how to "
        "resolve it, using only the Knowledge provided below. If the Knowledge does "
        "not cover the specific failure, say so plainly."
    ),
    "architecture": (
        "Explain the relevant system architecture or design, using only the "
        "Knowledge provided below. Reference the actual module or service names given."
    ),
    "dataset": (
        "Explain the Dataset System behavior relevant to this question, using only "
        "the Knowledge and Workflow provided below."
    ),
    "training": (
        "Explain the Training System behavior relevant to this question, using only "
        "the Knowledge and Workflow provided below. Never claim to start, resume, or "
        "execute training yourself."
    ),
    "rag": (
        "Explain the RAG (Retrieval-Augmented Generation) System behavior relevant "
        "to this question, using only the Knowledge provided below."
    ),
    "workflow": (
        "Explain the relevant workflow step-by-step, using the Workflow and "
        "Knowledge provided below, in the correct order."
    ),
    "coding": (
        "Answer the coding-related question directly and concisely, using the "
        "Knowledge provided below where relevant. If the Knowledge does not cover "
        "this, say so plainly rather than inventing an answer."
    ),
    "admin_dashboard": (
        "Explain the relevant Admin Dashboard feature, page, or setting, using only "
        "the Knowledge provided below."
    ),
    "default": (
        "Answer the Admin's question as accurately and concisely as possible, using "
        "only the Knowledge provided below. If the Knowledge does not cover it, say "
        "so plainly rather than guessing."
    ),
}

# MB-03's own domain-specific intents map straight onto a template
# category. Non-specific intents ("unknown", "general_guidance") are
# deliberately absent here -- they fall through to the coding-keyword
# check and then the question_type table below.
DOMAIN_INTENT_TEMPLATE: dict[str, str] = {
    "dataset": "dataset",
    "training": "training",
    "tokenizer": "training",
    "instruction_tuning": "training",
    "evaluation": "training",
    "model_registry": "workflow",
    "inference_runtime": "architecture",
    "rag": "rag",
    "knowledge_routing": "rag",
    "admin_dashboard": "admin_dashboard",
    "configuration": "admin_dashboard",
    "workflow": "workflow",
    "architecture": "architecture",
    "documentation": "definition",
}

QUESTION_TYPE_TEMPLATE: dict[str, str] = {
    "definition": "definition",
    "howto": "howto",
    "troubleshooting": "troubleshooting",
    "procedural": "howto",
    "comparison": "definition",
    "status": "default",
    "temporal": "default",
    "location": "default",
    "general": "default",
    "statement": "default",
}

# Additive, local-only signal: MB-03 has no "coding" intent, so this
# module scans the raw question text itself for coding vocabulary.
# This does not modify or read from MB-03 -- it is a second, entirely
# independent literal-substring check.
_CODING_KEYWORDS = (
    "code", "function", "python", "javascript", "typescript", "endpoint",
    "api", "bug", "implement", "class ", "method", "script", "sql", "regex",
    "syntax", "compile", "exception", "traceback", "variable", "loop", "algorithm",
)


def has_coding_signal(question: str) -> bool:
    text = question.lower()
    return any(keyword in text for keyword in _CODING_KEYWORDS)


def select_template_category(*, intent: str, question_type: str, question: str) -> str:
    if intent in DOMAIN_INTENT_TEMPLATE:
        return DOMAIN_INTENT_TEMPLATE[intent]
    if has_coding_signal(question):
        return "coding"
    return QUESTION_TYPE_TEMPLATE.get(question_type, "default")


def template_text(category: str) -> str:
    return TEMPLATES.get(category, TEMPLATES["default"])
