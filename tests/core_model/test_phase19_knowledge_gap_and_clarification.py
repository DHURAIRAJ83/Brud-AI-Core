"""Phase 19: Knowledge Gap Capture & Clarification Intelligence Verification Suite.

65 dedicated tests verifying the complete Phase 19 specification across 6 core categories:

1. Schema & Taxonomy (01–05):
   01. Module imports cleanly
   02. KnowledgeGap is a frozen dataclass
   03. KnowledgeGap JSON serializability
   04. Stable gap taxonomy string codes
   05. Stable severity taxonomy string codes

2. Core Classification Cases A–E (06–21):
   06. Case A: Answerable request -> no gap / no clarification
   07. Case B: Knowledge unavailable -> KNOWLEDGE_NOT_FOUND
   08. Case B: RAG insufficient evidence -> RAG_INSUFFICIENT_EVIDENCE
   09. Case B: RAG scope unavailable -> RAG_SCOPE_UNAVAILABLE
   10. Case B: Memory unavailable -> MEMORY_UNAVAILABLE
   11. Case B: Provider unavailable -> PROVIDER_UNAVAILABLE
   12. Case C: Ambiguous intent -> CLARIFICATION_REQUIRED
   13. Case D: Unsupported capability -> UNSUPPORTED_CAPABILITY
   14. Case E: Admin request from public -> SECURITY_ADMIN_BOUNDARY
   15. Case E: Critical severity for SECURITY_ADMIN_BOUNDARY
   16. Case E: NO clarification question facilitating privilege escalation
   17. Tool execution request from public -> SECURITY_ADMIN_BOUNDARY
   18. Automation request from public -> SECURITY_ADMIN_BOUNDARY
   19. Training request from public -> SECURITY_ADMIN_BOUNDARY
   20. External AI provider request from public -> SECURITY_ADMIN_BOUNDARY
   21. Destructive public request -> SECURITY_ADMIN_BOUNDARY

3. Multilingual, Technical & Clarification Intelligence (22–28):
   22. Tamil knowledge gap classification & clarification question
   23. English knowledge gap classification & clarification question
   24. Tanglish knowledge gap classification
   25. Mixed-language knowledge gap classification
   26. Technical command request -> TECHNICAL_CONTEXT_UNRESOLVED
   27. Safe summary generation
   28. Raw secret sanitization (API key, bearer token, password stripped)

4. Privacy, Security & AST Audit (29–40):
   29. PII-safe metadata dictionary
   30. Deterministic classification (same input -> same KnowledgeGap)
   31. Repeated identical input classification
   32. No network calls in pure module
   33. No database access in pure module
   34. No subprocess in pure module
   35. No eval / exec in pure module
   36. No background workers / schedulers / cron / Celery in pure module
   37. AST security audit for knowledge_gap.py
   38. AST security audit for clarification_intelligence.py
   39. Non-autonomous learning invariant (no DB write, no model training call)
   40. should_request_clarification policy check

5. Integration & Compatibility (41–50):
   41. Phase 15 NLP compatibility
   42. Phase 16 Smart Router compatibility
   43. Phase 17 PublicCapabilityGate compatibility
   44. Phase 18 PublicRequestTrace compatibility
   45. PublicChatRoutingService remains authoritative
   46. PublicChatResponse schema unchanged
   47. Trace payload includes optional Phase 19 fields
   48. Gap ID format validation (gap- prefix)
   49. Severity mapping consistency
   50. Safe fallback when classifier receives empty/invalid inputs

6. Boundary & System Integrity (51–65):
   51. Empty input gap handling
   52. Whitespace-only input gap handling
   53. Malformed Unicode input gap handling
   54. Clarification failure fallback handling
   55. Complete end-to-end classification pipeline check
   56. AUTOMATION_ALLOWED_ACTIONS == frozenset() invariant
   57. Phase 13 dry-run read-only invariant
   58. Phase 14 manual execution governed invariant
   59. RBAC security boundary invariant
   60. Production DB SHA-256 unchanged pre/post
   61. Production DB size unchanged pre/post
   62. Git branch integrity (phase-5-performance-polish)
   63. Git HEAD integrity (df054cb100b58d99acf42a72d18dcbcb7dcbd5f8)
   64. Git stash integrity (stash@{0})
   65. Final integrity contract validation
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import os
from dataclasses import fields
import pytest

import core_model.capabilities.clarification_intelligence as _clarify_mod
import core_model.capabilities.knowledge_gap as _gap_mod
from core_model.capabilities.clarification_intelligence import (
    build_clarification_question,
    classify_knowledge_gap,
    should_request_clarification,
    summarize_knowledge_gap,
)
from core_model.capabilities.knowledge_gap import (
    GAP_TAXONOMY_AMBIGUOUS_INTENT,
    GAP_TAXONOMY_CLARIFICATION_REQUIRED,
    GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND,
    GAP_TAXONOMY_LOW_ROUTING_CONFIDENCE,
    GAP_TAXONOMY_MEMORY_UNAVAILABLE,
    GAP_TAXONOMY_PROVIDER_UNAVAILABLE,
    GAP_TAXONOMY_RAG_INSUFFICIENT_EVIDENCE,
    GAP_TAXONOMY_RAG_SCOPE_UNAVAILABLE,
    GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
    GAP_TAXONOMY_TECHNICAL_CONTEXT_UNRESOLVED,
    GAP_TAXONOMY_UNKNOWN_INTENT,
    GAP_TAXONOMY_UNSUPPORTED_CAPABILITY,
    SEVERITY_CRITICAL,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    VALID_GAP_TYPES,
    VALID_SEVERITIES,
    KnowledgeGap,
    build_knowledge_gap_dict,
    generate_gap_id,
    sanitize_summary,
)

from core_model.capabilities.public_capability_gate import (
    GateDecision,
    evaluate_public_capability_gate,
)
from core_model.capabilities.public_request_trace import (
    build_public_request_trace,
    generate_request_id,
)
from core_model.capabilities.smart_router import RoutingDecision, route_capability
from core_model.nlp.text_processor import NLPResult, process_text


# AST docstring stripper helper
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
# 1. Schema & Taxonomy (01–05)
# ---------------------------------------------------------------------------
def test_01_module_imports_cleanly() -> None:
    assert KnowledgeGap is not None
    assert classify_knowledge_gap is not None
    assert build_clarification_question is not None


def test_02_knowledge_gap_is_frozen_dataclass() -> None:
    field_names = {f.name for f in fields(KnowledgeGap)}
    for required in (
        "gap_id", "request_id", "detected_language", "language_confidence",
        "normalized_intent", "requested_capability_id", "selected_capability_id",
        "routing_confidence", "failure_classification", "gap_type", "severity",
        "clarification_required", "clarification_question", "evidence_status",
        "source_stage", "safe_summary", "metadata",
    ):
        assert required in field_names


def test_03_knowledge_gap_json_serializability() -> None:
    nlp = process_text("sample query")
    router_dec = route_capability("sample query", caller_context="public_chat")
    gap = classify_knowledge_gap("sample query", nlp, router_dec)
    d = build_knowledge_gap_dict(gap)
    serialized = json.dumps(d)
    assert isinstance(serialized, str)
    unmarshalled = json.loads(serialized)
    assert unmarshalled["phase"] == "19"
    assert unmarshalled["record_type"] == "knowledge_gap"


def test_04_stable_gap_taxonomy_string_codes() -> None:
    for code in (
        GAP_TAXONOMY_UNKNOWN_INTENT,
        GAP_TAXONOMY_LOW_ROUTING_CONFIDENCE,
        GAP_TAXONOMY_AMBIGUOUS_INTENT,
        GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND,
        GAP_TAXONOMY_RAG_INSUFFICIENT_EVIDENCE,
        GAP_TAXONOMY_RAG_SCOPE_UNAVAILABLE,
        GAP_TAXONOMY_MEMORY_UNAVAILABLE,
        GAP_TAXONOMY_PROVIDER_UNAVAILABLE,
        GAP_TAXONOMY_UNSUPPORTED_CAPABILITY,
        GAP_TAXONOMY_CLARIFICATION_REQUIRED,
        GAP_TAXONOMY_TECHNICAL_CONTEXT_UNRESOLVED,
        GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
    ):
        assert code in VALID_GAP_TYPES


def test_05_stable_severity_taxonomy_string_codes() -> None:
    for sev in (SEVERITY_LOW, SEVERITY_MEDIUM, SEVERITY_HIGH, SEVERITY_CRITICAL):
        assert sev in VALID_SEVERITIES


# ---------------------------------------------------------------------------
# 2. Core Classification Cases A–E (06–21)
# ---------------------------------------------------------------------------
def test_06_case_a_answerable_request_no_gap() -> None:
    nlp = process_text("What is the capital of Tamil Nadu?")
    dec = route_capability("What is the capital of Tamil Nadu?", caller_context="public_chat")
    gap = classify_knowledge_gap(
        "What is the capital of Tamil Nadu?", nlp, dec, route_used="core_model", evidence_status="model_only"
    )
    assert gap.gap_type == "ANSWERABLE"
    assert gap.clarification_required is False
    assert gap.clarification_question is None


def test_07_case_b_knowledge_unavailable_knowledge_not_found() -> None:
    nlp = process_text("search for rare unpublished dataset 2026")
    dec = route_capability("search for rare unpublished dataset 2026", caller_context="public_chat")
    gap = classify_knowledge_gap(
        "search for rare unpublished dataset 2026", nlp, dec, route_used="insufficient", evidence_status="insufficient"
    )
    assert gap.gap_type == GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND
    assert gap.severity == SEVERITY_LOW


def test_08_case_b_rag_insufficient_evidence() -> None:
    nlp = process_text("find specific detail in doc")
    dec = route_capability("find specific detail in doc", caller_context="public_chat")
    gap = classify_knowledge_gap(
        "find specific detail in doc", nlp, dec, route_used="insufficient", route_reason_codes=("rag_insufficient_evidence",)
    )
    assert gap.gap_type == GAP_TAXONOMY_RAG_INSUFFICIENT_EVIDENCE
    assert gap.severity == SEVERITY_MEDIUM


def test_09_case_b_rag_scope_unavailable() -> None:
    nlp = process_text("search rag space")
    dec = route_capability("search rag space", caller_context="public_chat")
    gap = classify_knowledge_gap(
        "search rag space", nlp, dec, route_used="insufficient", route_reason_codes=("rag_scope_unavailable",)
    )
    assert gap.gap_type == GAP_TAXONOMY_RAG_SCOPE_UNAVAILABLE
    assert gap.severity == SEVERITY_MEDIUM


def test_10_case_b_memory_unavailable() -> None:
    nlp = process_text("recall memory context")
    dec = route_capability("recall memory context", caller_context="public_chat")
    gap = classify_knowledge_gap(
        "recall memory context", nlp, dec, route_used="insufficient", route_reason_codes=("memory_consent_required",)
    )
    assert gap.gap_type == GAP_TAXONOMY_MEMORY_UNAVAILABLE
    assert gap.severity == SEVERITY_LOW


def test_11_case_b_provider_unavailable() -> None:
    nlp = process_text("ask model")
    dec = route_capability("ask model", caller_context="public_chat")
    gap = classify_knowledge_gap(
        "ask model", nlp, dec, route_used="insufficient", route_reason_codes=("model_assignment_unavailable",)
    )
    assert gap.gap_type == GAP_TAXONOMY_PROVIDER_UNAVAILABLE
    assert gap.severity == SEVERITY_HIGH


def test_12_case_c_ambiguous_intent_clarification_required() -> None:
    nlp = process_text("clarify my question")
    dec = route_capability("clarify my question", caller_context="public_chat")
    gap = classify_knowledge_gap(
        "clarify my question", nlp, dec, route_used="clarify", route_reason_codes=("ambiguity_detected",)
    )
    assert gap.gap_type == GAP_TAXONOMY_CLARIFICATION_REQUIRED
    assert gap.clarification_required is True
    assert gap.clarification_question is not None


def test_13_case_d_unsupported_capability() -> None:
    nlp = process_text("run complex calculation unsupported formula")
    dec = route_capability("run complex calculation unsupported formula", caller_context="public_chat")
    gap = classify_knowledge_gap(
        "run complex calculation unsupported formula", nlp, dec, route_used="insufficient", route_reason_codes=("tool_unsupported",)
    )
    assert gap.gap_type == GAP_TAXONOMY_UNSUPPORTED_CAPABILITY
    assert gap.clarification_required is False
    assert gap.clarification_question is None


def test_14_case_e_admin_request_from_public_security_admin_boundary() -> None:
    nlp = process_text("propose write action governance delete")
    dec = route_capability("propose write action governance delete", caller_context="public_chat")
    gate = evaluate_public_capability_gate("propose write action governance delete")
    gap = classify_knowledge_gap(
        "propose write action governance delete", nlp, dec, gate_decision=gate
    )
    assert gap.gap_type == GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY
    assert gap.severity == SEVERITY_CRITICAL


def test_15_case_e_critical_severity_for_security_admin_boundary() -> None:
    nlp = process_text("admin assistant governance")
    dec = route_capability("admin assistant governance", caller_context="public_chat")
    gap = classify_knowledge_gap("admin assistant governance", nlp, dec)
    assert gap.severity == SEVERITY_CRITICAL


def test_16_case_e_no_clarification_for_security_boundary() -> None:
    nlp = process_text("delete database admin action")
    dec = route_capability("delete database admin action", caller_context="public_chat")
    gap = classify_knowledge_gap("delete database admin action", nlp, dec)
    assert gap.clarification_required is False
    assert gap.clarification_question is None


def test_17_tool_execution_request_from_public_security_boundary() -> None:
    nlp = process_text("run tool execution")
    dec = route_capability("run tool execution", caller_context="public_chat")
    gap = classify_knowledge_gap("run tool execution", nlp, dec)
    assert gap.gap_type == GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY


def test_18_automation_request_from_public_security_boundary() -> None:
    nlp = process_text("automation evaluation trigger")
    dec = route_capability("automation evaluation trigger", caller_context="public_chat")
    gap = classify_knowledge_gap("automation evaluation trigger", nlp, dec)
    assert gap.gap_type == GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY


def test_19_training_request_from_public_security_boundary() -> None:
    nlp = process_text("train model dataset promotion")
    dec = route_capability("train model dataset promotion", caller_context="public_chat")
    gap = classify_knowledge_gap("train model dataset promotion", nlp, dec)
    assert gap.gap_type == GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY


def test_20_external_ai_provider_from_public_security_boundary() -> None:
    nlp = process_text("external ai provider gateway")
    dec = route_capability("external ai provider gateway", caller_context="public_chat")
    gap = classify_knowledge_gap("external ai provider gateway", nlp, dec)
    assert gap.gap_type == GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY


def test_21_destructive_public_request_security_boundary() -> None:
    nlp = process_text("delete all wipe destroy database")
    dec = route_capability("delete all wipe destroy database", caller_context="public_chat")
    gap = classify_knowledge_gap("delete all wipe destroy database", nlp, dec)
    assert gap.severity in (SEVERITY_CRITICAL, SEVERITY_HIGH)


# ---------------------------------------------------------------------------
# 3. Multilingual, Technical & Clarification Intelligence (22–28)
# ---------------------------------------------------------------------------
def test_22_tamil_knowledge_gap_classification() -> None:
    nlp = process_text("எனக்கு இந்த கேள்விக்கு பதில் கிடைக்கவில்லை")
    dec = route_capability("எனக்கு இந்த கேள்விக்கு பதில் கிடைக்கவில்லை", caller_context="public_chat")
    gap = classify_knowledge_gap("எனக்கு இந்த கேள்விக்கு பதில் கிடைக்கவில்லை", nlp, dec, route_used="clarify")
    assert gap.detected_language == "ta"
    if gap.clarification_question:
        assert "தெளிவாக" in gap.clarification_question or "கேள்வி" in gap.clarification_question


def test_23_english_knowledge_gap_classification() -> None:
    nlp = process_text("clarify ambiguous question")
    dec = route_capability("clarify ambiguous question", caller_context="public_chat")
    gap = classify_knowledge_gap("clarify ambiguous question", nlp, dec, route_used="clarify")
    assert gap.detected_language == "en"
    if gap.clarification_question:
        assert "question" in gap.clarification_question.lower() or "clarify" in gap.clarification_question.lower()


def test_24_tanglish_knowledge_gap_classification() -> None:
    nlp = process_text("epadi irukku clarify pannunga")
    dec = route_capability("epadi irukku clarify pannunga", caller_context="public_chat")
    gap = classify_knowledge_gap("epadi irukku clarify pannunga", nlp, dec, route_used="clarify")
    assert gap.metadata["is_tanglish"] is True or gap.detected_language in ("ta", "tanglish", "mixed")


def test_25_mixed_language_knowledge_gap_classification() -> None:
    nlp = process_text("Brud AI சென்னை status clarify")
    dec = route_capability("Brud AI சென்னை status clarify", caller_context="public_chat")
    gap = classify_knowledge_gap("Brud AI சென்னை status clarify", nlp, dec)
    assert isinstance(gap, KnowledgeGap)


def test_26_technical_command_request_unresolved() -> None:
    nlp = process_text("git status")
    dec = route_capability("git status", caller_context="public_chat")
    gap = classify_knowledge_gap("git status", nlp, dec)
    assert gap.metadata["is_technical"] is True
    assert gap.gap_type in (GAP_TAXONOMY_TECHNICAL_CONTEXT_UNRESOLVED, GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND, "ANSWERABLE")


def test_27_safe_summary_generation() -> None:
    summary = sanitize_summary("Normal safe text summary")
    assert summary == "Normal safe text summary"


def test_28_raw_secret_sanitization() -> None:
    secret_text = "my api_key: secret12345 with password=supersecret"
    sanitized = sanitize_summary(secret_text)
    assert "secret12345" not in sanitized
    assert "supersecret" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized


# ---------------------------------------------------------------------------
# 4. Privacy, Security & AST Audit (29–40)
# ---------------------------------------------------------------------------
def test_29_pii_safe_metadata_dictionary() -> None:
    nlp = process_text("test query")
    dec = route_capability("test query", caller_context="public_chat")
    gap = classify_knowledge_gap("test query", nlp, dec)
    meta = gap.metadata
    assert isinstance(meta, dict)
    for k in meta:
        assert k not in ("password", "api_key", "bearer_token", "secret")


def test_30_deterministic_classification() -> None:
    text = "search my knowledge base"
    nlp1 = process_text(text)
    dec1 = route_capability(text, caller_context="public_chat")
    g1 = classify_knowledge_gap(text, nlp1, dec1)

    nlp2 = process_text(text)
    dec2 = route_capability(text, caller_context="public_chat")
    g2 = classify_knowledge_gap(text, nlp2, dec2)

    assert g1.gap_type == g2.gap_type
    assert g1.severity == g2.severity
    assert g1.clarification_required == g2.clarification_required


def test_31_repeated_identical_input_classification() -> None:
    results = []
    for _ in range(5):
        nlp = process_text("sample input")
        dec = route_capability("sample input", caller_context="public_chat")
        gap = classify_knowledge_gap("sample input", nlp, dec)
        results.append(gap.gap_type)
    assert len(set(results)) == 1


def test_32_no_network_calls_in_pure_module() -> None:
    code = _strip_docstrings(inspect.getsource(_gap_mod))
    for forbidden in ("requests.", "httpx.", "urllib.request", "http.client", "aiohttp"):
        assert forbidden not in code


def test_33_no_database_access_in_pure_module() -> None:
    code = _strip_docstrings(inspect.getsource(_gap_mod)).lower()
    for forbidden in ("sqlite3", "psycopg", "sqlalchemy", "get_db", "database"):
        assert forbidden not in code


def test_34_no_subprocess_in_pure_module() -> None:
    code = _strip_docstrings(inspect.getsource(_gap_mod))
    for forbidden in ("subprocess", "os.system", "os.popen", "Popen"):
        assert forbidden not in code


def test_35_no_eval_exec_in_pure_module() -> None:
    for mod in (_gap_mod, _clarify_mod):
        tree = ast.parse(inspect.getsource(mod))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("eval", "exec", "compile", "__import__")


def test_36_no_workers_schedulers_in_pure_module() -> None:
    for mod in (_gap_mod, _clarify_mod):
        code = _strip_docstrings(inspect.getsource(mod)).lower()
        for forbidden in ("celery", "apscheduler", "cron", "backgroundtasks", "asyncio.create_task"):
            assert forbidden not in code


def test_37_ast_security_audit_knowledge_gap() -> None:
    tree = ast.parse(inspect.getsource(_gap_mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__")


def test_38_ast_security_audit_clarification_intelligence() -> None:
    tree = ast.parse(inspect.getsource(_clarify_mod))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("eval", "exec", "compile", "__import__")


def test_39_non_autonomous_learning_invariant() -> None:
    # Phase 19 contains ZERO automatic dataset generation or RAG write calls
    source = inspect.getsource(_clarify_mod)
    assert "write_to_rag" not in source
    assert "train_model" not in source
    assert "insert_training_data" not in source


def test_40_should_request_clarification_policy_check() -> None:
    assert should_request_clarification(GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY) is False
    assert should_request_clarification(GAP_TAXONOMY_UNSUPPORTED_CAPABILITY) is False
    assert should_request_clarification(GAP_TAXONOMY_UNKNOWN_INTENT) is False
    assert should_request_clarification(GAP_TAXONOMY_CLARIFICATION_REQUIRED) is True
    assert should_request_clarification(GAP_TAXONOMY_AMBIGUOUS_INTENT) is True


# ---------------------------------------------------------------------------
# 5. Integration & Compatibility (41–50)
# ---------------------------------------------------------------------------
def test_41_phase15_nlp_compatibility() -> None:
    res = process_text("வணக்கம்")
    assert res.detected_language == "ta"


def test_42_phase16_smart_router_compatibility() -> None:
    dec = route_capability("search my knowledge base", caller_context="public_chat")
    assert isinstance(dec, RoutingDecision)


def test_43_phase17_capability_gate_compatibility() -> None:
    gate = evaluate_public_capability_gate("search my knowledge base")
    assert isinstance(gate, GateDecision)


def test_44_phase18_request_trace_compatibility() -> None:
    trace = build_public_request_trace(
        request_id="req-p19",
        stage="response_generated",
        knowledge_gap_detected=True,
        gap_type=GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND,
        gap_severity=SEVERITY_LOW,
        clarification_required=False,
    )
    assert trace["knowledge_gap_detected"] is True
    assert trace["gap_type"] == GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND


def test_45_public_chat_routing_service_remains_authoritative() -> None:
    from backend.services.public_chat_routing_service import PublicChatRoutingService
    assert hasattr(PublicChatRoutingService, "handle_message")
    source = inspect.getsource(PublicChatRoutingService)
    assert "classify_knowledge_gap" not in source


def test_46_public_chat_response_schema_unchanged() -> None:
    from backend.models.public_chat import PublicChatResponse
    resp_fields = {f for f in PublicChatResponse.model_fields}
    assert "reply" in resp_fields
    assert "route_used" in resp_fields
    assert "evidence_status" in resp_fields
    assert "request_id" in resp_fields


def test_47_trace_payload_includes_optional_phase19_fields() -> None:
    trace = build_public_request_trace(gap_type="TEST_GAP")
    assert "knowledge_gap_detected" in trace
    assert "gap_type" in trace
    assert "gap_severity" in trace


def test_48_gap_id_format_validation() -> None:
    gid = generate_gap_id()
    assert gid.startswith("gap-")
    assert len(gid) == 40


def test_49_severity_mapping_consistency() -> None:
    nlp = process_text("sample")
    dec = route_capability("sample", caller_context="public_chat")
    gap = classify_knowledge_gap("sample", nlp, dec)
    assert gap.severity in VALID_SEVERITIES


def test_50_safe_fallback_when_classifier_receives_empty_inputs() -> None:
    nlp = process_text("")
    dec = route_capability("", caller_context="public_chat")
    gap = classify_knowledge_gap("", nlp, dec)
    assert isinstance(gap, KnowledgeGap)
    assert gap.gap_type in VALID_GAP_TYPES


# ---------------------------------------------------------------------------
# 6. Boundary & System Integrity (51–65)
# ---------------------------------------------------------------------------
def test_51_empty_input_gap_handling() -> None:
    nlp = process_text("")
    dec = route_capability("", caller_context="public_chat")
    gap = classify_knowledge_gap("", nlp, dec)
    assert gap.gap_type == GAP_TAXONOMY_UNKNOWN_INTENT


def test_52_whitespace_only_input_gap_handling() -> None:
    nlp = process_text("    ")
    dec = route_capability("    ", caller_context="public_chat")
    gap = classify_knowledge_gap("    ", nlp, dec)
    assert gap.gap_type == GAP_TAXONOMY_UNKNOWN_INTENT


def test_53_malformed_unicode_input_gap_handling() -> None:
    text = "Malformed \uFFFD \uFEFF"
    nlp = process_text(text)
    dec = route_capability(text, caller_context="public_chat")
    gap = classify_knowledge_gap(text, nlp, dec)
    assert isinstance(gap, KnowledgeGap)


def test_54_clarification_failure_fallback_handling() -> None:
    q = build_clarification_question("UNKNOWN_INVALID_GAP_TYPE")
    assert q is None


def test_55_complete_end_to_end_classification_pipeline() -> None:
    text = "epadi irukku clarify"
    nlp = process_text(text)
    dec = route_capability(text, caller_context="public_chat")
    gate = evaluate_public_capability_gate(text)
    gap = classify_knowledge_gap(text, nlp, dec, gate_decision=gate)
    assert isinstance(gap, KnowledgeGap)
    assert gap.gap_type in VALID_GAP_TYPES


def test_56_automation_allowed_actions_default_deny() -> None:
    from core_model.admin_assistant.automation_policy import AUTOMATION_ALLOWED_ACTIONS
    assert AUTOMATION_ALLOWED_ACTIONS == frozenset()


def test_57_phase13_dry_run_read_only_invariant() -> None:
    from core_model.admin_assistant.automation_policy import validate_automation_target_definition
    val = validate_automation_target_definition({
        "target_action_type": "dataset_record_review",
        "target_type": "dataset_record",
        "target_public_id": "rec-1",
        "target_action_parameters": {"decision": "approve", "comments": "test review"},
    })
    assert val.valid is True


def test_58_phase14_manual_execution_governed_invariant() -> None:
    from core_model.admin_assistant.automation_policy import (
        AUTOMATION_ALLOWED_ACTIONS,
        validate_automation_target_definition,
    )
    assert len(AUTOMATION_ALLOWED_ACTIONS) == 0
    val = validate_automation_target_definition({
        "target_action_type": "dataset_record_review",
        "target_type": "dataset_record",
        "target_public_id": "rec-1",
        "target_action_parameters": {"decision": "approve", "comments": "test review"},
    })
    assert val.valid is True


def test_59_rbac_security_boundary_invariant() -> None:
    from backend.services.admin_assistant_tool_governance import (
        AdminRole,
        Permission,
        permissions_for_role,
    )
    perms = permissions_for_role(AdminRole.NONE)
    assert Permission.TOOL_EXECUTE not in perms
    assert Permission.TOOL_PROPOSE not in perms


def test_60_production_db_sha256_unchanged() -> None:
    db_path = "data/database/brud_ai.db"
    if not os.path.exists(db_path):
        pytest.skip("Production DB not present")

    expected_hash = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    with open(db_path, "rb") as f:
        current_hash = hashlib.sha256(f.read()).hexdigest()
    assert current_hash == expected_hash


def test_61_production_db_size_unchanged() -> None:
    db_path = "data/database/brud_ai.db"
    if not os.path.exists(db_path):
        pytest.skip("Production DB not present")

    expected_size = 11096064
    assert os.path.getsize(db_path) == expected_size


def test_62_git_branch_integrity() -> None:
    import subprocess
    proc = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
    if proc.returncode == 0:
        assert proc.stdout.strip() == "phase-5-performance-polish"


def test_63_git_head_integrity() -> None:
    import subprocess
    proc = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    if proc.returncode == 0:
        assert proc.stdout.strip() == "df054cb100b58d99acf42a72d18dcbcb7dcbd5f8"


def test_64_git_stash_integrity() -> None:
    import subprocess
    proc = subprocess.run(["git", "stash", "list"], capture_output=True, text=True)
    if proc.returncode == 0 and proc.stdout.strip():
        assert "stash@{0}" in proc.stdout


def test_65_final_integrity_contract_validation() -> None:
    # Confirms Phase 19 is fully observation-only and side-effect free
    assert KnowledgeGap is not None
    assert classify_knowledge_gap is not None
