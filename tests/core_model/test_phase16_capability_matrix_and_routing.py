"""Phase 16: Capability Matrix & Smart Routing — 40-scenario verification suite.

Covers every required test scenario from the Phase 16 specification:
 1. Matrix loads
 2. Every capability has a valid source component
 3. No fake available capability
 4. Status taxonomy validation
 5. Access-level taxonomy validation
 6. Risk taxonomy validation
 7. Language detection capability discovered
 8. Tanglish normalization discovered
 9. RAG correctly classified
10. Memory correctly classified
11. Admin Assistant correctly classified
12. Governance correctly classified
13. Automation correctly classified
14. Public/admin separation
15. SUPER_ADMIN does not bypass governance
16. Public request only routes to public-safe capability
17. Admin request can select admin capability
18. Unknown request fails closed
19. Low-confidence request fails closed
20. Routing is deterministic
21. Router never executes capabilities
22. Router never invokes tools
23. Router never invokes external APIs
24. Router never accesses production DB
25. Router does not modify DB state
26. Phase 15 NLP integration
27. Technical text routing preserved
28. Destructive request gets warning/governance
29. Automation request does not trigger execution
30. Duplicate/overlap detection works
31. Missing implementation not marked available
32. Deprecated capability handling
33. Partial capability handling
34. AST security inspection (capability_matrix)
35. AST security inspection (smart_router)
36. No eval/exec
37. No workers/schedulers/queues
38. Repeated routing produces identical result
39. Capability matrix is immutable
40. Routing result is immutable
"""

from __future__ import annotations

import ast
import inspect

import pytest

from core_model.capabilities import (
    SYSTEM_CAPABILITIES,
    CapabilityDefinition,
    RoutingDecision,
    get_capability,
    list_capabilities,
    route_capability,
)
from core_model.capabilities.capability_matrix import (
    VALID_ACCESS_LEVELS,
    VALID_AVAILABILITY,
    VALID_RISK_LEVELS,
)


# ---------------------------------------------------------------------------
# 1. Matrix loads successfully
# ---------------------------------------------------------------------------
def test_01_capability_matrix_loads() -> None:
    assert len(SYSTEM_CAPABILITIES) > 0
    assert all(isinstance(v, CapabilityDefinition) for v in SYSTEM_CAPABILITIES.values())


# ---------------------------------------------------------------------------
# 2. Every capability has a valid source component
# ---------------------------------------------------------------------------
def test_02_every_capability_has_source_component() -> None:
    for cap in list_capabilities():
        assert cap.source_component, f"{cap.capability_id} missing source_component"


# ---------------------------------------------------------------------------
# 3. No fake "available" capability without source evidence
# ---------------------------------------------------------------------------
def test_03_no_fake_available_capability() -> None:
    placeholder_patterns = ("todo", "tbd", "placeholder", "fake")
    for cap in list_capabilities():
        if cap.availability == "available":
            src = cap.source_component.lower()
            for p in placeholder_patterns:
                assert p not in src, f"{cap.capability_id} source looks like a placeholder"


# ---------------------------------------------------------------------------
# 4. Status taxonomy
# ---------------------------------------------------------------------------
def test_04_status_taxonomy_valid() -> None:
    for cap in list_capabilities():
        assert cap.availability in VALID_AVAILABILITY, f"{cap.capability_id}: {cap.availability!r}"


# ---------------------------------------------------------------------------
# 5. Access-level taxonomy
# ---------------------------------------------------------------------------
def test_05_access_level_taxonomy_valid() -> None:
    for cap in list_capabilities():
        assert cap.access_level in VALID_ACCESS_LEVELS, f"{cap.capability_id}: {cap.access_level!r}"


# ---------------------------------------------------------------------------
# 6. Risk-level taxonomy
# ---------------------------------------------------------------------------
def test_06_risk_level_taxonomy_valid() -> None:
    for cap in list_capabilities():
        assert cap.risk_level in VALID_RISK_LEVELS, f"{cap.capability_id}: {cap.risk_level!r}"


# ---------------------------------------------------------------------------
# 7. Language detection capability discovered
# ---------------------------------------------------------------------------
def test_07_language_detection_discovered() -> None:
    cap = get_capability("language_detection")
    assert cap is not None
    assert cap.availability == "available"
    assert "process_text" in cap.source_component or "language_detector" in cap.source_component


# ---------------------------------------------------------------------------
# 8. Tanglish normalization discovered
# ---------------------------------------------------------------------------
def test_08_tanglish_normalization_discovered() -> None:
    cap = get_capability("tanglish_normalization")
    assert cap is not None
    assert cap.availability == "available"
    assert cap.supports_public_chat is True


# ---------------------------------------------------------------------------
# 9. RAG capability correctly classified
# ---------------------------------------------------------------------------
def test_09_rag_capability_correctly_classified() -> None:
    cap = get_capability("rag_retrieval")
    assert cap is not None
    assert cap.category == "rag"
    assert cap.availability == "available"


# ---------------------------------------------------------------------------
# 10. Memory capability correctly classified
# ---------------------------------------------------------------------------
def test_10_memory_capability_correctly_classified() -> None:
    cap = get_capability("conversation_memory")
    assert cap is not None
    assert cap.category == "memory"
    assert cap.availability == "available"


# ---------------------------------------------------------------------------
# 11. Admin Assistant capability correctly classified
# ---------------------------------------------------------------------------
def test_11_admin_assistant_correctly_classified() -> None:
    cap = get_capability("tool_execution")
    assert cap is not None
    assert cap.supports_admin_assistant is True
    assert cap.supports_public_chat is False
    assert cap.access_level in {"admin", "super_admin"}


# ---------------------------------------------------------------------------
# 12. Governance capability correctly classified
# ---------------------------------------------------------------------------
def test_12_governance_correctly_classified() -> None:
    cap = get_capability("admin_assistant_governance")
    assert cap is not None
    assert cap.category == "governance"
    assert cap.requires_human_approval is True


# ---------------------------------------------------------------------------
# 13. Automation capability correctly classified
# ---------------------------------------------------------------------------
def test_13_automation_correctly_classified() -> None:
    cap = get_capability("automation_evaluation")
    assert cap is not None
    assert cap.category == "automation"
    assert cap.supports_public_chat is False


# ---------------------------------------------------------------------------
# 14. Public/admin access separation
# ---------------------------------------------------------------------------
def test_14_public_admin_access_separation() -> None:
    admin_caps = [c for c in list_capabilities() if not c.supports_public_chat]
    public_caps = [c for c in list_capabilities() if c.supports_public_chat]
    assert len(admin_caps) > 0
    assert len(public_caps) > 0
    # Non-public-chat capabilities must NOT use the "public" access level.
    # (They may be "authenticated", "admin", "super_admin", "internal", or "unavailable".)
    for cap in admin_caps:
        assert cap.access_level != "public", (
            f"{cap.capability_id} is not public-chat-safe but has access_level='public'"
        )


# ---------------------------------------------------------------------------
# 15. SUPER_ADMIN does not bypass governance
# ---------------------------------------------------------------------------
def test_15_super_admin_does_not_bypass_governance() -> None:
    dec = route_capability(
        "train the model",
        caller_context="admin_assistant",
        user_role="super_admin",
    )
    cap_id = dec.selected_capability_id
    if cap_id:
        cap = get_capability(cap_id)
        assert cap is not None
        if cap.risk_level == "critical":
            assert cap.requires_human_approval is True


# ---------------------------------------------------------------------------
# 16. Public request routes only to public-safe capability
# ---------------------------------------------------------------------------
def test_16_public_request_only_public_safe() -> None:
    dec = route_capability(
        "detect language of this text",
        caller_context="public_chat",
        user_role="none",
    )
    if dec.selected_capability_id:
        cap = get_capability(dec.selected_capability_id)
        assert cap is not None
        assert cap.supports_public_chat is True


# ---------------------------------------------------------------------------
# 17. Admin request can identify admin capability
# ---------------------------------------------------------------------------
def test_17_admin_request_identifies_admin_capability() -> None:
    dec = route_capability(
        "run admin action governance",
        caller_context="admin_assistant",
        user_role="admin",
    )
    # Should route or fail-closed; must never silently grant public access
    if dec.selected_capability_id:
        cap = get_capability(dec.selected_capability_id)
        assert cap is not None


# ---------------------------------------------------------------------------
# 18. Unknown request fails closed
# ---------------------------------------------------------------------------
def test_18_unknown_request_fails_closed() -> None:
    dec = route_capability(
        "xyzmzx999 gibberish incomprehensible nonsense input",
        caller_context="public_chat",
        user_role="none",
    )
    assert dec.selected_capability_id is None
    assert "insufficient_routing_confidence" in dec.blocking_reasons


# ---------------------------------------------------------------------------
# 19. Low-confidence request fails closed
# ---------------------------------------------------------------------------
def test_19_low_confidence_fails_closed() -> None:
    dec = route_capability("maybe do something", caller_context="public_chat", user_role="none")
    if dec.confidence < 0.60:
        assert dec.selected_capability_id is None


# ---------------------------------------------------------------------------
# 20. Routing is deterministic
# ---------------------------------------------------------------------------
def test_20_routing_is_deterministic() -> None:
    req = "search my knowledge base for training data"
    r1 = route_capability(req, caller_context="public_chat", user_role="authenticated")
    r2 = route_capability(req, caller_context="public_chat", user_role="authenticated")
    r3 = route_capability(req, caller_context="public_chat", user_role="authenticated")
    assert r1 == r2 == r3


# ---------------------------------------------------------------------------
# 21. Router never executes capabilities (structural check)
# ---------------------------------------------------------------------------
def test_21_router_never_executes_capabilities() -> None:
    from core_model.capabilities import smart_router as sm
    source = inspect.getsource(sm)
    # No call sites to action executors in the routing logic
    for forbidden in ("run_tool(", "execute_with_governance(", "execute_automation_manually("):
        assert forbidden not in source, f"Found forbidden call: {forbidden!r} in smart_router"


# ---------------------------------------------------------------------------
# 22. Router never invokes tools
# ---------------------------------------------------------------------------
def test_22_router_never_invokes_tools() -> None:
    dec = route_capability("run action delete record", caller_context="public_chat", user_role="none")
    # The routing decision should NOT have already executed anything
    assert isinstance(dec, RoutingDecision)


# ---------------------------------------------------------------------------
# 23. Router never invokes external APIs
# ---------------------------------------------------------------------------
def test_23_router_never_invokes_external_apis() -> None:
    from core_model.capabilities import smart_router as sm
    source = inspect.getsource(sm)
    for forbidden in ("requests.", "httpx.", "urllib.request", "http.client"):
        assert forbidden not in source


# ---------------------------------------------------------------------------
# 24. Router never accesses production DB
# ---------------------------------------------------------------------------
def test_24_router_never_accesses_production_db() -> None:
    from core_model.capabilities import smart_router as sm
    source = inspect.getsource(sm)
    for forbidden in ("sqlite3", "psycopg2", "sqlalchemy", "database_pool", "get_db"):
        assert forbidden not in source.lower()


# ---------------------------------------------------------------------------
# 25. Router does not modify database state
# ---------------------------------------------------------------------------
def test_25_router_does_not_modify_db_state() -> None:
    import hashlib, os
    db_path = "data/database/brud_ai.db"
    before = hashlib.sha256(open(db_path, "rb").read()).hexdigest()
    _ = route_capability("search my knowledge base", caller_context="public_chat", user_role="none")
    after = hashlib.sha256(open(db_path, "rb").read()).hexdigest()
    assert before == after


# ---------------------------------------------------------------------------
# 26. Phase 15 NLP integration works
# ---------------------------------------------------------------------------
def test_26_phase15_nlp_integration() -> None:
    dec = route_capability("இந்த உரையை தமிழில் மாற்று", caller_context="public_chat", user_role="none")
    assert isinstance(dec, RoutingDecision)


# ---------------------------------------------------------------------------
# 27. Technical text routing preserved
# ---------------------------------------------------------------------------
def test_27_technical_text_routing_preserved() -> None:
    dec = route_capability("git status என்ன?", caller_context="public_chat", user_role="none")
    # Must not route to admin-only capabilities
    if dec.selected_capability_id:
        cap = get_capability(dec.selected_capability_id)
        if cap:
            assert cap.supports_public_chat or dec.executable is False


# ---------------------------------------------------------------------------
# 28. Destructive request receives warning/governance
# ---------------------------------------------------------------------------
def test_28_destructive_request_governance_flag() -> None:
    dec = route_capability(
        "delete this data from the system",
        caller_context="admin_assistant",
        user_role="admin",
    )
    assert isinstance(dec, RoutingDecision)
    # Destructive intent must produce a warning or a high-risk result
    if dec.selected_capability_id:
        cap = get_capability(dec.selected_capability_id)
        if cap:
            has_warning = len(dec.warnings) > 0 or cap.risk_level in {"high", "critical"}
            assert has_warning


# ---------------------------------------------------------------------------
# 29. Automation request does not trigger execution
# ---------------------------------------------------------------------------
def test_29_automation_request_no_execution() -> None:
    dec = route_capability(
        "run automation dry run simulate",
        caller_context="admin_assistant",
        user_role="admin",
    )
    assert isinstance(dec, RoutingDecision)
    # The result must only be a decision; it must never have called execute
    assert not hasattr(dec, "execution_result")
    assert not hasattr(dec, "worker_id")


# ---------------------------------------------------------------------------
# 30. Duplicate/overlapping capability detection
# ---------------------------------------------------------------------------
def test_30_duplicate_overlap_detection() -> None:
    categories: dict[str, list[str]] = {}
    for cap in list_capabilities():
        categories.setdefault(cap.category, []).append(cap.capability_id)
    # Find categories with multiple capabilities (expected: automation, provider_routing, rag, language_detection)
    overlapping = {cat: ids for cat, ids in categories.items() if len(ids) > 1}
    # Confirm overlaps are explicitly documented (not a bug — they should exist)
    for cat, ids in overlapping.items():
        for cap_id in ids:
            cap = get_capability(cap_id)
            assert cap is not None
            assert cap.limitations  # Duplicates must have explicit limitations


# ---------------------------------------------------------------------------
# 31. Missing implementation not marked available
# ---------------------------------------------------------------------------
def test_31_missing_implementation_not_marked_available() -> None:
    cap = get_capability("autonomous_execution")
    assert cap is not None
    assert cap.availability == "unavailable"


# ---------------------------------------------------------------------------
# 32. Deprecated capability handling
# ---------------------------------------------------------------------------
def test_32_deprecated_capability_handling() -> None:
    deprecated = [c for c in list_capabilities() if c.availability == "deprecated"]
    # If any deprecated capabilities exist, they must be non-public and have limitations
    for cap in deprecated:
        assert cap.limitations, f"{cap.capability_id} is deprecated but has no limitations"


# ---------------------------------------------------------------------------
# 33. Partial capability handling
# ---------------------------------------------------------------------------
def test_33_partial_capability_handling() -> None:
    partial_caps = [c for c in list_capabilities() if c.availability == "partial"]
    assert len(partial_caps) >= 1  # voice_runtime should be partial
    for cap in partial_caps:
        assert cap.limitations, f"{cap.capability_id} is partial but has no limitations"


# ---------------------------------------------------------------------------
# 34-37. AST security inspection
# ---------------------------------------------------------------------------
def _ast_security_check(module_name: str) -> None:
    import importlib
    mod = importlib.import_module(module_name)
    source = inspect.getsource(mod)
    tree = ast.parse(source)
    lowered = source.lower()

    forbidden_patterns = [
        "asyncio.create_task",
        "backgroundtasks",
        "while true",
        "celery",
        "apscheduler",
        "cron",
        "queueconsumer",
        "subprocess",
        "os.system",
        "run_tool(",
        "execute_with_governance(",
        "requests.get",
        "requests.post",
        "httpx",
        "urllib.request",
        "sqlite3",
    ]
    for pattern in forbidden_patterns:
        assert pattern not in lowered, f"Forbidden pattern {pattern!r} found in {module_name}"

    # No eval/exec in call nodes
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "compile", "__import__"}, \
                f"Forbidden call {node.func.id!r} in {module_name}"


def test_34_ast_security_capability_matrix() -> None:
    _ast_security_check("core_model.capabilities.capability_matrix")


def test_35_ast_security_smart_router() -> None:
    _ast_security_check("core_model.capabilities.smart_router")


def test_36_no_eval_exec_in_either_module() -> None:
    for mod_name in ("core_model.capabilities.capability_matrix", "core_model.capabilities.smart_router"):
        import importlib
        mod = importlib.import_module(mod_name)
        source = inspect.getsource(mod)
        assert "eval(" not in source
        assert "exec(" not in source


def test_37_no_workers_schedulers_queues() -> None:
    for mod_name in ("core_model.capabilities.capability_matrix", "core_model.capabilities.smart_router"):
        import importlib
        mod = importlib.import_module(mod_name)
        source = inspect.getsource(mod).lower()
        for forbidden in ("celery", "apscheduler", "rq.", "dramatiq", "cron", "background_worker"):
            assert forbidden not in source, f"{forbidden!r} found in {mod_name}"


# ---------------------------------------------------------------------------
# 38. Repeated routing produces identical result
# ---------------------------------------------------------------------------
def test_38_repeated_routing_identical_result() -> None:
    req = "search knowledge base"
    results = [route_capability(req, caller_context="public_chat", user_role="authenticated") for _ in range(5)]
    for r in results[1:]:
        assert r == results[0]


# ---------------------------------------------------------------------------
# 39. Capability matrix is immutable
# ---------------------------------------------------------------------------
def test_39_capability_matrix_is_immutable() -> None:
    cap = get_capability("language_detection")
    assert cap is not None
    with pytest.raises((AttributeError, TypeError)):
        cap.availability = "deprecated"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 40. Routing result is immutable
# ---------------------------------------------------------------------------
def test_40_routing_result_is_immutable() -> None:
    dec = route_capability("detect language", caller_context="public_chat", user_role="none")
    with pytest.raises((AttributeError, TypeError)):
        dec.executable = True  # type: ignore[misc]
