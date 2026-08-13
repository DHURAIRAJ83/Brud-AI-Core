"""MB-39: Chat -> Proposal bridge -- pure.

Maps a small, explicit set of free-text keyword phrases to the
ALREADY-REGISTERED `admin_assistant` action types they may propose
(never execute). This module never touches the proposal/review/execute
engine itself (`action_registry.py`, `admin_assistant_service.py`) --
every `action_type` referenced below already exists there, unmodified.
It only decides *whether* a chat message names one of the four MB-39
scopes, so the service layer can call the existing, unmodified
`AdminAssistantService.propose()` -- never `execute()`.

Naming note (disclosed, not silent): the task that introduced this
module referred to "tool_intent_classifier.py", which is a different,
disconnected module (`core_model.mini_brain.llm_runtime
.tool_intent_classifier`) governing Mini Brain's own, separate chat
system. The Admin Assistant chat this bridge actually connects to
(`backend.services.admin_assistant_chat_service.AdminAssistantChatService
.send_message`) has its own real, private keyword matchers -- this
module extends that system instead, since extending the unrelated one
would not connect chat to the proposal engine at all.
"""

from __future__ import annotations

from dataclasses import dataclass

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


__all__ = ["CHAT_ACTION_SCOPES", "TARGET_TYPE_BY_ACTION", "ChatActionMatch", "match_actionable_intent"]
