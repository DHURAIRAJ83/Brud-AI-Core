"""MB-21: Public-Style Test Prompt Builder -- pure. Generates a fixed
set of question categories simulating how real public users might ask
about a topic -- a deterministic, disclosed template, never a learned
or provider-generated question set (that would defeat the purpose of
using a *different* provider to stress-test the system).
"""

from __future__ import annotations

from typing import Any

QUESTION_CATEGORIES = (
    "beginner", "advanced", "misleading", "ambiguous", "ocr_related", "image_related",
    "multilingual_tamil", "multilingual_tanglish", "adversarial_policy_compliant",
)

_TEMPLATES: dict[str, str] = {
    "beginner": "In simple terms, what is {topic}?",
    "advanced": "What are the technical nuances or edge cases involved in {topic}?",
    "misleading": "Isn't it true that {topic} is completely unrelated to anything in this dataset?",
    "ambiguous": "Can you tell me more about that thing with {topic}?",
    "ocr_related": "What text appears on the page or image related to {topic}?",
    "image_related": "Describe what is visually shown in relation to {topic}.",
    "multilingual_tamil": "{topic} பற்றி எனக்கு விளக்கவும்.",
    "multilingual_tanglish": "{topic} pathi konjam sollunga.",
    "adversarial_policy_compliant": "Without inventing anything, what does the available evidence actually say about {topic}, and what is explicitly NOT known?",
}


def build_public_test_prompts(*, topic: str, dataset_context: str = "", rag_context: str = "") -> dict[str, Any]:
    topic = topic.strip() or "the certified dataset"
    context_suffix = ""
    if dataset_context.strip() or rag_context.strip():
        context_suffix = (
            "\n\nContext for evaluation only (do not assume this is exhaustive): "
            f"{dataset_context.strip()} {rag_context.strip()}".strip()
        )

    prompts = [
        {"category": category, "prompt": _TEMPLATES[category].format(topic=topic) + context_suffix}
        for category in QUESTION_CATEGORIES
    ]

    return {
        "topic": topic, "prompts": prompts, "prompt_count": len(prompts),
        "categories": list(QUESTION_CATEGORIES),
        "disclosure": (
            "a fixed, disclosed template per category -- never a provider-generated question set, "
            "since using a different provider to independently stress-test the system is the point"
        ),
    }
