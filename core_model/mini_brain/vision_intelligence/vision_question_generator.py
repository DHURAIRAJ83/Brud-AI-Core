"""MB-14: Vision Question Generator -- pure. Templated educational QA
built from the already-admin-annotated objects and caption -- never a
generative model. Always `verified: false`.
"""

from __future__ import annotations

from typing import Any

MAX_QUESTIONS = 50


def generate_questions(*, objects: list[dict[str, Any]], caption: str | None) -> dict[str, Any]:
    questions: list[dict[str, Any]] = []

    if caption:
        questions.append({"question": "What is shown in this image?", "answer_hint": caption, "verified": False})

    for obj in objects:
        questions.append({
            "question": f"Where is the {obj['label']} located?",
            "answer_hint": obj.get("bounding_box"), "verified": False,
        })

    label_counts: dict[str, int] = {}
    for obj in objects:
        label_counts[obj["label"]] = label_counts.get(obj["label"], 0) + 1
    for label, count in label_counts.items():
        if count > 1:
            questions.append({
                "question": f"How many {label}(s) are shown?", "answer_hint": str(count), "verified": False,
            })

    return {
        "questions": questions[:MAX_QUESTIONS], "question_count": min(len(questions), MAX_QUESTIONS),
        "verified": False,
    }
