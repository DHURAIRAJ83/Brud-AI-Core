"""Structured-record adapters (Step 13).

The pipeline's `classify()` only accepts free text. Real RAG records,
dataset candidates, training candidates, evaluation prompts, and
knowledge-gap cases are structured objects with their own title/
summary/tag fields -- forcing every caller to flatten those into text
by hand would be error-prone and would tempt callers into passing full
raw document bodies through the classifier. These adapters do that
flattening once, in one reviewed place, using only the bounded fields
each record type is expected to carry. No adapter fabricates a field
that was not present on the input record.

Each adapter returns the derived classification text; callers pass it
to `pipeline.classify(text, context_type=...)`. The derived text is
never persisted by this module -- only `pipeline.classify()`'s
resulting `input_hash` is meant for storage.
"""

from __future__ import annotations

from typing import Any

from core_model.knowledge_routing.pipeline import ClassificationResult, classify


def _join_fields(*parts: str | None) -> str:
    return " \n".join(part.strip() for part in parts if part and part.strip())


def adapt_rag_record(record: dict[str, Any]) -> str:
    """RAG record: title + summary/snippet + tags.

    Expected keys (all optional except at least one must be present):
    `title`, `summary`, `snippet`, `tags` (list[str]).
    """

    tags = record.get("tags") or []
    tag_text = " ".join(str(tag) for tag in tags) if tags else None
    return _join_fields(
        record.get("title"), record.get("summary") or record.get("snippet"), tag_text
    )


def adapt_dataset_candidate(record: dict[str, Any]) -> str:
    """Dataset candidate: prompt/question text + category label."""

    return _join_fields(
        record.get("prompt") or record.get("question"),
        record.get("category_label"),
    )


def adapt_training_candidate(record: dict[str, Any]) -> str:
    """Training candidate: source prompt + task type label."""

    return _join_fields(record.get("prompt"), record.get("task_type"))


def adapt_evaluation_prompt(record: dict[str, Any]) -> str:
    """Evaluation prompt: the prompt text + evaluation category."""

    return _join_fields(
        record.get("prompt_text") or record.get("prompt"), record.get("eval_category")
    )


def adapt_knowledge_gap_case(record: dict[str, Any]) -> str:
    """Future knowledge-gap case: the representative question text +
    any recorded gap topic label. No knowledge-gap registry exists yet
    (Phase 17 explicitly does not build it) -- this adapter exists so
    Phase 18+ has a ready-made entry point that does not need this
    module touched again."""

    return _join_fields(record.get("representative_question"), record.get("gap_topic"))


_ADAPTERS = {
    "rag_record": adapt_rag_record,
    "dataset_candidate": adapt_dataset_candidate,
    "training_candidate": adapt_training_candidate,
    "evaluation_prompt": adapt_evaluation_prompt,
    "knowledge_gap_case": adapt_knowledge_gap_case,
}


def classify_record(context_type: str, record: dict[str, Any]) -> ClassificationResult:
    """Adapt a structured record for `context_type` and classify it.

    `context_type == "public_chat_question"` is handled by callers
    passing raw text directly to `pipeline.classify()`; it has no
    adapter here since it has no structured record shape.
    """

    adapter = _ADAPTERS.get(context_type)
    if adapter is None:
        raise ValueError(f"no adapter registered for context_type: {context_type!r}")
    text = adapter(record)
    if not text.strip():
        raise ValueError(f"record for context_type {context_type!r} produced no classifiable text")
    return classify(text, context_type=context_type)


__all__ = [
    "adapt_dataset_candidate",
    "adapt_evaluation_prompt",
    "adapt_knowledge_gap_case",
    "adapt_rag_record",
    "adapt_training_candidate",
    "classify_record",
]
