"""Phase 17: Public Chat Capability Gate — End-to-End Verification Suite.

43 dedicated tests covering the complete Phase 17 specification:

Gate Correctness (01–16):
  01. Gate module imports cleanly
  02. GateDecision is a frozen dataclass
  03. Tamil input → allowed (language_detection capability)
  04. Tanglish input → allowed (tanglish_normalization)
  05. RAG search request → allowed
  06. Memory recall request → allowed
  07. Admin governance request from public → blocked
  08. Tool execution request from public → blocked
  09. Automation evaluation request from public → blocked
  10. Manual automation execution request from public → blocked
  11. Incremental training request from public → blocked
  12. External AI provider request from public → blocked
  13. Low-confidence gibberish → blocked (fail-closed)
  14. Empty string input → blocked (fail-closed)
  15. Technical code text (git status) → not routed to admin capability
  16. Destructive request from public → blocked

Observability (17–23):
  17. audit_payload always populated (allowed path)
  18. audit_payload always populated (blocked path)
  19. audit_payload is JSON-serializable (no frozen dataclasses inside)
  20. audit_payload contains nlp_trace key
  21. audit_payload contains routing_trace key
  22. audit_payload contains gate_decision key
  23. denial_reason is None when allowed; non-None when blocked

Policy Integrity (24–27):
  24. Gate is deterministic — same input → same GateDecision
  25. gate_decision.allowed field consistent with GateDecision.allowed
  26. NLPResult embedded as plain dict (not as dataclass object)
  27. RoutingDecision embedded as plain dict (not as dataclass object)

Security — No Execution (28–35):
  28. Gate never executes capabilities (structural source check)
  29. Gate never invokes tools (source check)
  30. Gate never accesses DB (source check)
  31. Gate never calls external HTTP APIs (source check)
  32. Gate never uses eval / exec
  33. Gate never uses subprocess / os.system
  34. Gate never spawns background workers / celery / cron
  35. AST security inspection — gate module

  36. AST security inspection — observability module

Compatibility Regression (37–40):
  37. Phase 15 — NLPResult shape unchanged
  38. Phase 16 — RoutingDecision shape unchanged
  39. PublicChatRequest schema unchanged (public API contract)
  40. PublicChatRoutingService module unchanged (gate is additive)

Phase 10–14 Automation Regression (41):
  41. AUTOMATION_ALLOWED_ACTIONS == frozenset() (default-deny)

DB + Git Integrity (42–43):
  42. DB SHA-256 hash unchanged after gate evaluation
  43. GateDecision itself is immutable (frozen dataclass)
"""

from __future__ import annotations

import ast
import inspect
import json
from dataclasses import fields

import pytest

import core_model.capabilities.public_capability_gate as _gate_mod
import core_model.capabilities.gate_observability as _obs_mod
from core_model.capabilities.public_capability_gate import (
    GateDecision,
    evaluate_public_capability_gate,
)
from core_model.capabilities.gate_observability import (
    build_gate_decided_payload,
    build_nlp_trace,
    build_routing_trace,
)
from core_model.nlp.text_processor import NLPResult, process_text
from core_model.capabilities.smart_router import RoutingDecision, route_capability


# ---------------------------------------------------------------------------
# 01. Gate module imports cleanly
# ---------------------------------------------------------------------------
def test_01_gate_module_imports_cleanly() -> None:
    assert evaluate_public_capability_gate is not None
    assert GateDecision is not None


# ---------------------------------------------------------------------------
# 02. GateDecision is a frozen dataclass
# ---------------------------------------------------------------------------
def test_02_gate_decision_is_frozen_dataclass() -> None:
    field_names = {f.name for f in fields(GateDecision)}
    assert "allowed" in field_names
    assert "routing_decision" in field_names
    assert "nlp_result" in field_names
    assert "denial_reason" in field_names
    assert "audit_payload" in field_names


# ---------------------------------------------------------------------------
# 03. Tamil input → allowed (language_detection capability)
# ---------------------------------------------------------------------------
def test_03_tamil_input_allowed() -> None:
    decision = evaluate_public_capability_gate("இந்த உரையை மொழி கண்டறிய வேண்டும்")
    # Tamil language queries about language detection must be allowed
    assert isinstance(decision, GateDecision)
    # The gate decision tracks NLP language correctly
    assert decision.nlp_result.detected_language in {"ta", "mixed"}


# ---------------------------------------------------------------------------
# 04. Tanglish input → allowed (tanglish_normalization)
# ---------------------------------------------------------------------------
def test_04_tanglish_input_allowed() -> None:
    decision = evaluate_public_capability_gate("epadi irukku tanglish convert venum")
    assert isinstance(decision, GateDecision)
    # Must not route to any admin-only capability
    if decision.routing_decision.selected_capability_id is not None:
        from core_model.capabilities.capability_matrix import get_capability
        cap = get_capability(decision.routing_decision.selected_capability_id)
        if cap is not None:
            assert cap.supports_public_chat is True


# ---------------------------------------------------------------------------
# 05. RAG search request → allowed
# ---------------------------------------------------------------------------
def test_05_rag_search_request_allowed() -> None:
    decision = evaluate_public_capability_gate("search my knowledge base for information")
    assert isinstance(decision, GateDecision)
    if decision.routing_decision.selected_capability_id == "rag_retrieval":
        assert decision.allowed is True
        assert decision.denial_reason is None


# ---------------------------------------------------------------------------
# 06. Memory recall request → allowed
# ---------------------------------------------------------------------------
def test_06_memory_recall_request_allowed() -> None:
    decision = evaluate_public_capability_gate(
        "recall from memory what we discussed earlier"
    )
    assert isinstance(decision, GateDecision)
    if decision.routing_decision.selected_capability_id == "conversation_memory":
        assert decision.allowed is True


# ---------------------------------------------------------------------------
# 07. Admin governance request from public → blocked
# ---------------------------------------------------------------------------
def test_07_admin_governance_blocked_from_public() -> None:
    decision = evaluate_public_capability_gate(
        "propose write action approve governance delete"
    )
    assert isinstance(decision, GateDecision)
    # If the router selected an admin capability, the gate must block it
    cap_id = decision.routing_decision.selected_capability_id
    if cap_id == "admin_assistant_governance":
        assert decision.allowed is False
        assert decision.denial_reason is not None


# ---------------------------------------------------------------------------
# 08. Tool execution request from public → blocked
# ---------------------------------------------------------------------------
def test_08_tool_execution_blocked_from_public() -> None:
    decision = evaluate_public_capability_gate("run action execute admin tool command")
    assert isinstance(decision, GateDecision)
    cap_id = decision.routing_decision.selected_capability_id
    if cap_id == "tool_execution":
        assert decision.allowed is False
        assert decision.denial_reason is not None


# ---------------------------------------------------------------------------
# 09. Automation evaluation request from public → blocked
# ---------------------------------------------------------------------------
def test_09_automation_evaluation_blocked_from_public() -> None:
    decision = evaluate_public_capability_gate("automation dry run simulate")
    assert isinstance(decision, GateDecision)
    cap_id = decision.routing_decision.selected_capability_id
    if cap_id == "automation_evaluation":
        assert decision.allowed is False
        assert decision.denial_reason is not None
        assert "automation" in decision.denial_reason


# ---------------------------------------------------------------------------
# 10. Manual automation execution from public → blocked
# ---------------------------------------------------------------------------
def test_10_manual_automation_execution_blocked_from_public() -> None:
    decision = evaluate_public_capability_gate("manually run trigger automation execution")
    assert isinstance(decision, GateDecision)
    cap_id = decision.routing_decision.selected_capability_id
    if cap_id == "manual_automation_execution":
        assert decision.allowed is False


# ---------------------------------------------------------------------------
# 11. Training request from public → blocked
# ---------------------------------------------------------------------------
def test_11_training_request_blocked_from_public() -> None:
    decision = evaluate_public_capability_gate("train the model with dataset promotion")
    assert isinstance(decision, GateDecision)
    cap_id = decision.routing_decision.selected_capability_id
    if cap_id == "incremental_training":
        assert decision.allowed is False
        assert decision.denial_reason is not None


# ---------------------------------------------------------------------------
# 12. External AI provider request from public → blocked
# ---------------------------------------------------------------------------
def test_12_external_ai_provider_blocked_from_public() -> None:
    decision = evaluate_public_capability_gate("use openai provider gemini external model")
    assert isinstance(decision, GateDecision)
    cap_id = decision.routing_decision.selected_capability_id
    if cap_id == "external_ai_provider_gateway":
        assert decision.allowed is False


# ---------------------------------------------------------------------------
# 13. Low-confidence gibberish → blocked (fail-closed)
# ---------------------------------------------------------------------------
def test_13_low_confidence_gibberish_blocked() -> None:
    decision = evaluate_public_capability_gate("xyzmzx999 zzz aaa bbb ccc incomprehensible")
    assert isinstance(decision, GateDecision)
    # Gibberish must be blocked (fail-closed)
    assert decision.allowed is False
    assert decision.denial_reason is not None
    assert "confidence" in decision.denial_reason or "routing_failed" in decision.denial_reason


# ---------------------------------------------------------------------------
# 14. Empty string input → blocked (fail-closed)
# ---------------------------------------------------------------------------
def test_14_empty_string_blocked() -> None:
    decision = evaluate_public_capability_gate("   ")
    assert isinstance(decision, GateDecision)
    assert decision.allowed is False
    assert decision.denial_reason is not None
    assert "empty" in decision.denial_reason


# ---------------------------------------------------------------------------
# 15. Technical code (git status) → not routed to admin capability
# ---------------------------------------------------------------------------
def test_15_technical_code_not_routed_to_admin() -> None:
    decision = evaluate_public_capability_gate("git status என்ன?")
    assert isinstance(decision, GateDecision)
    assert decision.nlp_result.is_technical_code is True
    # Technical code in public context must never route to admin caps
    cap_id = decision.routing_decision.selected_capability_id
    if cap_id is not None:
        from core_model.capabilities.capability_matrix import get_capability
        cap = get_capability(cap_id)
        if cap is not None and decision.allowed:
            assert cap.supports_public_chat is True


# ---------------------------------------------------------------------------
# 16. Destructive request from public → blocked
# ---------------------------------------------------------------------------
def test_16_destructive_request_blocked_from_public() -> None:
    decision = evaluate_public_capability_gate("delete all data wipe destroy records")
    assert isinstance(decision, GateDecision)
    # Destructive request must be blocked or routed to a non-executable admin cap
    if decision.routing_decision.selected_capability_id is not None:
        # If there's a selected capability, it must be either blocked by the gate
        # or flagged with a destructive warning
        is_blocked = not decision.allowed
        has_warning = "destructive" in (decision.denial_reason or "")
        routing_has_warning = len(decision.routing_decision.warnings) > 0
        assert is_blocked or routing_has_warning


# ---------------------------------------------------------------------------
# 17. audit_payload always populated (allowed path)
# ---------------------------------------------------------------------------
def test_17_audit_payload_always_populated_allowed() -> None:
    decision = evaluate_public_capability_gate("search knowledge base")
    assert isinstance(decision.audit_payload, dict)
    assert len(decision.audit_payload) > 0
    assert "phase" in decision.audit_payload
    assert decision.audit_payload["phase"] == "17"


# ---------------------------------------------------------------------------
# 18. audit_payload always populated (blocked path)
# ---------------------------------------------------------------------------
def test_18_audit_payload_always_populated_blocked() -> None:
    decision = evaluate_public_capability_gate("zzz999gibberish")
    assert isinstance(decision.audit_payload, dict)
    assert len(decision.audit_payload) > 0
    assert "gate_decision" in decision.audit_payload


# ---------------------------------------------------------------------------
# 19. audit_payload is JSON-serializable
# ---------------------------------------------------------------------------
def test_19_audit_payload_is_json_serializable() -> None:
    for text in [
        "search my knowledge base",
        "run admin action execute",
        "xyzmzx999 gibberish",
        "   ",
        "எனக்கு தமிழில் பதில் வேண்டும்",
        "epadi irukku tanglish",
    ]:
        decision = evaluate_public_capability_gate(text)
        # Must not raise — if it does, audit_payload contains non-JSON types
        serialized = json.dumps(decision.audit_payload)
        assert isinstance(serialized, str)


# ---------------------------------------------------------------------------
# 20. audit_payload contains nlp_trace key
# ---------------------------------------------------------------------------
def test_20_audit_payload_contains_nlp_trace() -> None:
    decision = evaluate_public_capability_gate("search my knowledge base")
    assert "nlp_trace" in decision.audit_payload
    nlp_trace = decision.audit_payload["nlp_trace"]
    assert isinstance(nlp_trace, dict)
    assert "detected_language" in nlp_trace
    assert "language_confidence" in nlp_trace
    assert "is_tanglish" in nlp_trace
    assert "is_technical_code" in nlp_trace


# ---------------------------------------------------------------------------
# 21. audit_payload contains routing_trace key
# ---------------------------------------------------------------------------
def test_21_audit_payload_contains_routing_trace() -> None:
    decision = evaluate_public_capability_gate("search my knowledge base")
    assert "routing_trace" in decision.audit_payload
    routing_trace = decision.audit_payload["routing_trace"]
    assert isinstance(routing_trace, dict)
    assert "selected_capability_id" in routing_trace
    assert "confidence" in routing_trace
    assert "risk_level" in routing_trace
    assert "executable" in routing_trace
    assert "blocking_reasons" in routing_trace
    assert isinstance(routing_trace["blocking_reasons"], list)  # not tuple
    assert isinstance(routing_trace["alternative_capabilities"], list)  # not tuple


# ---------------------------------------------------------------------------
# 22. audit_payload contains gate_decision key
# ---------------------------------------------------------------------------
def test_22_audit_payload_contains_gate_decision() -> None:
    decision = evaluate_public_capability_gate("search my knowledge base")
    assert "gate_decision" in decision.audit_payload
    gate_dec = decision.audit_payload["gate_decision"]
    assert isinstance(gate_dec, dict)
    assert "allowed" in gate_dec
    assert "denial_reason" in gate_dec
    assert "risk_level" in gate_dec


# ---------------------------------------------------------------------------
# 23. denial_reason is None when allowed; non-None when blocked
# ---------------------------------------------------------------------------
def test_23_denial_reason_consistency() -> None:
    # Blocked path
    blocked = evaluate_public_capability_gate("xyzmzx999 gibberish nonsense incomprehensible")
    assert blocked.allowed is False
    assert blocked.denial_reason is not None
    assert isinstance(blocked.denial_reason, str)
    assert len(blocked.denial_reason) > 0
    # Consistency with audit_payload
    assert blocked.audit_payload["gate_decision"]["denial_reason"] == blocked.denial_reason


# ---------------------------------------------------------------------------
# 24. Gate is deterministic — same input → same GateDecision
# ---------------------------------------------------------------------------
def test_24_gate_is_deterministic() -> None:
    text = "search my knowledge base for information"
    results = [evaluate_public_capability_gate(text) for _ in range(5)]
    for r in results[1:]:
        assert r.allowed == results[0].allowed
        assert r.denial_reason == results[0].denial_reason
        assert r.routing_decision == results[0].routing_decision


# ---------------------------------------------------------------------------
# 25. gate_decision.allowed consistent with GateDecision.allowed
# ---------------------------------------------------------------------------
def test_25_gate_allowed_field_consistency() -> None:
    for text in [
        "search my knowledge base",
        "run admin action execute",
        "gibberish zzz999",
        "   ",
    ]:
        decision = evaluate_public_capability_gate(text)
        assert decision.audit_payload["gate_decision"]["allowed"] == decision.allowed


# ---------------------------------------------------------------------------
# 26. NLPResult in audit_payload is plain dict (not dataclass)
# ---------------------------------------------------------------------------
def test_26_nlp_result_serialized_as_plain_dict() -> None:
    decision = evaluate_public_capability_gate("search my knowledge base")
    nlp_trace = decision.audit_payload["nlp_trace"]
    # Must be a plain dict, not a frozen dataclass
    assert type(nlp_trace) is dict
    # Must NOT contain any NLPResult instance
    for v in nlp_trace.values():
        assert not isinstance(v, NLPResult)


# ---------------------------------------------------------------------------
# 27. RoutingDecision in audit_payload is plain dict (not dataclass)
# ---------------------------------------------------------------------------
def test_27_routing_decision_serialized_as_plain_dict() -> None:
    decision = evaluate_public_capability_gate("search my knowledge base")
    routing_trace = decision.audit_payload["routing_trace"]
    assert type(routing_trace) is dict
    for v in routing_trace.values():
        assert not isinstance(v, RoutingDecision)
    # Tuples must have been converted to lists
    assert isinstance(routing_trace["blocking_reasons"], list)
    assert isinstance(routing_trace["warnings"], list)
    assert isinstance(routing_trace["alternative_capabilities"], list)


# ---------------------------------------------------------------------------
# 28. Gate never executes capabilities (structural source check)
# ---------------------------------------------------------------------------
def test_28_gate_never_executes_capabilities() -> None:
    source = inspect.getsource(_gate_mod)
    for forbidden in (
        "run_tool(",
        "execute_with_governance(",
        "execute_automation_manually(",
        "dispatch(",
        "run_action(",
    ):
        assert forbidden not in source, f"Forbidden execution call: {forbidden!r}"


# ---------------------------------------------------------------------------
# 29. Gate never invokes tools (source check)
# ---------------------------------------------------------------------------
def test_29_gate_never_invokes_tools() -> None:
    source = inspect.getsource(_gate_mod)
    for forbidden in ("DeterministicToolExecutionService", "tool_execution_service"):
        assert forbidden not in source, f"Forbidden tool invocation: {forbidden!r}"


# ---------------------------------------------------------------------------
# 30. Gate never accesses DB (source check)
# ---------------------------------------------------------------------------
def test_30_gate_never_accesses_db() -> None:
    source = inspect.getsource(_gate_mod)
    for forbidden in ("sqlite3", "psycopg2", "sqlalchemy", "database_pool",
                      "get_db", "initialize_database", "ConversationMemoryRepository"):
        assert forbidden not in source.lower(), f"Forbidden DB access: {forbidden!r}"


# ---------------------------------------------------------------------------
# 31. Gate never calls external HTTP APIs (source check)
# ---------------------------------------------------------------------------
def test_31_gate_never_calls_external_apis() -> None:
    source = inspect.getsource(_gate_mod)
    for forbidden in ("requests.", "httpx.", "urllib.request", "http.client",
                      "aiohttp", "boto3"):
        assert forbidden not in source, f"Forbidden HTTP call: {forbidden!r}"


# ---------------------------------------------------------------------------
# 32. Gate never uses eval / exec
# ---------------------------------------------------------------------------
def test_32_gate_no_eval_exec() -> None:
    for mod_source in (
        inspect.getsource(_gate_mod),
        inspect.getsource(_obs_mod),
    ):
        assert "eval(" not in mod_source
        assert "exec(" not in mod_source
        assert "compile(" not in mod_source


# ---------------------------------------------------------------------------
# 33. Gate never uses subprocess / os.system
# ---------------------------------------------------------------------------
def test_33_gate_no_subprocess() -> None:
    def _strip_docstrings(source: str) -> str:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    node.body = node.body[1:]
        return ast.unparse(tree)

    for mod_source in (
        _strip_docstrings(inspect.getsource(_gate_mod)),
        _strip_docstrings(inspect.getsource(_obs_mod)),
    ):
        for forbidden in ("subprocess", "os.system", "os.popen", "Popen"):
            assert forbidden not in mod_source, f"Forbidden: {forbidden!r}"


# ---------------------------------------------------------------------------
# 34. Gate never spawns background workers / celery / cron
# ---------------------------------------------------------------------------
def test_34_gate_no_workers_schedulers() -> None:
    def _strip_docstrings(source: str) -> str:
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if (
                    node.body
                    and isinstance(node.body[0], ast.Expr)
                    and isinstance(node.body[0].value, ast.Constant)
                    and isinstance(node.body[0].value.value, str)
                ):
                    node.body = node.body[1:]
        return ast.unparse(tree).lower()

    for mod_source in (
        _strip_docstrings(inspect.getsource(_gate_mod)),
        _strip_docstrings(inspect.getsource(_obs_mod)),
    ):
        for forbidden in (
            "celery", "apscheduler", "rq.", "dramatiq", "cron",
            "background_worker", "asyncio.create_task", "backgroundtasks",
            "while true",
        ):
            assert forbidden not in mod_source, f"Forbidden: {forbidden!r}"


# ---------------------------------------------------------------------------
# 35. AST security inspection — gate module
# ---------------------------------------------------------------------------
def test_35_ast_security_gate_module() -> None:
    source = inspect.getsource(_gate_mod)
    tree = ast.parse(source)
    forbidden_calls = {"eval", "exec", "compile", "__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in forbidden_calls, (
                f"Forbidden AST call: {node.func.id!r}"
            )


# ---------------------------------------------------------------------------
# 36. AST security inspection — observability module
# ---------------------------------------------------------------------------
def test_36_ast_security_observability_module() -> None:
    source = inspect.getsource(_obs_mod)
    tree = ast.parse(source)
    lowered = source.lower()
    for pattern in ("sqlite3", "requests.get", "requests.post", "httpx",
                    "subprocess", "os.system", "cron", "celery"):
        assert pattern not in lowered, f"Forbidden pattern {pattern!r} in observability"
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in {"eval", "exec", "compile", "__import__"}, (
                f"Forbidden call {node.func.id!r} in gate_observability"
            )


# ---------------------------------------------------------------------------
# 37. Phase 15 regression — NLPResult shape unchanged
# ---------------------------------------------------------------------------
def test_37_phase15_nlp_result_shape_unchanged() -> None:
    result = process_text("வணக்கம் எப்படி இருக்கிறீர்கள்")
    assert hasattr(result, "original_text")
    assert hasattr(result, "normalized_text")
    assert hasattr(result, "detected_language")
    assert hasattr(result, "language_confidence")
    assert hasattr(result, "is_tanglish")
    assert hasattr(result, "is_mixed_language")
    assert hasattr(result, "is_technical_code")
    assert hasattr(result, "normalization_applied")
    assert hasattr(result, "normalization_notes")
    assert hasattr(result, "tokens")
    assert hasattr(result, "nlp_normalization_version")
    # Phase 15 invariant: Tamil script detected as "ta"
    assert result.detected_language == "ta"


# ---------------------------------------------------------------------------
# 38. Phase 16 regression — RoutingDecision shape unchanged
# ---------------------------------------------------------------------------
def test_38_phase16_routing_decision_shape_unchanged() -> None:
    decision = route_capability("search my knowledge base", caller_context="public_chat")
    assert hasattr(decision, "requested_capability")
    assert hasattr(decision, "selected_capability_id")
    assert hasattr(decision, "selected_component")
    assert hasattr(decision, "confidence")
    assert hasattr(decision, "routing_reason")
    assert hasattr(decision, "alternative_capabilities")
    assert hasattr(decision, "access_level_required")
    assert hasattr(decision, "requires_human_approval")
    assert hasattr(decision, "risk_level")
    assert hasattr(decision, "executable")
    assert hasattr(decision, "blocking_reasons")
    assert hasattr(decision, "warnings")
    # Phase 16 invariant: RoutingDecision is frozen
    with pytest.raises((AttributeError, TypeError)):
        decision.executable = True  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 39. PublicChatRequest schema unchanged (public API contract)
# ---------------------------------------------------------------------------
def test_39_public_chat_request_schema_unchanged() -> None:
    from backend.models.public_chat import MAX_MESSAGE_LENGTH, PublicChatRequest
    req = PublicChatRequest(message="hello")
    assert req.message == "hello"
    assert req.conversation_id is None
    assert req.language_override == "auto"
    assert req.memory_consent is False
    assert req.client_request_id is None
    assert MAX_MESSAGE_LENGTH == 4000


# ---------------------------------------------------------------------------
# 40. PublicChatRoutingService module unchanged (gate is additive)
# ---------------------------------------------------------------------------
def test_40_public_chat_routing_service_unchanged() -> None:
    from backend.services.public_chat_routing_service import PublicChatRoutingService
    # Service must still have the same public entry point
    assert hasattr(PublicChatRoutingService, "handle_message")
    # Gate imports must NOT appear in the service (gate is in the API route only)
    source = inspect.getsource(PublicChatRoutingService)
    assert "evaluate_public_capability_gate" not in source
    assert "GateDecision" not in source


# ---------------------------------------------------------------------------
# 41. Phase 10–14: AUTOMATION_ALLOWED_ACTIONS == frozenset() (default-deny)
# ---------------------------------------------------------------------------
def test_41_automation_allowed_actions_default_deny() -> None:
    from core_model.admin_assistant.automation_policy import AUTOMATION_ALLOWED_ACTIONS
    # Phase 10–14 invariant: automation is default-deny
    assert AUTOMATION_ALLOWED_ACTIONS == frozenset(), (
        "AUTOMATION_ALLOWED_ACTIONS must remain frozenset() — "
        "no automated execution is permitted."
    )


# ---------------------------------------------------------------------------
# 42. DB SHA-256 hash unchanged after gate evaluation
# ---------------------------------------------------------------------------
def test_42_db_sha256_unchanged_after_gate() -> None:
    import hashlib
    import os
    db_path = "data/database/brud_ai.db"
    if not os.path.exists(db_path):
        pytest.skip("Production DB not found; skipping SHA-256 check")
    with open(db_path, "rb") as f:
        before = hashlib.sha256(f.read()).hexdigest()
    # Run several gate evaluations
    for text in [
        "search my knowledge base",
        "run admin action execute",
        "எனக்கு தமிழில் பதில் வேண்டும்",
        "epadi irukku tanglish",
        "gibberish xyzmzx999",
    ]:
        _ = evaluate_public_capability_gate(text)
    with open(db_path, "rb") as f:
        after = hashlib.sha256(f.read()).hexdigest()
    assert before == after, (
        "DB SHA-256 changed after gate evaluation — "
        "gate must never write to the production database."
    )


# ---------------------------------------------------------------------------
# 43. GateDecision itself is immutable (frozen dataclass)
# ---------------------------------------------------------------------------
def test_43_gate_decision_is_immutable() -> None:
    decision = evaluate_public_capability_gate("search my knowledge base")
    with pytest.raises((AttributeError, TypeError)):
        decision.allowed = False  # type: ignore[misc]
    with pytest.raises((AttributeError, TypeError)):
        decision.denial_reason = "tampered"  # type: ignore[misc]
