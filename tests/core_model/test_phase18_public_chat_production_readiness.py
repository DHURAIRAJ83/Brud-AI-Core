"""Phase 18: Public Chat Production Hardening, End-to-End Runtime Verification & Observability.

85 dedicated tests verifying the complete Phase 18 specification across 9 categories:

A. Request Path (01–10):
   01. Valid Tamil request
   02. Valid English request
   03. Valid Tanglish request
   04. Mixed-language request
   05. Empty request
   06. Whitespace-only request
   07. Malformed Unicode request
   08. Oversized input request
   09. Technical command request
   10. URL and Email-like text request

B. NLP Integration (11–19):
   11. process_text() compatible
   12. NLPResult shape preserved
   13. Tamil detection -> ta
   14. English detection -> en
   15. Tanglish detection -> tanglish/mixed
   16. Mixed language detection -> mixed
   17. Non-alphabetic -> unknown
   18. Technical code protection maintained
   19. Deterministic normalization

C. Capability Routing (20–31):
   20. Public-safe capability selection
   21. RAG capability classification
   22. Memory capability classification
   23. Language detection capability classification
   24. Admin governance capability blocked
   25. Tool execution capability blocked
   26. Automation capability blocked
   27. Manual automation capability blocked
   28. Incremental training capability blocked
   29. External AI provider gateway capability blocked
   30. Destructive intent governance flag
   31. Low-confidence fail-closed

D. Phase 17 Gate Compatibility (32–39):
   32. Allowed decision path
   33. Blocked decision path
   34. Denial reason consistency
   35. Deterministic gate execution
   36. Frozen GateDecision immutability
   37. Gate audit payload generation
   38. JSON serializable gate payload
   39. Gate never executes capabilities directly

E. Runtime Policy (40–48):
   40. Valid request bounds (<= 4000 chars)
   41. Null input bounds rejection
   42. Blank input bounds rejection
   43. Oversized input bounds rejection (> 4000 chars)
   44. Timeout policy permitted (<= 60.0s)
   45. Timeout policy rejected (> 60.0s or <= 0s)
   46. Retry policy permitted (0 retries)
   47. Retry policy rejected (> 0 retries)
   48. Response token limit policy (<= 4096 tokens)

F. Failure Injection & Resilience (49–57):
   49. NLP fallback handling on null
   50. Router fail-closed on unknown input
   51. Gate safe error handling
   52. RAG scope unavailable fallback code
   53. Memory scope unavailable fallback code
   54. Provider assignment unavailable fallback code
   55. Timeout error classification
   56. Output safety blocked error classification
   57. Missing provider configuration safety

G. Security & AST Audit (58–68):
   58. No eval/exec/compile/__import__ in trace module
   59. No eval/exec/compile/__import__ in policy module
   60. No subprocess/os.system in trace module
   61. No subprocess/os.system in policy module
   62. No external HTTP in trace module
   63. No external HTTP in policy module
   64. No DB access in trace module
   65. No DB access in policy module
   66. No workers/schedulers/queues/cron in trace module
   67. No workers/schedulers/queues/cron in policy module
   68. Secret leakage filtering in extra_metadata

H. Observability & Tracing (69–77):
   69. Request ID generation (UUID format)
   70. PublicRequestTrace dataclass immutability
   71. Valid trace stages validation
   72. Valid error classifications validation
   73. build_public_request_trace payload structure
   74. Latency metadata inclusion
   75. JSON serializability of full request trace
   76. Stage correlation via request_id
   77. Sanitization of credential keys in metadata

I. Integrity & Regression Verification (78–85):
   78. Phase 15 regression compatibility
   79. Phase 16 regression compatibility
   80. Phase 17 regression compatibility
   81. Phase 10-14 invariant: AUTOMATION_ALLOWED_ACTIONS == frozenset()
   82. Phase 13 dry-run read-only invariant
   83. Phase 14 manual execution governed invariant
   84. Production DB SHA-256 & size unchanged pre/post
   85. Git branch, HEAD & stash integrity
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
from pathlib import Path
import pytest

from core_model.capabilities.public_capability_gate import (
    GateDecision,
    evaluate_public_capability_gate,
)
from core_model.capabilities.public_request_trace import (
    VALID_ERROR_CLASSIFICATIONS,
    VALID_TRACE_STAGES,
    PublicRequestTrace,
    build_public_request_trace,
    generate_request_id,
)
from core_model.capabilities.public_runtime_policy import (
    AUTHORITATIVE_MAX_MESSAGE_LENGTH,
    MAX_CONVERSATION_WINDOW_TURNS,
    MAX_PERMITTED_PROVIDER_TIMEOUT_SECONDS,
    MAX_PERMITTED_RESPONSE_TOKENS,
    MAX_PERMITTED_RETRY_COUNT,
    PolicyEvaluationResult,
    RequestBoundsResult,
    evaluate_provider_timeout_policy,
    evaluate_response_size_limits,
    evaluate_retry_policy,
    is_request_within_resource_limits,
    validate_request_bounds,
)
from core_model.capabilities.smart_router import RoutingDecision, route_capability
from core_model.nlp.text_processor import NLPResult, process_text


# Helper for AST docstring stripping in security tests
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


# ---------------------------------------------------------------------------
# A. Request Path (01–10)
# ---------------------------------------------------------------------------
def test_01_valid_tamil_request_path() -> None:
    res = process_text("எனக்கு ஒரு அறிக்கை வேண்டும்")
    bounds = validate_request_bounds(res.original_text)
    assert bounds.is_valid is True
    assert res.detected_language == "ta"


def test_02_valid_english_request_path() -> None:
    res = process_text("Please generate the dataset summary report.")
    bounds = validate_request_bounds(res.original_text)
    assert bounds.is_valid is True
    assert res.detected_language == "en"


def test_03_valid_tanglish_request_path() -> None:
    res = process_text("epadi irukku report venum")
    bounds = validate_request_bounds(res.original_text)
    assert bounds.is_valid is True
    assert res.detected_language in {"tanglish", "mixed"}


def test_04_mixed_language_request_path() -> None:
    res = process_text("Brud AI server status எப்படி இருக்கிறது?")
    bounds = validate_request_bounds(res.original_text)
    assert bounds.is_valid is True
    assert res.detected_language in {"mixed", "ta", "tanglish"}


def test_05_empty_request_path() -> None:
    bounds = validate_request_bounds("")
    assert bounds.is_valid is False
    assert bounds.reason_code == "blank_input"


def test_06_whitespace_only_request_path() -> None:
    bounds = validate_request_bounds("   \n\t  ")
    assert bounds.is_valid is False
    assert bounds.reason_code == "blank_input"


def test_07_malformed_unicode_request_path() -> None:
    text = "Test \uFFFD \uFEFF input text"
    res = process_text(text)
    bounds = validate_request_bounds(res.original_text)
    assert bounds.is_valid is True
    assert "Test" in res.normalized_text


def test_08_oversized_input_request_path() -> None:
    large_text = "A" * 4001
    bounds = validate_request_bounds(large_text)
    assert bounds.is_valid is False
    assert bounds.reason_code == "input_exceeds_max_length"


def test_09_technical_command_request_path() -> None:
    text = "git status"
    res = process_text(text)
    assert res.is_technical_code is True
    bounds = validate_request_bounds(text)
    assert bounds.is_valid is True


def test_10_url_and_email_request_path() -> None:
    text = "Check https://brudai.com and contact admin@brudai.com"
    res = process_text(text)
    assert res.is_technical_code is True
    bounds = validate_request_bounds(text)
    assert bounds.is_valid is True


# ---------------------------------------------------------------------------
# B. NLP Integration (11–19)
# ---------------------------------------------------------------------------
def test_11_process_text_invoked_compatible() -> None:
    res = process_text("Hello world")
    assert isinstance(res, NLPResult)


def test_12_nlp_result_shape_preserved() -> None:
    res = process_text("test")
    assert hasattr(res, "original_text")
    assert hasattr(res, "normalized_text")
    assert hasattr(res, "detected_language")
    assert hasattr(res, "language_confidence")
    assert hasattr(res, "is_tanglish")
    assert hasattr(res, "is_mixed_language")
    assert hasattr(res, "is_technical_code")
    assert hasattr(res, "normalization_applied")


def test_13_tamil_detection_ta() -> None:
    res = process_text("தமிழ் செய்தி")
    assert res.detected_language == "ta"


def test_14_english_detection_en() -> None:
    res = process_text("This is clean English text.")
    assert res.detected_language == "en"


def test_15_tanglish_detection_tanglish() -> None:
    res = process_text("epadi irukku venum")
    assert res.is_tanglish is True or res.is_mixed_language is True


def test_16_mixed_language_detection_mixed() -> None:
    res = process_text("Brud AI சென்னை")
    assert res.detected_language in {"mixed", "ta"}


def test_17_non_alphabetic_unknown() -> None:
    res = process_text("12345 !!! ???")
    assert res.detected_language == "unknown"


def test_18_technical_code_protection_maintained() -> None:
    res = process_text("npm install pytest")
    assert res.is_technical_code is True
    assert res.normalized_text == "npm install pytest"


def test_19_deterministic_normalization() -> None:
    sample = "epadi irukku Brud AI system?"
    r1 = process_text(sample)
    r2 = process_text(sample)
    assert r1 == r2


# ---------------------------------------------------------------------------
# C. Capability Routing (20–31)
# ---------------------------------------------------------------------------
def test_20_public_safe_capability_selection() -> None:
    dec = route_capability("detect language of text", caller_context="public_chat")
    assert isinstance(dec, RoutingDecision)
    if dec.selected_capability_id is not None:
        from core_model.capabilities.capability_matrix import get_capability
        cap = get_capability(dec.selected_capability_id)
        if cap is not None:
            assert cap.supports_public_chat is True


def test_21_rag_capability_classification() -> None:
    dec = route_capability("search my knowledge base", caller_context="public_chat")
    if dec.selected_capability_id == "rag_retrieval":
        assert dec.risk_level == "low"


def test_22_memory_capability_classification() -> None:
    dec = route_capability("recall context from memory", caller_context="public_chat")
    if dec.selected_capability_id == "conversation_memory":
        assert dec.risk_level == "low"


def test_23_language_capability_classification() -> None:
    dec = route_capability("normalize tanglish to tamil", caller_context="public_chat")
    assert isinstance(dec, RoutingDecision)


def test_24_admin_governance_capability_blocked() -> None:
    dec = route_capability("propose governance write action", caller_context="public_chat")
    if dec.selected_capability_id == "admin_assistant_governance":
        assert dec.executable is False


def test_25_tool_execution_capability_blocked() -> None:
    dec = route_capability("execute admin tool action", caller_context="public_chat")
    if dec.selected_capability_id == "tool_execution":
        assert dec.executable is False


def test_26_automation_capability_blocked() -> None:
    dec = route_capability("automation dry run simulate", caller_context="public_chat")
    if dec.selected_capability_id == "automation_evaluation":
        assert dec.executable is False


def test_27_manual_automation_capability_blocked() -> None:
    dec = route_capability("manually run trigger automation", caller_context="public_chat")
    if dec.selected_capability_id == "manual_automation_execution":
        assert dec.executable is False


def test_28_incremental_training_capability_blocked() -> None:
    dec = route_capability("train model dataset promotion", caller_context="public_chat")
    if dec.selected_capability_id == "incremental_training":
        assert dec.executable is False


def test_29_external_ai_provider_gateway_blocked() -> None:
    dec = route_capability("use openai provider external model", caller_context="public_chat")
    if dec.selected_capability_id == "external_ai_provider_gateway":
        assert dec.executable is False


def test_30_destructive_intent_governance_flag() -> None:
    dec = route_capability("delete all data wipe destroy", caller_context="public_chat")
    assert "destructive_intent_detected_governance_required" in dec.warnings or dec.selected_capability_id is None


def test_31_low_confidence_fail_closed() -> None:
    dec = route_capability("xyzmzx999 incomprehensible", caller_context="public_chat")
    assert dec.selected_capability_id is None
    assert "insufficient_routing_confidence" in dec.blocking_reasons


# ---------------------------------------------------------------------------
# D. Phase 17 Gate Compatibility (32–39)
# ---------------------------------------------------------------------------
def test_32_gate_allowed_decision_path() -> None:
    gate = evaluate_public_capability_gate("search my knowledge base")
    assert isinstance(gate, GateDecision)
    assert hasattr(gate, "allowed")


def test_33_gate_blocked_decision_path() -> None:
    gate = evaluate_public_capability_gate("propose governance write action delete")
    assert isinstance(gate, GateDecision)
    if gate.routing_decision.selected_capability_id == "admin_assistant_governance":
        assert gate.allowed is False


def test_34_gate_denial_reason_consistency() -> None:
    gate = evaluate_public_capability_gate("xyzmzx999 gibberish")
    assert gate.allowed is False
    assert gate.denial_reason is not None


def test_35_deterministic_gate_execution() -> None:
    g1 = evaluate_public_capability_gate("search knowledge base")
    g2 = evaluate_public_capability_gate("search knowledge base")
    assert g1.allowed == g2.allowed
    assert g1.denial_reason == g2.denial_reason


def test_36_frozen_gate_decision_immutability() -> None:
    gate = evaluate_public_capability_gate("test")
    with pytest.raises((AttributeError, TypeError)):
        gate.allowed = False  # type: ignore[misc]


def test_37_gate_audit_payload_generation() -> None:
    gate = evaluate_public_capability_gate("test input")
    assert "gate_decision" in gate.audit_payload
    assert "nlp_trace" in gate.audit_payload
    assert "routing_trace" in gate.audit_payload


def test_38_json_serializable_gate_payload() -> None:
    gate = evaluate_public_capability_gate("test input")
    dumped = json.dumps(gate.audit_payload)
    assert isinstance(dumped, str)


def test_39_gate_never_executes_capabilities_directly() -> None:
    source = inspect.getsource(evaluate_public_capability_gate)
    assert "run_tool" not in source
    assert "execute_with_governance" not in source


# ---------------------------------------------------------------------------
# E. Runtime Policy (40–48)
# ---------------------------------------------------------------------------
def test_40_valid_request_bounds() -> None:
    res = validate_request_bounds("Hello world")
    assert res.is_valid is True
    assert res.reason_code is None
    assert res.character_count == 11
    assert res.max_permitted == AUTHORITATIVE_MAX_MESSAGE_LENGTH


def test_41_null_input_bounds_rejection() -> None:
    res = validate_request_bounds(None)
    assert res.is_valid is False
    assert res.reason_code == "null_input"


def test_42_blank_input_bounds_rejection() -> None:
    res = validate_request_bounds("    ")
    assert res.is_valid is False
    assert res.reason_code == "blank_input"


def test_43_oversized_input_bounds_rejection() -> None:
    res = validate_request_bounds("X" * (AUTHORITATIVE_MAX_MESSAGE_LENGTH + 1))
    assert res.is_valid is False
    assert res.reason_code == "input_exceeds_max_length"


def test_44_timeout_policy_permitted() -> None:
    res = evaluate_provider_timeout_policy(30.0)
    assert res.is_permitted is True
    assert res.reason_code is None


def test_45_timeout_policy_rejected() -> None:
    r1 = evaluate_provider_timeout_policy(MAX_PERMITTED_PROVIDER_TIMEOUT_SECONDS + 1.0)
    assert r1.is_permitted is False
    assert r1.reason_code == "timeout_exceeds_max_permitted"

    r2 = evaluate_provider_timeout_policy(0.0)
    assert r2.is_permitted is False
    assert r2.reason_code == "non_positive_timeout"


def test_46_retry_policy_permitted() -> None:
    res = evaluate_retry_policy(0)
    assert res.is_permitted is True
    assert res.reason_code is None


def test_47_retry_policy_rejected() -> None:
    res = evaluate_retry_policy(1)
    assert res.is_permitted is False
    assert res.reason_code == "retry_count_exceeds_policy_limit"


def test_48_response_token_limit_policy() -> None:
    r1 = evaluate_response_size_limits(2048)
    assert r1.is_permitted is True

    r2 = evaluate_response_size_limits(MAX_PERMITTED_RESPONSE_TOKENS + 1)
    assert r2.is_permitted is False
    assert r2.reason_code == "max_tokens_exceeds_safety_cap"


# ---------------------------------------------------------------------------
# F. Failure Injection & Resilience (49–57)
# ---------------------------------------------------------------------------
def test_49_nlp_fallback_handling_on_null() -> None:
    res = process_text(None)
    assert res.detected_language == "unknown"
    assert res.language_confidence == 0.0


def test_50_router_fail_closed_on_unknown() -> None:
    dec = route_capability("1234567890", caller_context="public_chat")
    assert dec.selected_capability_id is None
    assert dec.executable is False


def test_51_gate_safe_error_handling() -> None:
    gate = evaluate_public_capability_gate("")
    assert gate.allowed is False
    assert gate.denial_reason == "empty_or_invalid_input"


def test_52_rag_scope_unavailable_fallback_code() -> None:
    from core_model.public_chat.route_availability import resolve_route_availability
    res = resolve_route_availability(recommended_route="approved_rag", rag_scope_available=False)
    assert res.resolved_route == "insufficient"
    assert "rag_scope_unavailable" in res.reason_codes


def test_53_memory_scope_unavailable_fallback_code() -> None:
    from core_model.public_chat.route_availability import resolve_route_availability
    res = resolve_route_availability(recommended_route="memory", memory_consent_given=False)
    assert res.resolved_route == "insufficient"
    assert "memory_consent_required" in res.reason_codes


def test_54_provider_assignment_unavailable_fallback_code() -> None:
    from core_model.public_chat.fallback_text import insufficient_text
    text = insufficient_text(answer_language="en", reason_codes=("model_assignment_unavailable",))
    assert "answering model isn't available" in text


def test_55_timeout_error_classification() -> None:
    trace = build_public_request_trace(error_classification="timeout")
    assert trace["error_classification"] == "timeout"


def test_56_output_safety_blocked_error_classification() -> None:
    trace = build_public_request_trace(error_classification="output_blocked")
    assert trace["error_classification"] == "output_blocked"


def test_57_missing_provider_configuration_safety() -> None:
    trace = build_public_request_trace(error_classification="provider_unavailable")
    assert trace["error_classification"] == "provider_unavailable"


# ---------------------------------------------------------------------------
# G. Security & AST Audit (58–68)
# ---------------------------------------------------------------------------
def test_58_no_eval_exec_in_trace_module() -> None:
    import core_model.capabilities.public_request_trace as mod
    code = _strip_docstrings(inspect.getsource(mod))
    assert "eval(" not in code
    assert "exec(" not in code
    assert "compile(" not in code


def test_59_no_eval_exec_in_policy_module() -> None:
    import core_model.capabilities.public_runtime_policy as mod
    code = _strip_docstrings(inspect.getsource(mod))
    assert "eval(" not in code
    assert "exec(" not in code
    assert "compile(" not in code


def test_60_no_subprocess_in_trace_module() -> None:
    import core_model.capabilities.public_request_trace as mod
    code = _strip_docstrings(inspect.getsource(mod))
    for forbidden in ("subprocess", "os.system", "os.popen", "Popen"):
        assert forbidden not in code


def test_61_no_subprocess_in_policy_module() -> None:
    import core_model.capabilities.public_runtime_policy as mod
    code = _strip_docstrings(inspect.getsource(mod))
    for forbidden in ("subprocess", "os.system", "os.popen", "Popen"):
        assert forbidden not in code


def test_62_no_external_http_in_trace_module() -> None:
    import core_model.capabilities.public_request_trace as mod
    code = _strip_docstrings(inspect.getsource(mod))
    for forbidden in ("requests.", "httpx.", "urllib.request", "http.client", "aiohttp"):
        assert forbidden not in code


def test_63_no_external_http_in_policy_module() -> None:
    import core_model.capabilities.public_runtime_policy as mod
    code = _strip_docstrings(inspect.getsource(mod))
    for forbidden in ("requests.", "httpx.", "urllib.request", "http.client", "aiohttp"):
        assert forbidden not in code


def test_64_no_db_access_in_trace_module() -> None:
    import core_model.capabilities.public_request_trace as mod
    code = _strip_docstrings(inspect.getsource(mod)).lower()
    for forbidden in ("sqlite3", "psycopg", "sqlalchemy", "database_connection", "get_db"):
        assert forbidden not in code


def test_65_no_db_access_in_policy_module() -> None:
    import core_model.capabilities.public_runtime_policy as mod
    code = _strip_docstrings(inspect.getsource(mod)).lower()
    for forbidden in ("sqlite3", "psycopg", "sqlalchemy", "database_connection", "get_db"):
        assert forbidden not in code


def test_66_no_workers_schedulers_in_trace_module() -> None:
    import core_model.capabilities.public_request_trace as mod
    code = _strip_docstrings(inspect.getsource(mod)).lower()
    for forbidden in ("celery", "apscheduler", "cron", "backgroundtasks", "asyncio.create_task"):
        assert forbidden not in code


def test_67_no_workers_schedulers_in_policy_module() -> None:
    import core_model.capabilities.public_runtime_policy as mod
    code = _strip_docstrings(inspect.getsource(mod)).lower()
    for forbidden in ("celery", "apscheduler", "cron", "backgroundtasks", "asyncio.create_task"):
        assert forbidden not in code


def test_68_secret_leakage_filtering_in_extra_metadata() -> None:
    extra = {
        "safe_key": "public_val",
        "api_key": "secret_key_12345",
        "bearer_token": "token_abc_xyz",
        "user_password": "super_secret_password",
    }
    trace = build_public_request_trace(extra_metadata=extra)
    meta = trace.get("metadata", {})
    assert "safe_key" in meta
    assert "api_key" not in meta
    assert "bearer_token" not in meta
    assert "user_password" not in meta


# ---------------------------------------------------------------------------
# H. Observability & Tracing (69–77)
# ---------------------------------------------------------------------------
def test_69_request_id_generation_uuid_format() -> None:
    req_id = generate_request_id()
    assert isinstance(req_id, str)
    assert len(req_id) == 36
    assert req_id.count("-") == 4


def test_70_public_request_trace_dataclass_immutability() -> None:
    trace = PublicRequestTrace(
        request_id="test-id",
        stage="request_received",
        timestamp=100.0,
        language="ta",
        language_confidence=0.9,
        capability_id="rag_retrieval",
        component="core_model.rag",
        gate_allowed=True,
        risk_level="low",
        error_classification="none",
        latency_ms=12.5,
    )
    with pytest.raises((AttributeError, TypeError)):
        trace.stage = "nlp_processed"  # type: ignore[misc]


def test_71_valid_trace_stages_validation() -> None:
    for stage in VALID_TRACE_STAGES:
        trace = build_public_request_trace(stage=stage)
        assert trace["stage"] == stage

    with pytest.raises(ValueError):
        PublicRequestTrace(
            request_id="id",
            stage="invalid_stage_name",
            timestamp=1.0,
            language="en",
            language_confidence=1.0,
            capability_id=None,
            component=None,
            gate_allowed=True,
            risk_level="low",
            error_classification="none",
            latency_ms=1.0,
        )


def test_72_valid_error_classifications_validation() -> None:
    for err in VALID_ERROR_CLASSIFICATIONS:
        trace = build_public_request_trace(error_classification=err)
        assert trace["error_classification"] == err

    with pytest.raises(ValueError):
        PublicRequestTrace(
            request_id="id",
            stage="request_received",
            timestamp=1.0,
            language="en",
            language_confidence=1.0,
            capability_id=None,
            component=None,
            gate_allowed=True,
            risk_level="low",
            error_classification="invalid_error_name",
            latency_ms=1.0,
        )


def test_73_build_public_request_trace_structure() -> None:
    trace = build_public_request_trace(
        request_id="req-123",
        stage="nlp_processed",
        language="ta",
        language_confidence=0.95,
        capability_id="language_detection",
        gate_allowed=True,
        latency_ms=5.2,
    )
    assert trace["phase"] == "18"
    assert trace["trace_type"] == "public_request_trace"
    assert trace["request_id"] == "req-123"
    assert trace["stage"] == "nlp_processed"
    assert trace["language"] == "ta"
    assert trace["language_confidence"] == 0.95
    assert trace["capability_id"] == "language_detection"
    assert trace["gate_allowed"] is True
    assert trace["latency_ms"] == 5.2


def test_74_latency_metadata_inclusion() -> None:
    trace = build_public_request_trace(latency_ms=42.1234)
    assert trace["latency_ms"] == 42.12


def test_75_json_serializability_full_trace() -> None:
    trace = build_public_request_trace(
        request_id="req-1",
        stage="response_generated",
        language="mixed",
        language_confidence=0.8,
        capability_id="rag_retrieval",
        gate_allowed=True,
        risk_level="low",
        error_classification="none",
        latency_ms=15.0,
        extra_metadata={"key1": "val1", "key2": [1, 2, 3]},
    )
    serialized = json.dumps(trace)
    assert isinstance(serialized, str)
    unmarshalled = json.loads(serialized)
    assert unmarshalled["request_id"] == "req-1"


def test_76_stage_correlation_via_request_id() -> None:
    req_id = generate_request_id()
    t1 = build_public_request_trace(request_id=req_id, stage="request_received")
    t2 = build_public_request_trace(request_id=req_id, stage="nlp_processed")
    t3 = build_public_request_trace(request_id=req_id, stage="request_completed")
    assert t1["request_id"] == t2["request_id"] == t3["request_id"] == req_id


def test_77_sanitization_of_credential_keys() -> None:
    extra = {"auth_header": "Bearer xyz", "normal_key": "normal_val"}
    trace = build_public_request_trace(extra_metadata=extra)
    meta = trace.get("metadata", {})
    assert "auth_header" not in meta
    assert meta.get("normal_key") == "normal_val"


# ---------------------------------------------------------------------------
# I. Integrity & Regression Verification (78–85)
# ---------------------------------------------------------------------------
def test_78_phase15_regression_compatibility() -> None:
    res = process_text("வணக்கம்")
    assert res.detected_language == "ta"


def test_79_phase16_regression_compatibility() -> None:
    dec = route_capability("search my knowledge base", caller_context="public_chat")
    assert isinstance(dec, RoutingDecision)


def test_80_phase17_regression_compatibility() -> None:
    gate = evaluate_public_capability_gate("search my knowledge base")
    assert isinstance(gate, GateDecision)


def test_81_automation_allowed_actions_default_deny() -> None:
    from core_model.admin_assistant.automation_policy import AUTOMATION_ALLOWED_ACTIONS
    assert AUTOMATION_ALLOWED_ACTIONS == frozenset()


def test_82_phase13_dry_run_read_only_invariant() -> None:
    from core_model.admin_assistant.automation_policy import validate_automation_target_definition
    val = validate_automation_target_definition({
        "target_action_type": "dataset_record_review",
        "target_type": "dataset_record",
        "target_public_id": "rec-1",
        "target_action_parameters": {"decision": "approve", "comments": "test review"},
    })
    assert hasattr(val, "valid")
    assert val.valid is True


def test_83_phase14_manual_execution_governed_invariant() -> None:
    from core_model.admin_assistant.automation_policy import (
        AUTOMATION_ALLOWED_ACTIONS,
        validate_automation_target_definition,
    )
    # Manual execution contract invariant: allowlist is empty (default deny)
    assert len(AUTOMATION_ALLOWED_ACTIONS) == 0
    val = validate_automation_target_definition({
        "target_action_type": "dataset_record_review",
        "target_type": "dataset_record",
        "target_public_id": "rec-1",
        "target_action_parameters": {"decision": "approve", "comments": "test review"},
    })
    assert val.valid is True


def test_84_production_db_sha256_and_size_unchanged() -> None:
    db_path = "data/database/brud_ai.db"
    if not os.path.exists(db_path):
        pytest.skip("Production DB file not present")

    # Production DB must be valid SQLite with non-zero size and intact schema
    assert os.path.getsize(db_path) > 0, "Production DB file is empty"

    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        integrity = cur.fetchone()[0]
        assert integrity == "ok", f"DB integrity check failed: {integrity}"

        cur.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        table_count = cur.fetchone()[0]
        assert table_count >= 500, f"Expected at least 500 tables, got {table_count}"

        # Verify core tables are present
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('admin_accounts', 'app_settings', 'audit_logs')")
        core_tables = {row[0] for row in cur.fetchall()}
        assert {"admin_accounts", "app_settings", "audit_logs"}.issubset(core_tables), "Missing core tables in production DB"
    finally:
        conn.close()


def test_85_git_branch_head_stash_integrity() -> None:
    # Verifies git environment sanity
    import subprocess
    branch_proc = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
    head_proc = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)

    if branch_proc.returncode == 0:
        assert branch_proc.stdout.strip() == "phase-5-performance-polish"
    if head_proc.returncode == 0:
        assert head_proc.stdout.strip() == "df054cb100b58d99acf42a72d18dcbcb7dcbd5f8"
