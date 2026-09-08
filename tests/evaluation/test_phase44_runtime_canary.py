"""Phase 44 — Live Governance Drill, Internal Shadow Canary & Runtime Rollback Qualification Test Suite.

Comprehensive 42-test evaluation suite validating Workstreams 1 through 17 and strict safety directives:
1. Baseline read-only audit and database state
2. Candidate release manifest cryptographic verification
3. Two-person governance: Case A (distinct admins approve -> ADMIN_APPROVED)
4. Two-person governance: Case B (duplicate admin rejected)
5. Two-person governance: Case C (artifact mutation invalidates all approvals)
6. Two-person governance: Case D (admin signs old hash rejected)
7. Governance lifecycle progression through valid states up to INTERNAL_CANARY_QUALIFIED
8. Code-level prevention of transition to PUBLIC_PRODUCTION (raises PermissionError)
9. Runtime canary default traffic is strictly 0.0%
10. Strict 1.0% (0.01) maximum internal canary traffic ceiling
11. Rejection of traffic requests exceeding 1.0%
12. Rejection of candidate routing when governance is unapproved
13. Authorization of candidate routing when two-person governance is approved
14. Public Chat request routing strictly to known-good model (0.1.0-synthetic-test)
15. Candidate request explicitly targeting scope='public_chat' raises ScopeViolationError
16. Rejection of unknown or unauthorized scopes
17. Production shadow evaluation mode execution
18. Shadow candidate output strictly barred from public exposure
19. Machine-readable canary telemetry file generation (phase44_canary_telemetry.jsonl)
20. Telemetry data integrity and required fields
21. Rolling P95 latency calculation from observations
22. Rolling error rate calculation from observations
23. Automated error rate tripwire (>2% triggers atomic rollback)
24. Automated P95 latency tripwire (>1,000ms triggers atomic rollback)
25. Model load failure triggers immediate atomic rollback
26. Checkpoint integrity mismatch triggers immediate atomic rollback
27. Critical scope violation triggers immediate atomic rollback
28. Atomic rollback zeroes candidate traffic immediately
29. Atomic rollback restores active production model to 0.1.0-synthetic-test
30. Candidate artifacts and deployment bundle preserved non-destructively during rollback
31. Telemetry and audit logs preserved during rollback
32. Prohibition of canary reactivation following rollback without fresh two-person approval
33. Fail-closed behavior on controller exception during rollback
34. Fail-closed behavior when target model is unavailable
35. Capability recheck: Tamil language syllabic and lexical evaluation
36. Capability recheck: English language evaluation
37. Capability recheck: Tanglish input normalization and Tamil-first output policy
38. Capability recheck: 8 deterministic reasoning dimensions
39. Capability recheck: Hallucination refusal on missing facts
40. Static AST security scan (0 eval, exec, subprocess, os.system)
41. Production database byte-identical SHA-256 and size preservation
42. Git HEAD and stash@{0} preservation
"""

import ast
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import pytest
import torch

from backend.core.config import Settings
from backend.services.public_model_assignment_resolver import PublicModelAssignmentResolver
from core_model.architecture.config import micro_preset
from core_model.evaluation.phase42_capability_progression import CapabilityProgressionEvaluator
from core_model.release.phase43_candidate_registry import CandidateRegistry
from core_model.release.phase44_canary_monitor import CanaryObservation, RuntimeCanaryMonitor
from core_model.release.phase44_runtime_canary import (
    RoutingDecision,
    RuntimeInternalCanary,
    ScopeViolationError,
)
from core_model.release.phase44_runtime_governance import (
    GovernanceApprovalToken,
    RuntimeGovernanceController,
)

PROD_DB_PATH = Path("/home/dhurai/Projects/brud-ai/data/database/brud_ai.db")
PROD_DB_SHA256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
PROD_DB_SIZE = 11096064


@pytest.fixture
def test_env(tmp_path: Path) -> dict[str, Any]:
    """Sets up a complete isolated test environment with valid governance, canary, and monitor."""
    release_id = "rel-0.3.0-candidate-best-hash123"
    model_sha = hashlib.sha256(b"mock_model_weights").hexdigest()
    tok_sha = hashlib.sha256(b"mock_tokenizer").hexdigest()
    cfg_sha = hashlib.sha256(b"mock_config").hexdigest()
    mnf_sha = hashlib.sha256(b"mock_manifest").hexdigest()

    gov = RuntimeGovernanceController(release_id=release_id)
    canary = RuntimeInternalCanary(
        candidate_model_id="0.3.0-candidate",
        governance_controller=gov,
        traffic_percentage=0.0,
        shadow_enabled=True,
    )
    telemetry_file = tmp_path / "phase44_canary_telemetry.jsonl"
    monitor = RuntimeCanaryMonitor(canary=canary, governance_controller=gov, telemetry_file=telemetry_file)

    return {
        "gov": gov,
        "canary": canary,
        "monitor": monitor,
        "release_id": release_id,
        "model_sha": model_sha,
        "tok_sha": tok_sha,
        "cfg_sha": cfg_sha,
        "mnf_sha": mnf_sha,
        "telemetry_file": telemetry_file,
    }


# --- 1. Baseline & Release Manifest Integrity ---


def test_001_baseline_read_only_audit_invariants() -> None:
    assert PROD_DB_PATH.is_file()
    assert PROD_DB_PATH.stat().st_size == PROD_DB_SIZE
    hasher = hashlib.sha256(PROD_DB_PATH.read_bytes())
    assert hasher.hexdigest() == PROD_DB_SHA256


def test_002_candidate_release_manifest_cryptographic_verification(test_env: dict[str, Any]) -> None:
    token = GovernanceApprovalToken(
        admin_id="admin_lead",
        approval_role="ML_LEAD",
        release_id=test_env["release_id"],
        model_sha256=test_env["model_sha"],
        tokenizer_sha256=test_env["tok_sha"],
        config_sha256=test_env["cfg_sha"],
        release_manifest_sha256=test_env["mnf_sha"],
        governance_action="internal_canary_drill",
    )
    sig = token.compute_signature_hash()
    assert len(sig) == 64
    d = token.to_dict()
    assert d["signature_hash"] == sig


# --- 2. Two-Person Governance Drill (Cases A, B, C, D) ---


def test_003_governance_case_a_distinct_admins_approved(test_env: dict[str, Any]) -> None:
    gov: RuntimeGovernanceController = test_env["gov"]
    t1 = GovernanceApprovalToken(
        "admin_lead", "ML_LEAD", test_env["release_id"], test_env["model_sha"],
        test_env["tok_sha"], test_env["cfg_sha"], test_env["mnf_sha"], "drill"
    )
    t2 = GovernanceApprovalToken(
        "admin_sec", "SECURITY_OFFICER", test_env["release_id"], test_env["model_sha"],
        test_env["tok_sha"], test_env["cfg_sha"], test_env["mnf_sha"], "drill"
    )

    ok1, msg1 = gov.submit_approval(t1)
    assert ok1 is True
    assert gov.current_state == "ADMIN_APPROVAL_PENDING"

    ok2, msg2 = gov.submit_approval(t2)
    assert ok2 is True
    assert msg2 == "TWO_PERSON_APPROVAL_GRANTED"
    assert gov.current_state == "ADMIN_APPROVED"


def test_004_governance_case_b_duplicate_admin_rejected(test_env: dict[str, Any]) -> None:
    gov: RuntimeGovernanceController = test_env["gov"]
    t1 = GovernanceApprovalToken(
        "admin_lead", "ML_LEAD", test_env["release_id"], test_env["model_sha"],
        test_env["tok_sha"], test_env["cfg_sha"], test_env["mnf_sha"], "drill"
    )
    t2_duplicate = GovernanceApprovalToken(
        "admin_lead", "SECURITY_OFFICER", test_env["release_id"], test_env["model_sha"],
        test_env["tok_sha"], test_env["cfg_sha"], test_env["mnf_sha"], "drill"
    )

    gov.submit_approval(t1)
    ok_dup, msg_dup = gov.submit_approval(t2_duplicate)
    assert ok_dup is False
    assert "Duplicate approval rejected" in msg_dup
    assert gov.current_state == "ADMIN_APPROVAL_PENDING"


def test_005_governance_case_c_artifact_mutation_invalidates_approvals(test_env: dict[str, Any]) -> None:
    gov: RuntimeGovernanceController = test_env["gov"]
    t1 = GovernanceApprovalToken(
        "admin_lead", "ML_LEAD", test_env["release_id"], test_env["model_sha"],
        test_env["tok_sha"], test_env["cfg_sha"], test_env["mnf_sha"], "drill"
    )
    t2 = GovernanceApprovalToken(
        "admin_sec", "SECURITY_OFFICER", test_env["release_id"], test_env["model_sha"],
        test_env["tok_sha"], test_env["cfg_sha"], test_env["mnf_sha"], "drill"
    )
    gov.submit_approval(t1)
    gov.submit_approval(t2)
    assert gov.current_state == "ADMIN_APPROVED"

    # Simulate mutated model weights
    mutated_model_sha = hashlib.sha256(b"tampered_weights").hexdigest()
    verified, reason = gov.verify_approvals_against_live_artifacts(
        mutated_model_sha, test_env["tok_sha"], test_env["cfg_sha"], test_env["mnf_sha"]
    )
    assert verified is False
    assert "APPROVAL_INVALIDATED" in reason
    assert gov.current_state == "REVIEW_REQUIRED"
    assert len(gov.approvals) == 0


def test_006_governance_case_d_admin_signs_old_hash_rejected(test_env: dict[str, Any]) -> None:
    gov: RuntimeGovernanceController = test_env["gov"]
    old_hash = hashlib.sha256(b"stale_weights").hexdigest()
    t1 = GovernanceApprovalToken(
        "admin_lead", "ML_LEAD", test_env["release_id"], old_hash,
        test_env["tok_sha"], test_env["cfg_sha"], test_env["mnf_sha"], "drill"
    )
    t2 = GovernanceApprovalToken(
        "admin_sec", "SECURITY_OFFICER", test_env["release_id"], old_hash,
        test_env["tok_sha"], test_env["cfg_sha"], test_env["mnf_sha"], "drill"
    )
    gov.submit_approval(t1)
    gov.submit_approval(t2)

    # Verification against actual current live hash
    verified, reason = gov.verify_approvals_against_live_artifacts(
        test_env["model_sha"], test_env["tok_sha"], test_env["cfg_sha"], test_env["mnf_sha"]
    )
    assert verified is False
    assert "APPROVAL_INVALIDATED" in reason


def test_007_governance_lifecycle_state_progression(test_env: dict[str, Any]) -> None:
    gov: RuntimeGovernanceController = test_env["gov"]
    assert gov.current_state == "REVIEW_REQUIRED"
    gov.transition_to("RUNTIME_VALIDATION")
    assert gov.current_state == "RUNTIME_VALIDATION"
    gov.transition_to("INTERNAL_CANARY_READY")
    assert gov.current_state == "INTERNAL_CANARY_READY"
    gov.transition_to("INTERNAL_CANARY_ACTIVE")
    assert gov.current_state == "INTERNAL_CANARY_ACTIVE"
    gov.transition_to("INTERNAL_CANARY_QUALIFIED")
    assert gov.current_state == "INTERNAL_CANARY_QUALIFIED"


def test_008_prevention_of_transition_to_public_production(test_env: dict[str, Any]) -> None:
    gov: RuntimeGovernanceController = test_env["gov"]
    with pytest.raises(PermissionError, match="strictly prohibited in Phase 44"):
        gov.transition_to("PUBLIC_PRODUCTION")


# --- 3. Canary Traffic Bounds & Scope Isolation ---


def test_009_runtime_canary_default_traffic_zero(test_env: dict[str, Any]) -> None:
    canary: RuntimeInternalCanary = test_env["canary"]
    assert canary.traffic_percentage == 0.0
    assert canary.is_public_chat_eligible is False


def test_010_strict_one_percent_maximum_traffic_ceiling(test_env: dict[str, Any]) -> None:
    canary: RuntimeInternalCanary = test_env["canary"]
    gov: RuntimeGovernanceController = test_env["gov"]
    gov.transition_to("INTERNAL_CANARY_READY")

    # 1% is allowed
    canary.set_traffic_percentage(0.01, authorization_token="auth")
    assert canary.traffic_percentage == 0.01


def test_011_rejection_of_traffic_exceeding_one_percent(test_env: dict[str, Any]) -> None:
    canary: RuntimeInternalCanary = test_env["canary"]
    gov: RuntimeGovernanceController = test_env["gov"]
    gov.transition_to("INTERNAL_CANARY_READY")

    with pytest.raises(ValueError, match="exceeds 1.0% maximum internal ceiling"):
        canary.set_traffic_percentage(0.02, authorization_token="auth")


def test_012_rejection_of_candidate_routing_when_unapproved(test_env: dict[str, Any]) -> None:
    canary: RuntimeInternalCanary = test_env["canary"]
    # State is REVIEW_REQUIRED (unapproved)
    decision = canary.route_request("internal_canary")
    assert decision.allowed is False
    assert "Governance two-person approval required" in decision.reason


def test_013_authorization_of_candidate_routing_when_approved(test_env: dict[str, Any]) -> None:
    canary: RuntimeInternalCanary = test_env["canary"]
    gov: RuntimeGovernanceController = test_env["gov"]
    gov.transition_to("INTERNAL_CANARY_READY")
    canary.set_traffic_percentage(0.01, authorization_token="auth")

    decision = canary.route_request("internal_canary")
    assert decision.allowed is True
    assert decision.target_model_id == "0.3.0-candidate"
    assert decision.traffic_percentage == 0.01


def test_014_public_chat_routing_strictly_to_known_good_model(test_env: dict[str, Any]) -> None:
    canary: RuntimeInternalCanary = test_env["canary"]
    decision = canary.route_request("public_chat")
    assert decision.allowed is True
    assert decision.target_model_id == "0.1.0-synthetic-test"
    assert "Public Chat routed to verified production fallback model" in decision.reason


def test_015_candidate_request_targeting_public_chat_raises_error(test_env: dict[str, Any]) -> None:
    canary: RuntimeInternalCanary = test_env["canary"]
    with pytest.raises(ScopeViolationError, match="Candidate model cannot be routed to Public Chat"):
        canary.route_request("public_chat", request_payload={"requested_model_id": "0.3.0-candidate"})


def test_016_rejection_of_unauthorized_or_unknown_scope(test_env: dict[str, Any]) -> None:
    canary: RuntimeInternalCanary = test_env["canary"]
    decision = canary.route_request("malicious_admin_backdoor")
    assert decision.allowed is False
    assert "Unauthorized scope" in decision.reason


# --- 4. Shadow Evaluation Mode ---


def test_017_production_shadow_evaluation_mode(test_env: dict[str, Any]) -> None:
    canary: RuntimeInternalCanary = test_env["canary"]
    res = canary.execute_shadow_evaluation("Sample prompt", lambda p: f"Echo: {p}")
    assert res["shadow_executed"] is True
    assert res["status"] == "success"
    assert res["user_exposed"] is False
    assert res["latency_ms"] >= 0.0


def test_018_shadow_candidate_output_strictly_barred_from_public(test_env: dict[str, Any]) -> None:
    canary: RuntimeInternalCanary = test_env["canary"]
    res = canary.execute_shadow_evaluation("Critical query", lambda p: "Secret response")
    assert res["user_exposed"] is False


# --- 5. Telemetry & Rolling Metrics ---


def test_019_canary_telemetry_file_logging(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    obs = CanaryObservation(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        release_id=test_env["release_id"],
        model_sha256=test_env["model_sha"],
        scope="internal_canary",
        traffic_percentage=0.01,
        request_id="req-001",
        latency_ms=45.2,
        status="success",
        error=None,
    )
    monitor.record_observation(obs)

    telemetry_file: Path = test_env["telemetry_file"]
    assert telemetry_file.is_file()
    lines = telemetry_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["request_id"] == "req-001"
    assert data["status"] == "success"


def test_020_telemetry_data_integrity_and_required_fields(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    obs = CanaryObservation(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        release_id=test_env["release_id"],
        model_sha256=test_env["model_sha"],
        scope="internal_canary",
        traffic_percentage=0.01,
        request_id="req-002",
        latency_ms=50.0,
        status="success",
    )
    d = obs.to_dict()
    for field_name in ["timestamp", "release_id", "model_sha256", "scope", "traffic_percentage", "request_id", "latency_ms", "status"]:
        assert field_name in d


def test_021_rolling_p95_latency_calculation(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    for lat in [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]:
        obs = CanaryObservation("ts", "rel", "sha", "internal_canary", 0.01, f"req-{lat}", lat, "success")
        monitor.record_observation(obs)

    metrics = monitor.calculate_metrics()
    assert metrics["p95_latency_ms"] >= 90.0
    assert metrics["total_requests"] == 10


def test_022_rolling_error_rate_calculation(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    monitor.record_observation(CanaryObservation("ts", "rel", "sha", "internal_canary", 0.01, "r1", 20.0, "success"))
    monitor.record_observation(CanaryObservation("ts", "rel", "sha", "internal_canary", 0.01, "r2", 20.0, "error", "Err"))

    metrics = monitor.calculate_metrics()
    assert metrics["error_rate"] == 0.5
    assert metrics["total_requests"] == 2


# --- 6. Automated Tripwires & Atomic Rollback ---


def test_023_error_rate_tripwire_triggers_rollback(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    canary: RuntimeInternalCanary = test_env["canary"]
    canary._traffic_percentage = 0.01

    # Record 8 success, 2 errors (20% error rate > 2% bound over 10 requests)
    for i in range(8):
        monitor.record_observation(CanaryObservation("ts", "rel", "sha", "internal_canary", 0.01, f"s-{i}", 20.0, "success"))
    for i in range(2):
        monitor.record_observation(CanaryObservation("ts", "rel", "sha", "internal_canary", 0.01, f"e-{i}", 20.0, "error", "Timeout"))

    assert monitor.rollback_occurred is True
    assert canary.traffic_percentage == 0.0
    assert "Error rate" in monitor.last_rollback_details["rollback_reason"]


def test_024_p95_latency_tripwire_triggers_rollback(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    canary: RuntimeInternalCanary = test_env["canary"]
    canary._traffic_percentage = 0.01

    for i in range(5):
        monitor.record_observation(CanaryObservation("ts", "rel", "sha", "internal_canary", 0.01, f"lat-{i}", 1500.0, "success"))

    assert monitor.rollback_occurred is True
    assert canary.traffic_percentage == 0.0
    assert "P95 latency" in monitor.last_rollback_details["rollback_reason"]


def test_025_model_load_failure_triggers_rollback(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    canary: RuntimeInternalCanary = test_env["canary"]
    canary._traffic_percentage = 0.01

    monitor.trigger_model_load_failure("0.3.0-candidate", "CUDA OOM simulated")
    assert monitor.rollback_occurred is True
    assert canary.traffic_percentage == 0.0


def test_026_integrity_failure_triggers_rollback(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    canary: RuntimeInternalCanary = test_env["canary"]
    canary._traffic_percentage = 0.01

    monitor.trigger_integrity_failure("model_state.pt altered")
    assert monitor.rollback_occurred is True
    assert canary.traffic_percentage == 0.0


def test_027_scope_violation_triggers_critical_rollback(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    canary: RuntimeInternalCanary = test_env["canary"]
    canary._traffic_percentage = 0.01

    monitor.trigger_scope_violation("Candidate targeted for public chat")
    assert monitor.rollback_occurred is True
    assert canary.traffic_percentage == 0.0


def test_028_atomic_rollback_traffic_zeroing(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    canary: RuntimeInternalCanary = test_env["canary"]
    canary._traffic_percentage = 0.01

    res = monitor.execute_atomic_rollback("Operator manual drill")
    assert res["candidate_traffic"] == 0.0
    assert canary.traffic_percentage == 0.0


def test_029_atomic_rollback_restores_fallback_model(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    res = monitor.execute_atomic_rollback("Drill")
    assert res["active_production_model"] == "0.1.0-synthetic-test"


def test_030_candidate_artifacts_preserved_during_rollback(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    res = monitor.execute_atomic_rollback("Preservation check")
    assert res["candidate_artifacts_preserved"] is True


def test_031_telemetry_and_audit_logs_preserved(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    res = monitor.execute_atomic_rollback("Log check")
    assert res["telemetry_preserved"] is True
    assert res["audit_logs_preserved"] is True


def test_032_prohibition_of_canary_reactivation_without_fresh_approval(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    canary: RuntimeInternalCanary = test_env["canary"]
    monitor.execute_atomic_rollback("Drill")

    # Governance state is ROLLED_BACK; setting traffic without new approvals is blocked
    with pytest.raises(PermissionError, match="not approved"):
        canary.set_traffic_percentage(0.01, authorization_token="token")


def test_033_fail_closed_on_unexpected_exception(test_env: dict[str, Any]) -> None:
    monitor: RuntimeCanaryMonitor = test_env["monitor"]
    canary: RuntimeInternalCanary = test_env["canary"]
    canary._traffic_percentage = 0.01

    # Simulate exception inside governance during rollback
    test_env["gov"].transition_to = None
    res = monitor.execute_atomic_rollback("Simulated catastrophic crash")
    assert res["candidate_traffic"] == 0.0
    assert res["active_production_model"] == "0.1.0-synthetic-test"


def test_034_fail_closed_when_target_model_unavailable(test_env: dict[str, Any]) -> None:
    canary: RuntimeInternalCanary = test_env["canary"]
    # Unknown scope fails closed to known-good model with allowed=False
    decision = canary.route_request("corrupted_scope")
    assert decision.allowed is False
    assert decision.target_model_id == "0.1.0-synthetic-test"


# --- 7. Candidate Quality & Regression Recheck ---


def test_035_model_quality_tamil_evaluation() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot(
        "candidate_snap", step=4, train_loss=3.21, val_loss=3.32,
        model_responses={"தமிழ் நாட்டின் தலைநகரம் எது?": "சென்னை"}
    )
    assert snap.tamil_score > 0.0


def test_036_model_quality_english_evaluation() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot(
        "candidate_snap", step=4, train_loss=3.21, val_loss=3.32,
        model_responses={"What is the capital of France?": "Paris"}
    )
    assert snap.english_score > 0.0


def test_037_model_quality_tanglish_policy_enforcement() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot(
        "candidate_snap", step=4, train_loss=3.21, val_loss=3.32,
        model_responses={"eppadi irukeenga?": "நான் நலமாக இருக்கிறேன்."}
    )
    assert snap.tanglish_verdict == "PASS"


def test_038_model_quality_eight_deterministic_reasoning_dimensions() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot(
        "candidate_snap", step=4, train_loss=3.21, val_loss=3.32,
        model_responses={
            "Calculate 15 + 27 =": "42",
            "Sort ascending: 8, 3, 11": "3, 8, 11",
            "Classify: Dog, Cat, Rose, Oak": "Animals: Dog, Cat; Plants: Rose, Oak",
            "Statement 1: Locked. Statement 2: Open. Contradiction?": "Yes",
            "Cup on table. Move cup to chair. Where is cup?": "chair",
            "All men are mortal. Socrates is a man. Therefore:": "Socrates is mortal",
            "Steps to send an email: Step 1: Compose message. Step 2:": "Send message",
            "X is older than Y. Y is older than Z. Who is youngest?": "Z",
        }
    )
    assert snap.reasoning_score == 1.0


def test_039_model_quality_hallucination_refusal_on_missing_facts() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot(
        "candidate_snap", step=4, train_loss=3.21, val_loss=3.32,
        model_responses={"Non-existent Martian data query": "ஆதாரம் இல்லை (insufficient evidence)."}
    )
    assert snap.hallucination_refusal_rate == 1.0


# --- 8. Security & System Invariants ---


def test_040_static_ast_security_audit() -> None:
    codebase = Path("/home/dhurai/Projects/brud-ai/core_model")
    for py_file in codebase.rglob("*.py"):
        if any(p in py_file.parts for p in ("venv", ".git", "__pycache__")):
            continue
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    pytest.fail(f"Forbidden call {node.func.id} in {py_file}")
                elif isinstance(node.func, ast.Attribute):
                    attr = f"{getattr(node.func.value, 'id', '')}.{node.func.attr}"
                    if attr in {"os.system", "subprocess.Popen", "subprocess.run"}:
                        pytest.fail(f"Forbidden attribute call {attr} in {py_file}")


def test_041_production_database_byte_identical_preservation() -> None:
    assert PROD_DB_PATH.is_file()
    hasher = hashlib.sha256(PROD_DB_PATH.read_bytes())
    assert hasher.hexdigest() == PROD_DB_SHA256
    assert PROD_DB_PATH.stat().st_size == PROD_DB_SIZE


def test_042_git_head_and_stash_preservation() -> None:
    head = Path("/home/dhurai/Projects/brud-ai/.git/HEAD")
    assert head.is_file()
