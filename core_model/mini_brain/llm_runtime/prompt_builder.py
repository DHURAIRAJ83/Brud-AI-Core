"""MB-28: Prompt Builder -- pure. Assembles the final
`{"system_prompt", "messages"}` chat shape the adapter layer consumes,
from a style directive (`answer_style_policy.py`), a context-window
selection (`context_window_manager.py`), and the current question.
"""

from __future__ import annotations

from typing import Any


def format_dashboard_context(context: dict[str, Any] | None) -> str:
    """Formats 11-subsystem operational state into a factual, concise context block.
    Strictly zero secrets/credentials."""
    if not context:
        return ""
    lines = ["[Live Admin Dashboard Context]"]
    sys_health = context.get("system_health") or context.get("system", {})
    if sys_health:
        lines.append(
            f"- System Health: status={sys_health.get('overall_status')}, "
            f"backend={sys_health.get('backend_type')}, model_loaded={sys_health.get('model_loaded')}, "
            f"env={sys_health.get('environment')}"
        )
    models = context.get("models", {})
    if models:
        lines.append(
            f"- Models: active_model={models.get('active_model')}, "
            f"backend_type={models.get('backend_type')}, local_available={models.get('local_available')}"
        )
    providers = context.get("providers", {})
    if providers:
        lines.append(
            f"- Providers: configured={providers.get('configured', [])}, "
            f"enabled={providers.get('enabled', [])}"
        )
    datasets = context.get("datasets", {})
    if datasets:
        lines.append(
            f"- Datasets: total_versions={datasets.get('total_dataset_versions')}, "
            f"latest_version={datasets.get('latest_version')}, training_ready={datasets.get('training_ready')}"
        )
    training = context.get("training", {})
    if training:
        lines.append(
            f"- Training: total_runs={training.get('total_runs')}, "
            f"latest_status={training.get('latest_run_status')}, "
            f"training_gate={('LOCKED (Fail-closed)' if training.get('training_gate_locked', True) else 'UNLOCKED')}"
        )
    evaluation = context.get("evaluation", {})
    if evaluation:
        lines.append(
            f"- Evaluation: total_evaluations={evaluation.get('total_evaluations')}, "
            f"latest_score={evaluation.get('latest_score')}, status={evaluation.get('evaluation_status')}"
        )
    rag = context.get("rag", {})
    if rag:
        lines.append(
            f"- RAG: spaces_count={rag.get('knowledge_spaces_count')}, "
            f"default_profile={rag.get('default_retrieval_profile_public_id')}, "
            f"grounded_ready={rag.get('grounded_chat_ready')}"
        )
    memory = context.get("memory", {})
    if memory:
        lines.append(
            f"- Memory: active_sessions={memory.get('active_chat_sessions')}, "
            f"total_messages={memory.get('total_messages_recorded')}"
        )
    governance = context.get("governance", {})
    if governance:
        lines.append(
            f"- Governance: authority_mode={governance.get('authority_mode', 'ADVISORY_ONLY')}, "
            f"pending_proposals={governance.get('pending_proposals_count', 0)}, "
            f"production_state={governance.get('production_state', 'LOCKED')}"
        )
    lines.append(
        "Precedence Rule: System/Governance > Admin Dashboard Context > RAG verified knowledge > Conversation memory > User request. "
        "Never invent metrics; always cite this live context when asked about system state."
    )
    return "\n".join(lines)


def build_prompt(
    *,
    style_directives: dict[str, Any],
    context_messages: list[dict[str, Any]],
    question: str,
    tool_results: list[dict[str, Any]] | None = None,
    dashboard_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    system_prompt = style_directives.get("system_prompt", "")
    context_block = format_dashboard_context(dashboard_context)
    if context_block:
        system_prompt = f"{system_prompt}\n\n{context_block}" if system_prompt else context_block

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
    dashboard_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """MB-37: Builds the grounded chat message list -- system prompt,
    then a single user message carrying only the retrieved evidence
    (never inventing a citation beyond what was actually retrieved),
    then the real user question, in that exact order.
    """
    context_block = format_dashboard_context(dashboard_context)
    if context_block:
        system_prompt = f"{system_prompt}\n\n{context_block}" if system_prompt else context_block

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
