"""MB-20: pure-module unit tests for core_model/mini_brain/release_governance/.

Covers safety pass/fail paths, compliance fail path, benchmark fail
path, deterministic risk-register/rollback generation, and honest-
empty-input paths the task spec's own testing section names.
"""

from core_model.mini_brain.release_governance.benchmark_gate_evaluator import run_benchmark_gates
from core_model.mini_brain.release_governance.compatibility_matrix_builder import (
    build_compatibility_matrix,
)
from core_model.mini_brain.release_governance.compliance_evaluator import run_compliance_gates
from core_model.mini_brain.release_governance.deployment_prerequisite_builder import (
    build_deployment_prerequisites,
)
from core_model.mini_brain.release_governance.operator_instruction_builder import (
    build_operator_instructions,
)
from core_model.mini_brain.release_governance.release_decision_builder import (
    APPROVED_FOR_RELEASE,
    CONDITIONALLY_APPROVED,
    NOT_APPROVED,
    build_release_decision,
)
from core_model.mini_brain.release_governance.release_manifest_builder import build_release_manifest
from core_model.mini_brain.release_governance.release_report_generator import generate_release_report
from core_model.mini_brain.release_governance.reproducibility_hasher import (
    build_reproducibility_record,
    verify_reproducibility,
)
from core_model.mini_brain.release_governance.risk_register_builder import build_risk_register
from core_model.mini_brain.release_governance.rollback_planner import build_rollback_plan
from core_model.mini_brain.release_governance.safety_gate_evaluator import run_safety_gates
from core_model.mini_brain.release_governance.source_collector import (
    collect_dataset_evidence,
    collect_evaluation_report,
    collect_rag_evidence,
    collect_training_package,
)

_ALL_PASS_KWARGS = dict(
    grounding_composite_score=90.0, hallucination_risk=0.0, ocr_conflict_ratio=0.0,
    unsupported_sentence_ratio=0.0, package_integrity_ok=True, missing_artifact_count=0,
    unicode_integrity=100.0, tamil_character_validity=100.0, duplicate_count=0,
    release_risk_level="low",
)

# -- source_collector ------------------------------------------------------------------------


def test_collect_dataset_evidence_accepts_only_admin_approved() -> None:
    sessions = [
        {"public_id": "d1", "status": "admin_approved"}, {"public_id": "d2", "status": "in_progress"},
    ]
    report = collect_dataset_evidence(dataset_sessions=sessions)
    assert report["accepted_session_public_ids"] == ["d1"]
    assert report["ready"] is True


def test_collect_rag_evidence_zero_accepted_still_ready() -> None:
    report = collect_rag_evidence(rag_sessions=[{"public_id": "r1", "admin_decision": "reject"}])
    assert report["accepted_count"] == 0
    assert report["ready"] is True


def test_collect_training_package_requires_admin_approved_with_real_package() -> None:
    accepted = collect_training_package(
        package_session={"public_id": "p1", "status": "admin_approved", "package_directory": "/x", "package_manifest": {"artifact_count": 9}},
    )
    assert accepted["accepted"] is True
    rejected = collect_training_package(
        package_session={"public_id": "p2", "status": "in_progress", "package_directory": "/x", "package_manifest": {"artifact_count": 9}},
    )
    assert rejected["accepted"] is False
    none_case = collect_training_package(package_session=None)
    assert none_case["accepted"] is False


def test_collect_evaluation_report_requires_admin_approved() -> None:
    accepted = collect_evaluation_report(evaluation_session={"public_id": "e1", "status": "admin_approved"})
    assert accepted["accepted"] is True
    rejected = collect_evaluation_report(evaluation_session={"public_id": "e2", "status": "in_progress"})
    assert rejected["accepted"] is False


# -- safety_gate_evaluator ----------------------------------------------------------------------


def test_run_safety_gates_all_pass() -> None:
    report = run_safety_gates(**_ALL_PASS_KWARGS)
    assert report["overall_status"] == "pass"
    assert report["failed_count"] == 0
    assert report["blocking_reasons"] == []


def test_run_safety_gates_grounding_failure_blocks() -> None:
    kwargs = dict(_ALL_PASS_KWARGS, grounding_composite_score=10.0)
    report = run_safety_gates(**kwargs)
    assert report["overall_status"] == "fail"
    assert any("grounding" in r for r in report["blocking_reasons"])


def test_run_safety_gates_package_integrity_failure_blocks() -> None:
    kwargs = dict(_ALL_PASS_KWARGS, package_integrity_ok=False)
    report = run_safety_gates(**kwargs)
    assert report["overall_status"] == "fail"
    assert any("package integrity" in r for r in report["blocking_reasons"])


def test_run_safety_gates_none_values_do_not_fail() -> None:
    """A None value (metric honestly unavailable upstream) must never
    be treated as a failure -- only an actually-out-of-band value
    should block."""
    kwargs = dict(_ALL_PASS_KWARGS, grounding_composite_score=None, hallucination_risk=None)
    report = run_safety_gates(**kwargs)
    assert report["overall_status"] == "pass"


def test_run_safety_gates_thresholds_documented() -> None:
    report = run_safety_gates(**_ALL_PASS_KWARGS)
    assert report["thresholds"]["grounding_quality_threshold"] == 60.0


# -- compliance_evaluator -----------------------------------------------------------------------


def test_run_compliance_gates_required_missing_fails() -> None:
    report = run_compliance_gates(
        checklist={"dataset_approval_present": False, "audit_trail_present": True},
        required_now={"dataset_approval_present", "audit_trail_present"},
    )
    assert report["overall_status"] == "fail"
    assert any("dataset_approval_present" in r for r in report["blocking_reasons"])


def test_run_compliance_gates_deferred_items_pending_not_failing() -> None:
    report = run_compliance_gates(
        checklist={"dataset_approval_present": True, "audit_trail_present": True},
        required_now={"dataset_approval_present", "audit_trail_present"},
    )
    assert report["overall_status"] == "in_progress"
    pending = [i for i in report["items"] if i["status"] == "pending"]
    assert len(pending) > 0
    assert report["blocking_reasons"] == []


def test_run_compliance_gates_complete_when_all_present() -> None:
    checklist = {name: True for name in (
        "dataset_approval_present", "audit_trail_present", "reproducibility_hash_present",
        "artifact_checksums_present", "rollback_plan_present", "operator_instructions_present",
        "deployment_prerequisites_present",
    )}
    report = run_compliance_gates(checklist=checklist, required_now=set(checklist))
    assert report["overall_status"] == "complete"


# -- benchmark_gate_evaluator --------------------------------------------------------------------


def test_run_benchmark_gates_classifies_passed_failed_marginal() -> None:
    results = [
        {"category": "language", "metric_name": "unicode_integrity", "metric_value": 95.0},
        {"category": "grounding", "metric_name": "citation_validity_rate", "metric_value": 0.2},
        {"category": "ocr", "metric_name": "ocr_conflict_ratio", "metric_value": 0.2},
        {"category": "multimodal", "metric_name": "image_coverage", "metric_value": 0.5},
    ]
    report = run_benchmark_gates(benchmark_results=results)
    assert {m["metric_name"] for m in report["passed_metrics"]} == {"unicode_integrity"}
    assert {m["metric_name"] for m in report["failed_metrics"]} == {"citation_validity_rate"}
    assert {m["metric_name"] for m in report["marginal_metrics"]} == {"ocr_conflict_ratio"}
    assert {m["metric_name"] for m in report["informational_metrics"]} == {"image_coverage"}
    assert report["overall_benchmark_status"] == "fail"


def test_run_benchmark_gates_no_data() -> None:
    report = run_benchmark_gates(benchmark_results=[])
    assert report["overall_benchmark_status"] == "no_data"


def test_run_benchmark_gates_skips_null_values() -> None:
    results = [{"category": "language", "metric_name": "unicode_integrity", "metric_value": None}]
    report = run_benchmark_gates(benchmark_results=results)
    assert report["evaluated_metric_count"] == 0


# -- risk_register_builder ----------------------------------------------------------------------


def test_build_risk_register_traces_to_real_failures_only() -> None:
    safety = run_safety_gates(**dict(_ALL_PASS_KWARGS, grounding_composite_score=10.0))
    compliance = run_compliance_gates(checklist={}, required_now=set())
    benchmark = {"failed_metrics": [], "marginal_metrics": []}
    risk = build_risk_register(safety_gate_report=safety, compliance_gate_report=compliance, benchmark_gate_report=benchmark)
    assert risk["entry_count"] == 1
    assert risk["entries"][0]["category"] == "safety"
    assert risk["entries"][0]["id"] == "RISK-001"


def test_build_risk_register_empty_when_everything_passes() -> None:
    safety = run_safety_gates(**_ALL_PASS_KWARGS)
    compliance = run_compliance_gates(checklist={"dataset_approval_present": True, "audit_trail_present": True}, required_now={"dataset_approval_present", "audit_trail_present"})
    benchmark = {"failed_metrics": [], "marginal_metrics": []}
    risk = build_risk_register(safety_gate_report=safety, compliance_gate_report=compliance, benchmark_gate_report=benchmark)
    assert risk["entry_count"] == 0


def test_build_risk_register_is_deterministic() -> None:
    safety = run_safety_gates(**dict(_ALL_PASS_KWARGS, grounding_composite_score=10.0, ocr_conflict_ratio=0.9))
    compliance = run_compliance_gates(checklist={}, required_now=set())
    benchmark = {"failed_metrics": [], "marginal_metrics": []}
    first = build_risk_register(safety_gate_report=safety, compliance_gate_report=compliance, benchmark_gate_report=benchmark)
    second = build_risk_register(safety_gate_report=safety, compliance_gate_report=compliance, benchmark_gate_report=benchmark)
    assert first == second


# -- rollback_planner -----------------------------------------------------------------------------


def test_build_rollback_plan_generation() -> None:
    risk = {"entries": [{"rollback_trigger": "safety gate 'x' fails again"}]}
    plan = build_rollback_plan(risk_register=risk)
    assert plan["trigger_conditions"] == ["safety gate 'x' fails again"]
    assert len(plan["rollback_steps"]) > 0
    assert len(plan["verification_steps"]) > 0
    assert len(plan["communication_checklist"]) > 0
    assert plan["executed"] is False


def test_build_rollback_plan_no_risks_still_has_fallback_trigger() -> None:
    plan = build_rollback_plan(risk_register={"entries": []})
    assert len(plan["trigger_conditions"]) == 1


# -- compatibility_matrix_builder / deployment_prerequisite_builder / operator_instruction_builder --


def test_build_compatibility_matrix_surfaces_upstream_fields() -> None:
    matrix = build_compatibility_matrix(
        hardware_estimate_report={"cpu_only_feasible": True, "ram_tier": "8GB+"},
        language_benchmark_report={"dominant_language": "en", "language_distribution": {"en": 5, "ta": 1}},
        multimodal_benchmark_report={"image_coverage": 0.2, "knowledge_graph_coverage": 0.0},
    )
    assert matrix["cpu_only_feasible"] is True
    assert matrix["supported_languages"] == ["en", "ta"]
    assert matrix["image_support"] is True
    assert matrix["knowledge_graph_support"] is False


def test_build_deployment_prerequisites_adds_gpu_item_when_not_cpu_feasible() -> None:
    cpu_only = build_deployment_prerequisites(compatibility_matrix={"cpu_only_feasible": True})
    gpu_needed = build_deployment_prerequisites(compatibility_matrix={"cpu_only_feasible": False})
    assert len(gpu_needed["items"]) == len(cpu_only["items"]) + 1
    assert all(item["verified"] is False for item in gpu_needed["items"])


def test_build_operator_instructions_never_executes() -> None:
    instructions = build_operator_instructions(release_topic="t", release_readiness_status="pass")
    assert instructions["executed_by_this_phase"] is False
    assert instructions["step_count"] > 0


# -- release_decision_builder -----------------------------------------------------------------------


def test_build_release_decision_approved_when_clean() -> None:
    safety = run_safety_gates(**_ALL_PASS_KWARGS)
    compliance = run_compliance_gates(checklist={"dataset_approval_present": True, "audit_trail_present": True}, required_now={"dataset_approval_present", "audit_trail_present"})
    benchmark = {"overall_benchmark_status": "pass"}
    decision = build_release_decision(safety_gate_report=safety, compliance_gate_report=compliance, benchmark_gate_report=benchmark, release_risk_level="low")
    assert decision["recommendation"] == APPROVED_FOR_RELEASE
    assert decision["binding"] is False


def test_build_release_decision_not_approved_on_safety_failure() -> None:
    safety = run_safety_gates(**dict(_ALL_PASS_KWARGS, grounding_composite_score=10.0))
    compliance = run_compliance_gates(checklist={"dataset_approval_present": True, "audit_trail_present": True}, required_now={"dataset_approval_present", "audit_trail_present"})
    benchmark = {"overall_benchmark_status": "pass"}
    decision = build_release_decision(safety_gate_report=safety, compliance_gate_report=compliance, benchmark_gate_report=benchmark, release_risk_level="low")
    assert decision["recommendation"] == NOT_APPROVED
    assert len(decision["blocking_issues"]) > 0


def test_build_release_decision_conditionally_approved_on_marginal_benchmark() -> None:
    safety = run_safety_gates(**_ALL_PASS_KWARGS)
    compliance = run_compliance_gates(checklist={"dataset_approval_present": True, "audit_trail_present": True}, required_now={"dataset_approval_present", "audit_trail_present"})
    benchmark = {"overall_benchmark_status": "marginal"}
    decision = build_release_decision(safety_gate_report=safety, compliance_gate_report=compliance, benchmark_gate_report=benchmark, release_risk_level="low")
    assert decision["recommendation"] == CONDITIONALLY_APPROVED


# -- release_manifest_builder / reproducibility_hasher -------------------------------------------------


def test_build_release_manifest_excludes_self_and_discloses() -> None:
    entries = [{"artifact_name": "risk_register.json", "relative_path": "risk_register.json", "sha256": "x", "file_size_bytes": 1}]
    manifest = build_release_manifest(
        session_public_id="s1", topic="t", source_dataset_public_ids=["d1"], source_rag_session_public_ids=[],
        source_training_package_public_id="p1", source_evaluation_session_public_id="e1",
        release_recommendation="approved_for_release", artifact_entries=entries, created_at="2026-01-01",
    )
    assert manifest["artifact_count"] == 1
    assert manifest["deployment_performed"] is False
    assert manifest["runtime_activated"] is False
    assert "not self-listed" in manifest["note"]
    assert manifest["sensitive_content_warnings"] == []


def test_reproducibility_record_is_reproducible_for_identical_inputs() -> None:
    manifest = {"a": 1}
    first = build_reproducibility_record(
        release_manifest=manifest, source_dataset_public_ids=["d2", "d1"], source_rag_session_public_ids=[],
        source_training_package_public_id="p1", source_evaluation_session_public_id="e1",
    )
    second = build_reproducibility_record(
        release_manifest=manifest, source_dataset_public_ids=["d1", "d2"], source_rag_session_public_ids=[],
        source_training_package_public_id="p1", source_evaluation_session_public_id="e1",
    )
    assert first == second


def test_verify_reproducibility_detects_tampering() -> None:
    from backend.core.json_utils import dumps_json

    manifest = {"a": 1}
    record = build_reproducibility_record(
        release_manifest=manifest, source_dataset_public_ids=[], source_rag_session_public_ids=[],
        source_training_package_public_id=None, source_evaluation_session_public_id=None,
    )
    assert verify_reproducibility(manifest_json=dumps_json(manifest), expected_checksum=record["manifest_checksum_sha256"]) is True
    assert verify_reproducibility(manifest_json=dumps_json({"a": 2}), expected_checksum=record["manifest_checksum_sha256"]) is False


# -- release_report_generator -------------------------------------------------------------------------


def _report_kwargs(**overrides):
    base = dict(
        session_public_id="s1", topic="t",
        dataset_collection_report={"accepted_count": 1}, rag_collection_report={"accepted_count": 1},
        training_package_collection_report={"accepted": True}, evaluation_collection_report={"accepted": True},
        safety_gate_report={"overall_status": "pass"}, compliance_gate_report={"overall_status": "complete"},
        benchmark_gate_report={"overall_benchmark_status": "pass"},
        risk_register={"entry_count": 0, "severity_counts": {}}, rollback_plan={"trigger_conditions": [], "rollback_steps": [], "executed": False},
        compatibility_matrix={}, deployment_prerequisites={}, operator_instructions={},
        release_decision={"recommendation": "approved_for_release", "blocking_issues": []},
        reproducibility_record={},
    )
    base.update(overrides)
    return base


def test_generate_release_report_discloses_all_honest_limitations() -> None:
    report = generate_release_report(**_report_kwargs())
    assert report["no_deployment_performed"] is True
    assert report["no_runtime_started"] is True
    assert report["no_public_traffic_enabled"] is True
    assert report["no_inference_benchmark_executed"] is True
    assert report["thresholds_are_heuristic_governance_rules"] is True
    assert report["compliance_is_checklist_based_not_legal_certification"] is True
    assert report["approval_does_not_imply_production_safety"] is True
    assert report["rollback_plan_is_procedural_not_executable_automation"] is True
    assert "no deployment has occurred" in report["disclaimer"]


def test_generate_release_report_score_excludes_missing_components() -> None:
    report = generate_release_report(**_report_kwargs(compliance_gate_report={}))
    assert report["component_scores"]["compliance"] is None
    assert report["overall_readiness_score"] is not None


def test_generate_release_report_recommendation_matches_decision() -> None:
    report = generate_release_report(**_report_kwargs(release_decision={"recommendation": "not_approved", "blocking_issues": ["x"]}))
    assert report["final_recommendation"] == "not_approved"
    assert report["blocking_issues"] == ["x"]
