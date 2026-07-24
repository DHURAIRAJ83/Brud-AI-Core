"""Deterministic, bounded conversation-context construction.

Reuses the same fixed token shape Phase 12's instruction template
established (``<bos> <system> ... <user> ... <assistant>``) but extends
it to a bounded multi-turn conversation rather than a single exchange.
Never appends an assistant response before generation — the assistant
prefix is always the final token of the built context, and the latest
user message is always preserved (older turns are dropped first).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from core_model.inference_runtime import CONTEXT_TRUNCATION_POLICIES

VALID_ROLES = ("system", "user", "assistant")


@dataclass(frozen=True)
class ConversationTurn:
    role: str
    text: str


def validate_turn_roles(turns: list[ConversationTurn]) -> list[str]:
    return [f"invalid role: {turn.role}" for turn in turns if turn.role not in VALID_ROLES]


def _render(
    *,
    bos_token: str,
    system_prefix: str,
    user_prefix: str,
    assistant_prefix: str,
    system_text: str,
    history: list[ConversationTurn],
    latest_user_message: str,
) -> str:
    parts = [bos_token]
    if system_text:
        parts.append(system_prefix)
        parts.append(system_text)
    for turn in history:
        prefix = {"system": system_prefix, "user": user_prefix, "assistant": assistant_prefix}[
            turn.role
        ]
        parts.append(prefix)
        parts.append(turn.text)
    parts.append(user_prefix)
    parts.append(latest_user_message)
    parts.append(assistant_prefix)
    return " ".join(part for part in parts if part)


def build_context(
    *,
    system_prompt: str,
    history: list[ConversationTurn],
    latest_user_message: str,
    bos_token: str,
    system_prefix: str,
    user_prefix: str,
    assistant_prefix: str,
    encode_fn: Callable[[str], list[int]],
    maximum_context_length: int,
    truncation_policy: str,
) -> dict[str, Any]:
    if truncation_policy not in CONTEXT_TRUNCATION_POLICIES:
        raise ValueError(f"truncation_policy must be one of {CONTEXT_TRUNCATION_POLICIES}")
    role_errors = validate_turn_roles(history)
    if role_errors:
        raise ValueError("; ".join(role_errors))

    working_history = list(history)
    working_system = system_prompt
    dropped_turns = 0

    def current() -> tuple[str, int]:
        text = _render(
            bos_token=bos_token,
            system_prefix=system_prefix,
            user_prefix=user_prefix,
            assistant_prefix=assistant_prefix,
            system_text=working_system,
            history=working_history,
            latest_user_message=latest_user_message,
        )
        return text, len(encode_fn(text))

    prompt_text, token_count = current()
    if token_count <= maximum_context_length:
        return {
            "prompt_text": prompt_text,
            "token_count": token_count,
            "truncated": False,
            "dropped_turns": 0,
            "rejected": False,
        }

    if truncation_policy == "reject":
        return {
            "prompt_text": "",
            "token_count": token_count,
            "truncated": False,
            "dropped_turns": 0,
            "rejected": True,
        }

    if truncation_policy == "truncate_system_then_history" and working_system:
        working_system = ""
        prompt_text, token_count = current()

    while working_history and token_count > maximum_context_length:
        working_history.pop(0)
        dropped_turns += 1
        prompt_text, token_count = current()

    if token_count > maximum_context_length:
        return {
            "prompt_text": "",
            "token_count": token_count,
            "truncated": True,
            "dropped_turns": dropped_turns,
            "rejected": True,
        }

    return {
        "prompt_text": prompt_text,
        "token_count": token_count,
        "truncated": dropped_turns > 0 or working_system != system_prompt,
        "dropped_turns": dropped_turns,
        "rejected": False,
    }
