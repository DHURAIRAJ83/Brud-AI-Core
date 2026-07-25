"""Combines system policy, the current request, recent conversation,
a validated summary, retrieved memory, and RAG evidence into one
priority-ordered, typed list of context items -- before budgeting.

Required priority order (highest first): system/safety instructions,
the latest user request, required RAG evidence, relevant active
user-confirmed memory, recent conversation, validated summary, then any
remaining lower-ranked memory. Memory and RAG evidence can never
override system policy -- system instructions are always assembled
first and are never subject to budget-based exclusion.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def build_context_items(
    *,
    system_instructions_text: str,
    current_request_text: str,
    rag_chunks: list[dict[str, Any]],
    confirmed_memory_items: list[dict[str, Any]],
    recent_turns: list[dict[str, Any]],
    validated_summary: dict[str, Any] | None,
    other_memory_items: list[dict[str, Any]],
    estimate_tokens: Callable[[str], int],
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []

    items.append({
        "item_type": "system_instruction", "source_public_id": None,
        "token_count": estimate_tokens(system_instructions_text),
        "content": system_instructions_text,
        "mandatory": True,
    })
    items.append({
        "item_type": "current_request", "source_public_id": None,
        "token_count": estimate_tokens(current_request_text),
        "content": current_request_text,
        "mandatory": True,
    })
    for chunk in rag_chunks:
        items.append({
            "item_type": "rag_chunk", "source_public_id": chunk["chunk_public_id"],
            "token_count": chunk["estimated_token_count"],
            "content": chunk["normalized_text"],
            "mandatory": False,
        })
    for memory_item in confirmed_memory_items:
        items.append({
            "item_type": "memory_item", "source_public_id": memory_item["public_id"],
            "token_count": memory_item["token_count"], "content": memory_item["display_value"],
            "mandatory": False,
        })
    for turn in recent_turns:
        items.append({
            "item_type": "conversation_turn", "source_public_id": turn["public_id"],
            "token_count": turn["token_count"], "content": turn["content"],
            "mandatory": False,
        })
    if validated_summary is not None:
        items.append({
            "item_type": "conversation_summary",
            "source_public_id": validated_summary["public_id"],
            "token_count": validated_summary["token_count"],
            "content": validated_summary["summary_text"],
            "mandatory": False,
        })
    for memory_item in other_memory_items:
        items.append({
            "item_type": "memory_item", "source_public_id": memory_item["public_id"],
            "token_count": memory_item["token_count"], "content": memory_item["display_value"],
            "mandatory": False,
        })
    return items
