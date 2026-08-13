"""MB-21: pure-module unit tests for core_model/mini_brain/external_ai_gateway/.

Covers authorization enforcement, sanitization redaction, provider
selection, agreement/contradiction detection, safety-violation
detection, and honest-empty-input paths the task spec's own testing
section names.
"""

from core_model.mini_brain.external_ai_gateway.agreement_analyzer import analyze_agreement
from core_model.mini_brain.external_ai_gateway.data_request_prompt_builder import build_data_request_prompt
from core_model.mini_brain.external_ai_gateway.evaluation_scoring import score_evaluation
from core_model.mini_brain.external_ai_gateway.evidence_bundle_builder import build_evidence_bundle
from core_model.mini_brain.external_ai_gateway.failure_detector import detect_failures
from core_model.mini_brain.external_ai_gateway.gateway_report_generator import generate_gateway_report
from core_model.mini_brain.external_ai_gateway.prompt_sanitizer import sanitize_prompt
from core_model.mini_brain.external_ai_gateway.provider_registry import select_providers
from core_model.mini_brain.external_ai_gateway.provider_response_normalizer import normalize_response
from core_model.mini_brain.external_ai_gateway.public_test_prompt_builder import (
    QUESTION_CATEGORIES,
    build_public_test_prompts,
)
from core_model.mini_brain.external_ai_gateway.recommendation_builder import (
    build_data_acquisition_handoff,
    build_public_evaluation_recommendations,
)
from core_model.mini_brain.external_ai_gateway.reproducibility_hasher import build_reproducibility_record
from core_model.mini_brain.external_ai_gateway.request_policy import validate_authorization
from core_model.mini_brain.external_ai_gateway.safety_violation_detector import detect_safety_violations

# -- request_policy -------------------------------------------------------------------------


def test_validate_authorization_requires_admin_and_note() -> None:
    result = validate_authorization(admin_public_id=None, authorization_note="", purpose="public_style_stress_test")
    assert result["authorized"] is False
    assert len(result["reasons"]) >= 1


def test_validate_authorization_succeeds_with_real_inputs() -> None:
    result = validate_authorization(admin_public_id="admin1", authorization_note="testing", purpose="public_style_stress_test")
    assert result["authorized"] is True
    assert result["reasons"] == []


def test_validate_authorization_rejects_unknown_purpose() -> None:
    result = validate_authorization(admin_public_id="admin1", authorization_note="testing", purpose="bogus")
    assert result["authorized"] is False


# -- prompt_sanitizer -------------------------------------------------------------------------


def test_sanitize_prompt_redacts_secret() -> None:
    result = sanitize_prompt(raw_prompt="my api_key=sk-12345 is here")
    assert "sk-12345" not in result["sanitized_prompt"]
    assert "secret_like_content" in result["privacy_audit"]["redaction_categories_applied"]


def test_sanitize_prompt_redacts_filesystem_path() -> None:
    result = sanitize_prompt(raw_prompt="the file is at /home/dhurai/secret.txt")
    assert "/home/dhurai" not in result["sanitized_prompt"]
    assert "local_username" in result["privacy_audit"]["redaction_categories_applied"]
    assert "filesystem_path" in result["privacy_audit"]["redaction_categories_applied"]


def test_sanitize_prompt_redacts_database_uuid() -> None:
    result = sanitize_prompt(raw_prompt="record 123e4567-e89b-12d3-a456-426614174000 was flagged")
    assert "123e4567" not in result["sanitized_prompt"]


def test_sanitize_prompt_truncates_oversized_payload() -> None:
    result = sanitize_prompt(raw_prompt="x" * 20_000)
    assert result["truncated"] is True
    assert len(result["sanitized_prompt"]) <= 8_000


def test_sanitize_prompt_excludes_private_context_by_default() -> None:
    result = sanitize_prompt(raw_prompt="hello", private_context="private stuff")
    assert "private stuff" not in result["sanitized_prompt"]
    assert "private_context_excluded_not_approved" in result["privacy_audit"]["redaction_categories_applied"]


def test_sanitize_prompt_includes_private_context_when_explicitly_allowed() -> None:
    result = sanitize_prompt(raw_prompt="hello", allow_private_context=True, private_context="approved stuff")
    assert "approved stuff" in result["sanitized_prompt"]
    assert result["privacy_audit"]["private_context_included"] is True


def test_sanitize_prompt_computes_stable_hashes() -> None:
    a = sanitize_prompt(raw_prompt="hello world")
    b = sanitize_prompt(raw_prompt="hello world")
    assert a["original_hash_sha256"] == b["original_hash_sha256"]
    assert a["sanitized_hash_sha256"] == b["sanitized_hash_sha256"]


# -- provider_registry -------------------------------------------------------------------------


def test_select_providers_only_enabled() -> None:
    result = select_providers(
        requested_provider_keys=["p1", "p2", "p3"],
        provider_availability=[
            {"provider_key": "p1", "status": "enabled"}, {"provider_key": "p2", "status": "disabled"},
        ],
    )
    assert [p["provider_key"] for p in result["selected_providers"]] == ["p1"]
    assert result["unknown_provider_keys"] == ["p3"]
    assert result["ready"] is True


def test_select_providers_not_ready_when_none_enabled() -> None:
    result = select_providers(requested_provider_keys=["p1"], provider_availability=[{"provider_key": "p1", "status": "unavailable"}])
    assert result["ready"] is False


# -- public_test_prompt_builder / data_request_prompt_builder ------------------------------------


def test_build_public_test_prompts_covers_all_categories() -> None:
    result = build_public_test_prompts(topic="rivers")
    assert result["prompt_count"] == len(QUESTION_CATEGORIES)
    assert {p["category"] for p in result["prompts"]} == set(QUESTION_CATEGORIES)
    assert all("rivers" in p["prompt"] for p in result["prompts"])


def test_build_data_request_prompt_discloses_unverified() -> None:
    result = build_data_request_prompt(admin_stated_need="missing facts about erosion")
    assert "unverified" in result["prompt"]
    assert result["admin_stated_need"] == "missing facts about erosion"


# -- provider_response_normalizer --------------------------------------------------------------


def test_normalize_response_success() -> None:
    raw = {"status": "success", "text": "The river flows downhill.", "latency_ms": 10.0, "error_message": None}
    result = normalize_response(provider_key="p1", raw_result=raw, purpose="public_style_stress_test")
    assert result["status"] == "success"
    assert result["word_count"] == 4


def test_normalize_response_failure_has_no_text() -> None:
    raw = {"status": "timeout", "text": None, "latency_ms": 0.0, "error_message": "timed out"}
    result = normalize_response(provider_key="p1", raw_result=raw, purpose="public_style_stress_test")
    assert result["normalized_text"] is None
    assert result["word_count"] == 0


def test_normalize_response_data_acquisition_computes_section_coverage() -> None:
    raw = {"status": "success", "text": "Fact: rivers flow. Example: the Nile. No reference known.", "latency_ms": 10.0, "error_message": None}
    result = normalize_response(provider_key="p1", raw_result=raw, purpose="data_acquisition_assistance")
    assert result["section_coverage"]["candidate_facts"] is True
    assert result["section_coverage"]["candidate_examples"] is True
    assert result["section_coverage"]["candidate_qa_pairs"] is False


# -- agreement_analyzer -------------------------------------------------------------------------


def test_analyze_agreement_high_overlap() -> None:
    responses = [
        {"provider_key": "p1", "status": "success", "normalized_text": "the river flows through the mountain valley"},
        {"provider_key": "p2", "status": "success", "normalized_text": "the river flows through the mountain valley"},
    ]
    result = analyze_agreement(normalized_responses=responses)
    assert result["agreement_score"] == 100.0
    assert result["contradiction_count"] == 0


def test_analyze_agreement_detects_contradiction() -> None:
    responses = [
        {"provider_key": "p1", "status": "success", "normalized_text": "apples grow on trees in orchards"},
        {"provider_key": "p2", "status": "success", "normalized_text": "quantum physics involves subatomic particles"},
    ]
    result = analyze_agreement(normalized_responses=responses)
    assert result["contradiction_count"] == 1
    assert result["unsupported_claim_count"] == 2


def test_analyze_agreement_counts_failures() -> None:
    responses = [
        {"provider_key": "p1", "status": "success", "normalized_text": "hello world"},
        {"provider_key": "p2", "status": "timeout", "normalized_text": None},
    ]
    result = analyze_agreement(normalized_responses=responses)
    assert result["provider_count"] == 2
    assert result["successful_provider_count"] == 1
    assert result["failed_provider_count"] == 1
    assert result["agreement_score"] == 100.0  # single successful response


def test_analyze_agreement_detects_hallucination_hedge() -> None:
    responses = [{"provider_key": "p1", "status": "success", "normalized_text": "I'm not sure about this topic."}]
    result = analyze_agreement(normalized_responses=responses)
    assert result["hallucination_warning_count"] == 1


def test_analyze_agreement_no_majority_voting_field_present() -> None:
    """No field in the output should claim a truth decision -- only
    measurement fields exist."""
    result = analyze_agreement(normalized_responses=[])
    assert "truth" not in "".join(result.keys()).lower()


# -- failure_detector -------------------------------------------------------------------------


def test_detect_failures_aggregates_by_status() -> None:
    runs = [
        {"provider_key": "p1", "status": "success"}, {"provider_key": "p2", "status": "timeout", "error_message": "x"},
        {"provider_key": "p3", "status": "rate_limited", "error_message": "y"},
    ]
    result = detect_failures(provider_runs=runs)
    assert result["failure_count"] == 2
    assert result["failures_by_status"] == {"timeout": 1, "rate_limited": 1}
    assert result["all_providers_failed"] is False


def test_detect_failures_all_failed() -> None:
    runs = [{"provider_key": "p1", "status": "unavailable", "error_message": "x"}]
    result = detect_failures(provider_runs=runs)
    assert result["all_providers_failed"] is True


# -- safety_violation_detector ------------------------------------------------------------------


def test_detect_safety_violations_flags_shell_command() -> None:
    responses = [{"provider_key": "p1", "normalized_text": "run rm -rf / to clean up"}]
    result = detect_safety_violations(normalized_responses=responses)
    assert result["has_violations"] is True
    assert "shell_command_like_content" in result["flagged_responses"][0]["categories"]


def test_detect_safety_violations_flags_executable_link() -> None:
    responses = [{"provider_key": "p1", "normalized_text": "download it from https://example.com/tool.exe"}]
    result = detect_safety_violations(normalized_responses=responses)
    assert "executable_download_link" in result["flagged_responses"][0]["categories"]


def test_detect_safety_violations_clean_response() -> None:
    responses = [{"provider_key": "p1", "normalized_text": "the river flows through the valley"}]
    result = detect_safety_violations(normalized_responses=responses)
    assert result["has_violations"] is False


# -- evaluation_scoring -------------------------------------------------------------------------


def test_score_evaluation_no_signal_when_all_failed() -> None:
    agreement = {"successful_provider_count": 0, "agreement_score": 0.0}
    failures = {"all_providers_failed": True}
    safety = {"has_violations": False}
    result = score_evaluation(agreement_report=agreement, failure_report=failures, safety_report=safety)
    assert result["confidence_level"] == "no_signal"


def test_score_evaluation_low_when_safety_flagged() -> None:
    agreement = {"successful_provider_count": 2, "agreement_score": 90.0}
    failures = {"all_providers_failed": False}
    safety = {"has_violations": True}
    result = score_evaluation(agreement_report=agreement, failure_report=failures, safety_report=safety)
    assert result["confidence_level"] == "low"


def test_score_evaluation_high_confidence() -> None:
    agreement = {"successful_provider_count": 2, "agreement_score": 90.0}
    failures = {"all_providers_failed": False}
    safety = {"has_violations": False}
    result = score_evaluation(agreement_report=agreement, failure_report=failures, safety_report=safety)
    assert result["confidence_level"] == "high"


# -- recommendation_builder ----------------------------------------------------------------------


def test_build_public_evaluation_recommendations_flags_hedge_as_missing_knowledge() -> None:
    responses = [{"provider_key": "p1", "status": "success", "normalized_text": "I don't have information on that."}]
    agreement = {"failed_provider_count": 0, "unsupported_claim_count": 0, "hallucination_warning_count": 1}
    result = build_public_evaluation_recommendations(normalized_responses=responses, agreement_report=agreement)
    assert "p1" in result["missing_knowledge_topics"]
    assert len(result["suggested_rag_improvements"]) > 0


def test_build_data_acquisition_handoff_never_inserts_directly() -> None:
    responses = [{"provider_key": "p1", "status": "success", "normalized_text": "x", "section_coverage": {"candidate_facts": True}}]
    result = build_data_acquisition_handoff(normalized_responses=responses)
    assert any("never" in action or "manually" in action for action in result["next_actions"])
    assert result["covered_sections"] == {"candidate_facts": 1}


# -- evidence_bundle_builder ---------------------------------------------------------------------


def test_build_evidence_bundle_hides_raw_text_unless_retained() -> None:
    sanitized = {"sanitized_prompt": "x", "sanitized_hash_sha256": "h1", "original_hash_sha256": "h2", "privacy_audit": {}}
    runs = [{"provider_key": "p1", "status": "success", "response_hash": "abc", "raw_response_retained": False, "normalized_response": {"normalized_text": "secret raw text"}, "latency_ms": 1.0}]
    bundle = build_evidence_bundle(
        sanitized_prompt_record=sanitized, provider_runs=runs, normalized_responses=[], agreement_report={},
        failure_report={}, safety_report={}, suggested_follow_up_actions=[],
    )
    assert bundle["provider_metadata"][0]["raw_response_text"] is None


def test_build_evidence_bundle_includes_raw_text_when_retained() -> None:
    sanitized = {"sanitized_prompt": "x", "sanitized_hash_sha256": "h1", "original_hash_sha256": "h2", "privacy_audit": {}}
    runs = [{"provider_key": "p1", "status": "success", "response_hash": "abc", "raw_response_retained": True, "normalized_response": {"normalized_text": "retained text"}, "latency_ms": 1.0}]
    bundle = build_evidence_bundle(
        sanitized_prompt_record=sanitized, provider_runs=runs, normalized_responses=[], agreement_report={},
        failure_report={}, safety_report={}, suggested_follow_up_actions=[],
    )
    assert bundle["provider_metadata"][0]["raw_response_text"] == "retained text"


# -- gateway_report_generator --------------------------------------------------------------------


def test_generate_gateway_report_discloses_all_honest_limitations() -> None:
    report = generate_gateway_report(
        session_public_id="s1", topic="t", purpose="public_style_stress_test",
        provider_runs=[{"provider_key": "p1", "status": "success", "latency_ms": 1.0}],
        agreement_report={"contradiction_count": 0, "agreement_score": 90.0},
        failure_report={"all_providers_failed": False}, safety_report={"has_violations": False, "flagged_count": 0},
        scoring_report={"confidence_level": "high"}, recommendations={"missing_knowledge_topics": [], "suggested_dataset_improvements": [], "suggested_rag_improvements": []},
        privacy_audit={"redaction_categories_applied": []},
    )
    assert report["external_ai_output_unverified"] is True
    assert report["no_automatic_truth_determination"] is True
    assert report["no_automatic_dataset_insertion"] is True
    assert report["no_automatic_training"] is True
    assert report["no_automatic_release_approval"] is True
    assert report["provider_availability_may_change"] is True
    assert report["provider_answers_may_be_wrong"] is True
    assert report["agreement_does_not_imply_correctness"] is True


def test_generate_gateway_report_flags_all_failed_as_key_finding() -> None:
    report = generate_gateway_report(
        session_public_id="s1", topic="t", purpose="public_style_stress_test", provider_runs=[],
        agreement_report={"contradiction_count": 0, "agreement_score": 0.0},
        failure_report={"all_providers_failed": True}, safety_report={"has_violations": False, "flagged_count": 0},
        scoring_report={"confidence_level": "no_signal"}, recommendations={"missing_knowledge_topics": [], "suggested_dataset_improvements": [], "suggested_rag_improvements": []},
        privacy_audit={},
    )
    assert any("failed" in finding for finding in report["key_findings"])


# -- reproducibility_hasher -----------------------------------------------------------------------


def test_reproducibility_record_stable_for_same_inputs() -> None:
    report = {"a": 1}
    first = build_reproducibility_record(gateway_report=report, sanitized_prompt_hash="h1", source_dataset_public_ids=["d2", "d1"], source_rag_session_public_id="r1")
    second = build_reproducibility_record(gateway_report=report, sanitized_prompt_hash="h1", source_dataset_public_ids=["d1", "d2"], source_rag_session_public_id="r1")
    assert first == second


def test_reproducibility_record_differs_for_different_prompt_hash() -> None:
    report = {"a": 1}
    first = build_reproducibility_record(gateway_report=report, sanitized_prompt_hash="h1", source_dataset_public_ids=[], source_rag_session_public_id=None)
    second = build_reproducibility_record(gateway_report=report, sanitized_prompt_hash="h2", source_dataset_public_ids=[], source_rag_session_public_id=None)
    assert first["input_set_checksum_sha256"] != second["input_set_checksum_sha256"]
