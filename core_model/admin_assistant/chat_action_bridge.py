"""MB-39: Chat -> Proposal bridge.

`match_actionable_intent()` is pure: it maps a small, explicit set of
free-text keyword phrases to the ALREADY-REGISTERED `admin_assistant`
action types they may propose (never execute). It never touches the
proposal/review/execute engine itself (`action_registry.py`,
`admin_assistant_service.py`) -- every `action_type` referenced below
already exists there, unmodified. It only decides *whether* a chat
message names one of the four MB-39 scopes.

Naming note (disclosed, not silent): the task that introduced this
module referred to "tool_intent_classifier.py", which is a different,
disconnected module (`core_model.mini_brain.llm_runtime
.tool_intent_classifier`) governing Mini Brain's own, separate chat
system. The Admin Assistant chat this bridge originally connected to
(`backend.services.admin_assistant_chat_service.AdminAssistantChatService
.send_message`) has its own real, private keyword matchers -- this
module extended that system instead, since extending the unrelated one
would not connect chat to the proposal engine at all.

Phase 16.5 (MB-28 -> Phase-8 governance proposal bridge): `propose_chat_action()`
below is the one, shared, non-pure half of this bridge -- it turns a
matched intent into a real call to the existing, unmodified
`AdminAssistantService.propose()` and nothing else (never `review()`,
never `execute()`). It is called from both
`AdminAssistantChatService._maybe_propose_chat_action()` (Phase-8's own
chat) and `MiniBrainLlmRuntimeService.chat()` (MB-28, the canonical
live chat runtime) so there is exactly one implementation of "how a
matched intent becomes a proposal," not two. Whichever chat surface
calls it, the result is always `status="pending"` -- a human must still
review and approve it through the existing, unmodified Admin Assistant
proposal flow before anything executes.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.services.admin_assistant_service import AdminAssistantService

# Defense in depth, mirrored from action_registry.py's own
# BLOCKED_ACTION_SUBSTRINGS: even though no keyword set below resembles
# training language today, a message that also mentions training is
# refused before any scope match is attempted -- so a future keyword
# addition can never accidentally open a path to a blocked action type.
_BLOCKED_MESSAGE_SUBSTRINGS = ("train", "pretrain")

# scope -> the real, already-registered admin_assistant action_type it proposes.
CHAT_ACTION_SCOPES: dict[str, str] = {
    "dataset.import.external": "register_external_data_provider",
    "dataset.clean": "run_sample_quality_checks",
    "rag.build": "build_rag_sandbox_index",
    "rag.evaluate": "run_rag_sandbox_evaluation",
}

# action_type -> the target_type ActionDefinition already requires for it
# (see core_model.admin_assistant.action_registry.ACTION_DEFINITIONS).
TARGET_TYPE_BY_ACTION: dict[str, str] = {
    "register_external_data_provider": "external_data_provider_registration",
    "run_sample_quality_checks": "external_dataset_sample_import",
    "build_rag_sandbox_index": "rag_sandbox_experiment",
    "run_rag_sandbox_evaluation": "rag_sandbox_experiment",
}

_KEYWORDS_BY_SCOPE: dict[str, tuple[str, ...]] = {
    "dataset.import.external": ("import dataset", "external provider"),
    "dataset.clean": ("clean dataset",),
    "rag.build": ("build rag",),
    "rag.evaluate": ("rag test",),
}


@dataclass(frozen=True)
class ChatActionMatch:
    scope: str
    action_type: str
    target_type: str
    matched_keywords: tuple[str, ...]


def match_actionable_intent(message: str) -> ChatActionMatch | None:
    """Returns the first matching MB-39 scope, or None. A message
    mentioning a blocked substring never matches any scope, regardless
    of what else it contains."""

    message_lower = message.lower()
    if any(token in message_lower for token in _BLOCKED_MESSAGE_SUBSTRINGS):
        return None
    for scope, keywords in _KEYWORDS_BY_SCOPE.items():
        hits = tuple(word for word in keywords if word in message_lower)
        if hits:
            action_type = CHAT_ACTION_SCOPES[scope]
            return ChatActionMatch(
                scope=scope,
                action_type=action_type,
                target_type=TARGET_TYPE_BY_ACTION[action_type],
                matched_keywords=hits,
            )
    return None


def propose_chat_action(
    assistant: "AdminAssistantService",
    *,
    match: ChatActionMatch,
    message: str,
    admin_id: str,
    entity_type: str | None,
    entity_public_id: str | None,
) -> dict[str, Any] | None:
    """Turns a matched intent into a real, pending proposal via the
    existing, unmodified `assistant.propose()` -- never `execute()`.
    Never invents a target entity or a payload value it was not
    actually given: for scopes that need real context this bridge
    was never given, it declines (returns None) instead, so the
    caller can fall back to guidance/normal chat. A returned proposal
    is always `status="pending"`."""

    if match.action_type == "register_external_data_provider":
        # Registering a brand-new provider needs no pre-existing
        # target, so this scope is always proposable once matched.
        provider_code = f"chat-{uuid.uuid4().hex[:10]}"
        proposal = assistant.propose(
            action_type=match.action_type,
            target_type=match.target_type,
            target_public_id=provider_code,
            request_payload={
                "provider_code": provider_code,
                "name": f"Chat-requested provider ({provider_code})",
                "provider_type": "custom_api",
                "access_mode": "public",
                "description": f"Registered from an Admin Assistant chat message: {message[:200]!r}",
            },
            requested_by=admin_id,
            summary="Register a new external data provider requested via Admin Assistant chat",
        )
        return {"public_id": proposal.public_id, "action_type": proposal.action_type, "status": proposal.status}

    if match.action_type == "run_sample_quality_checks":
        if entity_type == match.target_type and entity_public_id:
            proposal = assistant.propose(
                action_type=match.action_type,
                target_type=match.target_type,
                target_public_id=entity_public_id,
                request_payload={},
                requested_by=admin_id,
                summary="Run dataset quality checks requested via Admin Assistant chat",
            )
            return {"public_id": proposal.public_id, "action_type": proposal.action_type, "status": proposal.status}
        return None

    # build_rag_sandbox_index and run_rag_sandbox_evaluation both require
    # real configuration this bridge is never given (index_kind/
    # chunking_config/embedding_model_public_id, or an
    # answer_run_public_id) -- inventing those would produce a proposal
    # whose own preview misrepresents what was asked for, so this bridge
    # deliberately declines both.
    return None


__all__ = [
    "CHAT_ACTION_SCOPES", "TARGET_TYPE_BY_ACTION", "ChatActionMatch",
    "match_actionable_intent", "propose_chat_action",
]
