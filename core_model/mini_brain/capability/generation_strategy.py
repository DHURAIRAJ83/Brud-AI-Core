"""MB-04C: Generation Strategy -- deterministic mapping from a
capability category + MB-03's own question_type to one of the 10
named strategies, each with a target token budget and a short
directive string.

The directive is appended to MB-04A's ALREADY-BUILT prompt text by
the capability service, AFTER MB-04A has finished building it -- this
module and its caller never call into or modify MB-04A's Prompt
Builder. Priority: question_type (the question's SHAPE) decides for
definition/comparison/troubleshooting/procedural questions regardless
of topic; capability category (the question's DOMAIN) decides
otherwise.
"""

from __future__ import annotations

from typing import Any

STRATEGIES: dict[str, dict[str, Any]] = {
    "short_answer": {
        "max_tokens": 64,
        "directive": "Provide a short, direct answer in 1-3 sentences.",
    },
    "detailed_answer": {
        "max_tokens": 220,
        "directive": "Provide a detailed, thorough answer.",
    },
    "step_by_step": {
        "max_tokens": 180,
        "directive": "List the steps in order, one per line, numbered.",
    },
    "explanation": {
        "max_tokens": 200,
        "directive": "Explain clearly and directly, using only the knowledge provided.",
    },
    "definition": {
        "max_tokens": 80,
        "directive": "Give a concise definition in 1-2 sentences.",
    },
    "comparison": {
        "max_tokens": 180,
        "directive": "Compare the items clearly, listing the key differences.",
    },
    "troubleshooting": {
        "max_tokens": 180,
        "directive": "Diagnose the likely cause and explain how to resolve it.",
    },
    "code": {
        "max_tokens": 220,
        "directive": "Answer with correct, concise code and a brief explanation.",
    },
    "architecture": {
        "max_tokens": 220,
        "directive": "Explain the architecture clearly, referencing the actual component names given.",
    },
    "workflow": {
        "max_tokens": 180,
        "directive": "Explain the workflow step by step, in the correct order.",
    },
}

_CATEGORY_TO_STRATEGY: dict[str, str] = {
    "coding": "code",
    "architecture": "architecture",
    "workflow": "workflow",
    "simple_question": "short_answer",
    "knowledge_question": "explanation",
    "dataset": "explanation",
    "training": "explanation",
    "rag": "explanation",
}

_QUESTION_TYPE_TO_STRATEGY: dict[str, str] = {
    "definition": "definition",
    "comparison": "comparison",
    "troubleshooting": "troubleshooting",
    "procedural": "step_by_step",
}


def select_strategy_name(*, category: str, question_type: str) -> str:
    if question_type in _QUESTION_TYPE_TO_STRATEGY:
        return _QUESTION_TYPE_TO_STRATEGY[question_type]
    return _CATEGORY_TO_STRATEGY.get(category, "detailed_answer")


def select_strategy(*, category: str, question_type: str) -> dict[str, Any]:
    name = select_strategy_name(category=category, question_type=question_type)
    strategy = dict(STRATEGIES[name])
    strategy["name"] = name
    return strategy
