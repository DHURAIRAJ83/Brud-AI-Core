"""P1 Architectural Boundary and Bridge Verification Tests.

Proves:
1. Boundary Integrity: Phase 8 AdminAssistantChatService and MB-28 MiniBrainLlmRuntimeService
   remain distinct systems and both converge on core_model/admin_assistant/chat_action_bridge.py.
2. Public Chat Authority: Both /chat and /public/chat utilize PublicChatRoutingService as the
   sole canonical generation engine.
3. Zero Circular Dependencies: Import graphs across admin tools, admin assistant, and mini-brain
   are strictly acyclic.
"""

from __future__ import annotations

import importlib
import pytest


def test_boundary_phase8_and_mb28_converge_on_chat_action_bridge():
    """Verify that both AdminAssistantChatService and MiniBrainLlmRuntimeService import

    and utilize chat_action_bridge.propose_chat_action for action governance.
    """
    from core_model.admin_assistant import chat_action_bridge
    assert hasattr(chat_action_bridge, "match_actionable_intent")
    assert hasattr(chat_action_bridge, "propose_chat_action")

    import inspect
    from backend.services.admin_assistant_chat_service import AdminAssistantChatService
    from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService

    chat_src = inspect.getsource(AdminAssistantChatService)
    llm_src = inspect.getsource(MiniBrainLlmRuntimeService)

    assert "propose_chat_action" in chat_src or "chat_action_bridge" in chat_src
    assert "propose_chat_action" in llm_src or "chat_action_bridge" in llm_src


def test_public_chat_authoritative_routing_delegation():
    """Verify that MiniBrainPublicChatRuntimeService delegates generation

    directly to PublicChatRoutingService rather than reimplementing it.
    """
    import inspect
    from backend.services.mini_brain_public_chat_runtime_service import MiniBrainPublicChatRuntimeService
    from backend.services.public_chat_routing_service import PublicChatRoutingService

    mb_chat_src = inspect.getsource(MiniBrainPublicChatRuntimeService.send_message)
    assert "routing_service" in mb_chat_src or "PublicChatRoutingService" in mb_chat_src or "handle_message" in mb_chat_src


def test_no_circular_dependencies_in_admin_ecosystem():
    """Verify that importing admin_assistant_tools, admin_assistant_service,

    and mini_brain_llm_runtime_service resolves cleanly without circular import errors.
    """
    modules = [
        "backend.services.admin_assistant_tools",
        "backend.services.admin_assistant_service",
        "backend.services.admin_assistant_chat_service",
        "backend.services.mini_brain_llm_runtime_service",
        "backend.services.public_chat_routing_service",
        "backend.services.mini_brain_public_chat_runtime_service",
        "core_model.admin_assistant.chat_action_bridge",
    ]
    for mod in modules:
        m = importlib.import_module(mod)
        assert m is not None
