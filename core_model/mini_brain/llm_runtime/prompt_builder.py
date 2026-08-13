"""MB-28: Prompt Builder -- pure. Assembles the final
`{"system_prompt", "messages"}` chat shape the adapter layer consumes,
from a style directive (`answer_style_policy.py`), a context-window
selection (`context_window_manager.py`), and the current question.
"""

from __future__ import annotations

from typing import Any


def build_prompt(
    *,
    style_directives: dict[str, Any],
    context_messages: list[dict[str, Any]],
    question: str,
    tool_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    system_prompt = style_directives.get("system_prompt", "")
    messages: list[dict[str, Any]] = [
        {"role": message.get("role", "user"), "content": message.get("content", "")}
        for message in context_messages
        if message.get("role") != "system"
    ]

    for result in tool_results or []:
        messages.append(
            {
                "role": "tool",
                "content": f"Tool result ({result.get('tool_name', 'unknown')}): {result.get('summary', '')}",
            }
        )

    messages.append({"role": "user", "content": question})

    return {"system_prompt": system_prompt, "messages": messages}


def build_grounded_messages(
    *,
    system_prompt: str,
    user_message: str,
    retrieved_chunks: list[dict[str, Any]],
) -> dict[str, Any]:
    """MB-37: Builds the grounded chat message list -- system prompt,
    then a single user message carrying only the retrieved evidence
    (never inventing a citation beyond what was actually retrieved),
    then the real user question, in that exact order.
    """
    evidence_lines = [
        "Use the following retrieved knowledge. If the answer is not "
        "present, say that the retrieved knowledge does not contain the answer.",
        "",
    ]
    for index, chunk in enumerate(retrieved_chunks, start=1):
        evidence_lines.append(f"[Source {index}]")
        evidence_lines.append(chunk.get("normalized_text", ""))
        evidence_lines.append("")
    evidence_block = "\n".join(evidence_lines).rstrip()

    messages = [
        {"role": "user", "content": evidence_block},
        {"role": "user", "content": user_message},
    ]
    return {"system_prompt": system_prompt, "messages": messages}
