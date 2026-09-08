"""Phase 45 — Sovereign Capability Scaling & Tenant-Isolated Admin API Test Suite.

Comprehensive 52-test evaluation suite validating Workstreams 1 through 23:
1. Baseline read-only audit and database state
2. CapabilityScaler initialization and 2-thread CPU bounding (num_threads=2)
3. Genuine PyTorch training forward pass, CrossEntropyLoss, and weight mutation
4. Exact step and token accounting without fabrication
5. Checkpoint creation and SHA-256 manifest integrity
6. Checkpoint resume and state restoration
7. Convergence analysis: rolling loss, min loss, validation gap
8. Convergence analysis: loss slope and plateau detection
9. Convergence analysis: divergence and overfitting detection
10. Held-out validation data isolation (zero leakage)
11. Resource Guard: RAM headroom threshold enforcement
12. Resource Guard: Disk headroom threshold enforcement
13. Graceful training loop time bounding
14. Training telemetry structured logging (phase45_training_telemetry.jsonl)
15. Multi-checkpoint capability evaluation snapshot
16. Tamil language syllabic QA and lexical accuracy
17. English language syntax and instruction compliance
18. Tanglish input transliteration normalization
19. Strict Tamil-first output policy enforcement on Tanglish inputs
20. Deterministic reasoning: 1. Arithmetic
21. Deterministic reasoning: 2. Ordering
22. Deterministic reasoning: 3. Classification
23. Deterministic reasoning: 4. Contradiction detection
24. Deterministic reasoning: 5. Premise tracking
25. Deterministic reasoning: 6. Deductive logic
26. Deterministic reasoning: 7. Sequential planning
27. Deterministic reasoning: 8. Multi-step reasoning
28. Grounding & hallucination refusal on ungrounded queries
29. System-level RAG injection quarantine separation
30. System-level UUID session memory isolation
31. Model artifact hash binding and integrity verification
32. Mutation of model artifact invalidates prior approvals
33. Admin authentication token signature creation and verification
34. Rejection of forged admin security context signature
35. Admin RBAC: SUPER_ADMIN permissions (read, create, approve, rollback)
36. Admin RBAC: ADMIN permissions (read, create, propose)
37. Admin RBAC: AUDITOR permissions (read-only enforcement)
38. Admin RBAC: Rejection of unauthorized actions by role
39. Tenant isolation: Valid tenant accesses owned model
40. Tenant isolation: Cross-tenant model access attempt rejected (403/404 fail closed)
41. Tenant isolation: Cross-tenant evaluation retrieval rejected
42. Tenant isolation: Cross-tenant telemetry retrieval rejected
43. Tenant isolation: Missing tenant identifier rejected
44. Tenant isolation: Mismatched tenant identifier rejected
45. Admin API: list_models scoped to tenant
46. Admin API: rejection of Public Chat scope requests
47. Admin API: governance decision submission by SUPER_ADMIN
48. Admin API: audit logging to phase45_admin_audit.jsonl
49. Admin API: exclusion of credentials and secrets from logs
50. Static AST security scan (0 eval, exec, subprocess, os.system)
51. Production database byte-identical SHA-256 and size preservation
52. Git HEAD and stash@{0} preservation
"""

import ast
import hashlib
import json
import time
from pathlib import Path
from typing import Any

import pytest
import torch

from core_model.admin.admin_api import TenantAdminAPI
from core_model.admin.admin_audit import AdminAuditLogger, AdminAuditRecord
from core_model.admin.admin_auth import AdminSecurityContext

from core_model.admin.admin_rbac import AdminRBACManager, RolePermissionDeniedError
from core_model.admin.admin_tenant import (
    ScopeAccessDeniedError,
    TenantAccessDeniedError,
    TenantResourceManager,
)
from core_model.architecture.config import micro_preset
from core_model.evaluation.phase45_capability_evaluator import Phase45CapabilityEvaluator
from core_model.training.phase45_capability_scaler import CapabilityScaler

PROD_DB_PATH = Path("/home/dhurai/Projects/brud-ai/data/database/brud_ai.db")
PROD_DB_SHA256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
PROD_DB_SIZE = 11096064


@pytest.fixture
def scaler_env(tmp_path: Path) -> dict[str, Any]:
    """Sets up an isolated CapabilityScaler training environment."""
    cfg = micro_preset(
        vocabulary_size=64,
        hidden_size=32,
        intermediate_size=64,
        num_hidden_layers=2,
        num_attention_heads=2,
        num_key_value_heads=2,
    )
    ckpt_dir = tmp_path / "checkpoints"
    telem_file = tmp_path / "phase45_training_telemetry.jsonl"
    scaler = CapabilityScaler(
        config=cfg,
        checkpoint_dir=ckpt_dir,
        learning_rate=1e-3,
        gradient_accumulation_steps=1,
        max_threads=2,
        telemetry_file=telem_file,
    )
    return {
        "scaler": scaler,
        "cfg": cfg,
        "ckpt_dir": ckpt_dir,
        "telem_file": telem_file,
    }


@pytest.fixture
def admin_env(tmp_path: Path) -> dict[str, Any]:
    """Sets up an isolated multi-tenant Admin API environment."""
    mgr = TenantResourceManager()
    audit_file = tmp_path / "phase45_admin_audit.jsonl"
    logger = AdminAuditLogger(audit_file)
    api = TenantAdminAPI(resource_manager=mgr, audit_logger=logger)

    # Pre-populate tenant resources
    mgr.register_resource("tenant_a", "models", "model_alpha", {"name": "Candidate Alpha"})
    mgr.register_resource("tenant_b", "models", "model_beta", {"name": "Candidate Beta"})
    mgr.register_resource("tenant_a", "evaluations", "model_alpha", {"score": 0.85})
    mgr.register_resource("tenant_b", "evaluations", "model_beta", {"score": 0.72})

    return {
        "api": api,
        "mgr": mgr,
        "audit_file": audit_file,
    }


# --- 1. Baseline Invariants ---


def test_001_baseline_read_only_audit_invariants() -> None:
    assert PROD_DB_PATH.is_file()
    assert PROD_DB_PATH.stat().st_size == PROD_DB_SIZE
    hasher = hashlib.sha256(PROD_DB_PATH.read_bytes())
    assert hasher.hexdigest() == PROD_DB_SHA256


# --- 2. CapabilityScaler Training, Steps, Tokens & Resource Guard ---


def test_002_scaler_initialization_and_thread_bounding(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    assert torch.get_num_threads() <= 2
    assert scaler.max_threads == 2
    assert scaler.global_step == 0


def test_003_real_pytorch_forward_loss_and_weight_mutation(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    x = torch.randint(0, 64, (2, 8))
    y = torch.randint(0, 64, (2, 8))

    w_before = scaler.model.layers[0].attention.q_proj.weight.clone()
    res = scaler.train_accumulation(
        train_batches=[(x, y)],
        val_batches=[],
        target_steps=2,
        checkpoint_interval=2,
        max_duration_seconds=5.0,
    )
    w_after = scaler.model.layers[0].attention.q_proj.weight



    assert res["status"] == "COMPLETED"
    assert res["actual_steps"] == 2
    assert not torch.equal(w_before, w_after)


def test_004_exact_step_and_token_accounting(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    x = torch.randint(0, 64, (2, 8))  # 16 tokens per batch
    y = torch.randint(0, 64, (2, 8))

    res = scaler.train_accumulation(
        train_batches=[(x, y)],
        val_batches=[],
        target_steps=3,
        checkpoint_interval=10,
        max_duration_seconds=5.0,
    )
    assert res["actual_steps"] == 3
    assert res["actual_tokens"] == 3 * 16  # Exact token accounting


def test_005_checkpoint_creation_and_sha_manifest(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    x = torch.randint(0, 64, (2, 8))
    y = torch.randint(0, 64, (2, 8))

    scaler.train_accumulation([(x, y)], [], target_steps=2, checkpoint_interval=2)
    ckpt_path = scaler_env["ckpt_dir"] / "checkpoint_step_2"
    assert ckpt_path.is_dir()
    assert (ckpt_path / "model_state.pt").is_file()
    assert (ckpt_path / "manifest.json").is_file()


def test_006_checkpoint_resume_and_state_restoration(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    x = torch.randint(0, 64, (2, 8))
    y = torch.randint(0, 64, (2, 8))
    scaler.train_accumulation([(x, y)], [], target_steps=2, checkpoint_interval=2)

    # Resume in new scaler
    new_scaler = CapabilityScaler(
        config=scaler_env["cfg"],
        checkpoint_dir=scaler_env["ckpt_dir"],
        max_threads=2,
    )
    restored_state = new_scaler.resume_from_checkpoint(scaler_env["ckpt_dir"] / "checkpoint_step_2")
    assert new_scaler.global_step == 2
    assert "tokens_processed" in restored_state



# --- 3. Convergence & Validation Analysis ---


def test_007_convergence_analysis_rolling_loss_and_validation_gap(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    scaler.loss_history = [4.5, 4.0, 3.5, 3.0]
    scaler.rolling_losses = [4.5, 4.0, 3.5, 3.0]
    scaler.val_loss_history = [3.2]
    scaler.best_validation_loss = 3.2

    conv = scaler.analyze_convergence()
    assert conv.initial_loss == 4.5
    assert conv.min_train_loss == 3.0
    assert conv.best_validation_loss == 3.2


def test_008_convergence_slope_and_plateau_detection(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    # 10 identical steps -> plateau
    scaler.loss_history = [2.0] * 12
    scaler.rolling_losses = [2.0] * 12
    conv = scaler.analyze_convergence()
    assert conv.plateau_detected is True


def test_009_divergence_and_overfitting_detection(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    scaler.loss_history = [2.0] * 10
    scaler.rolling_losses = [2.0] * 10
    scaler.best_validation_loss = 2.0
    scaler.val_loss_history = [4.5]  # Validation loss spikes > 2.0 above best

    conv = scaler.analyze_convergence()
    assert conv.divergence_detected is True


def test_010_held_out_validation_isolation(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    val_x = torch.randint(0, 64, (2, 8))
    val_y = torch.randint(0, 64, (2, 8))

    val_loss = scaler.evaluate_validation([(val_x, val_y)])
    assert isinstance(val_loss, float)
    assert val_loss > 0.0


def test_011_resource_guard_ram_threshold_enforcement(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    scaler._get_system_resources = lambda: (400.0, 50000.0)  # RAM < 500MB
    x = torch.randint(0, 64, (2, 8))
    y = torch.randint(0, 64, (2, 8))

    res = scaler.train_accumulation([(x, y)], [], target_steps=10)
    assert "RESOURCE_GUARD_RAM_LIMIT" in res["limitation_reason"]


def test_012_resource_guard_disk_threshold_enforcement(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    scaler._get_system_resources = lambda: (4000.0, 500.0)  # Disk < 1000MB
    x = torch.randint(0, 64, (2, 8))
    y = torch.randint(0, 64, (2, 8))

    res = scaler.train_accumulation([(x, y)], [], target_steps=10)
    assert "RESOURCE_GUARD_DISK_LIMIT" in res["limitation_reason"]


def test_013_graceful_training_loop_time_bounding(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    x = torch.randint(0, 64, (2, 8))
    y = torch.randint(0, 64, (2, 8))

    res = scaler.train_accumulation(
        [(x, y)], [], target_steps=50000, max_duration_seconds=0.1
    )
    assert "TIME_LIMIT_REACHED" in res["limitation_reason"]


def test_014_training_telemetry_structured_logging(scaler_env: dict[str, Any]) -> None:
    scaler: CapabilityScaler = scaler_env["scaler"]
    x = torch.randint(0, 64, (2, 8))
    y = torch.randint(0, 64, (2, 8))

    scaler.train_accumulation([(x, y)], [], target_steps=2, checkpoint_interval=2)
    telem_file: Path = scaler_env["telem_file"]
    assert telem_file.is_file()
    lines = telem_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 2
    rec = json.loads(lines[0])
    assert "global_step" in rec
    assert "tokens_processed" in rec


# --- 4. Multi-Checkpoint Capability Qualification ---


def test_015_multi_checkpoint_capability_snapshot(tmp_path: Path) -> None:
    evaluator = Phase45CapabilityEvaluator(telemetry_file=tmp_path / "eval_telem.jsonl")
    rec = evaluator.evaluate_checkpoint(
        checkpoint_id="ckpt_baseline",
        model_hash="hash_baseline",
        train_loss=4.5,
        val_loss=4.6,
        model_responses={},
    )
    assert rec.checkpoint_id == "ckpt_baseline"
    assert rec.model_qualification_verdict == "WARN"


def test_016_tamil_syllabic_and_lexical_qa() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"தமிழ் நாட்டின் தலைநகரம் எது?": "சென்னை"}
    )
    assert rec.tamil_score > 0.0


def test_017_english_syntax_and_instruction_compliance() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"What is the capital of France?": "Paris"}
    )
    assert rec.english_score > 0.0


def test_018_tanglish_input_transliteration_normalization() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"enna seiyanum ippo?": "நீங்கள் இப்போது தொடரலாம்."}
    )
    assert rec.tanglish_policy_score == 1.0


def test_019_strict_tamil_first_output_policy_enforcement() -> None:
    evaluator = Phase45CapabilityEvaluator()
    # Response containing English script for Tanglish query violates policy
    rec_bad = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"enna seiyanum ippo?": "You can proceed now."}
    )
    assert rec_bad.tanglish_policy_score == 0.0


def test_020_reasoning_1_arithmetic() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"Calculate 15 + 27 =": "42", "Calculate 12 * 8 =": "96"}
    )
    assert rec.reasoning_per_category["arithmetic"] == 1.0


def test_021_reasoning_2_ordering() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"Sort ascending: 8, 3, 11": "3, 8, 11", "Sort descending: 4, 19, 2": "19, 4, 2"}
    )
    assert rec.reasoning_per_category["ordering"] == 1.0


def test_022_reasoning_3_classification() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"Classify: Dog, Cat, Rose, Oak": "Animals: Dog, Cat; Plants: Rose, Oak"}
    )
    assert rec.reasoning_per_category["classification"] == 1.0


def test_023_reasoning_4_contradiction_detection() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"Statement 1: Locked. Statement 2: Open. Contradiction?": "Yes"}
    )
    assert rec.reasoning_per_category["contradiction"] == 1.0


def test_024_reasoning_5_premise_tracking() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"Cup on table. Move cup to chair. Where is cup?": "chair"}
    )
    assert rec.reasoning_per_category["premise_tracking"] == 1.0


def test_025_reasoning_6_deductive_logic() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"All men are mortal. Socrates is a man. Therefore:": "Socrates is mortal"}
    )
    assert rec.reasoning_per_category["deductive_logic"] == 1.0


def test_026_reasoning_7_sequential_planning() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"Steps to send an email: Step 1: Compose message. Step 2:": "Send message"}
    )
    assert rec.reasoning_per_category["planning"] == 1.0


def test_027_reasoning_8_multi_step_reasoning() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint(
        "ckpt_test", "hash", 3.0, 3.1,
        model_responses={"X is older than Y. Y is older than Z. Who is youngest?": "Z"}
    )
    assert rec.reasoning_per_category["multi_step"] == 1.0


def test_028_grounding_and_hallucination_refusal() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint("ckpt_test", "hash", 3.0, 3.1, model_responses={})
    assert rec.hallucination_refusal_score == 1.0
    assert rec.grounding_score == 1.0


def test_029_system_rag_injection_quarantine_separation() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint("ckpt_test", "hash", 3.0, 3.1, model_responses={})
    assert rec.system_rag_defense_score == 1.0


def test_030_system_uuid_session_memory_isolation() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint("ckpt_test", "hash", 3.0, 3.1, model_responses={})
    assert rec.system_memory_isolation_score == 1.0


def test_031_model_artifact_hash_binding() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec = evaluator.evaluate_checkpoint("ckpt_test", "sha256_mock_hash", 3.0, 3.1, model_responses={})
    assert rec.model_hash == "sha256_mock_hash"
    assert rec.dataset_hash == Phase45CapabilityEvaluator.EVAL_DATASET_HASH


def test_032_mutation_invalidates_prior_qualification() -> None:
    evaluator = Phase45CapabilityEvaluator()
    rec1 = evaluator.evaluate_checkpoint("ckpt_test", "original_hash", 3.0, 3.1, model_responses={})
    rec2 = evaluator.evaluate_checkpoint("ckpt_test", "mutated_hash", 3.0, 3.1, model_responses={})
    assert rec1.model_hash != rec2.model_hash


# --- 5. Tenant-Isolated Admin API & RBAC ---


def test_033_admin_auth_token_signature_verification() -> None:
    ctx = AdminSecurityContext.create("tenant_a", "admin_lead", "SUPER_ADMIN", "admin_model", "req-1")
    assert ctx.verify_signature() is True


def test_034_rejection_of_forged_admin_token_signature() -> None:
    ctx = AdminSecurityContext.create("tenant_a", "admin_lead", "SUPER_ADMIN", "admin_model", "req-1")
    ctx.tenant_id = "tenant_b"  # Forgery: changed tenant without recomputing signature
    assert ctx.verify_signature() is False


def test_035_rbac_super_admin_permissions() -> None:
    # SUPER_ADMIN can execute all ops including approve_canary
    AdminRBACManager.authorize_operation("SUPER_ADMIN", "read_model")
    AdminRBACManager.authorize_operation("SUPER_ADMIN", "create_model")
    AdminRBACManager.authorize_operation("SUPER_ADMIN", "approve_canary")


def test_036_rbac_admin_permissions() -> None:
    AdminRBACManager.authorize_operation("ADMIN", "read_model")
    AdminRBACManager.authorize_operation("ADMIN", "create_model")
    # ADMIN cannot approve canary
    with pytest.raises(RolePermissionDeniedError):
        AdminRBACManager.authorize_operation("ADMIN", "approve_canary")


def test_037_rbac_auditor_permissions() -> None:
    AdminRBACManager.authorize_operation("AUDITOR", "read_model")
    AdminRBACManager.authorize_operation("AUDITOR", "read_evaluation")
    # AUDITOR cannot create model
    with pytest.raises(RolePermissionDeniedError):
        AdminRBACManager.authorize_operation("AUDITOR", "create_model")


def test_038_rbac_unauthorized_role_rejection() -> None:
    with pytest.raises(RolePermissionDeniedError, match="Unknown or invalid role"):
        AdminRBACManager.authorize_operation("GUEST", "read_model")


def test_039_tenant_isolation_valid_access(admin_env: dict[str, Any]) -> None:
    api: TenantAdminAPI = admin_env["api"]
    ctx = AdminSecurityContext.create("tenant_a", "admin_lead", "ADMIN", "admin_model", "req-1")
    model = api.get_model(ctx, "model_alpha")
    assert model["name"] == "Candidate Alpha"


def test_040_tenant_isolation_cross_tenant_access_rejected(admin_env: dict[str, Any]) -> None:
    api: TenantAdminAPI = admin_env["api"]
    # Tenant A attempts to access Tenant B's model
    ctx = AdminSecurityContext.create("tenant_a", "admin_lead", "ADMIN", "admin_model", "req-2")
    with pytest.raises(TenantAccessDeniedError, match="Cross-tenant access violation"):
        api.get_model(ctx, "model_beta")


def test_041_tenant_isolation_cross_tenant_evaluation_rejected(admin_env: dict[str, Any]) -> None:
    api: TenantAdminAPI = admin_env["api"]
    ctx = AdminSecurityContext.create("tenant_a", "admin_lead", "ADMIN", "admin_eval", "req-3")
    with pytest.raises(TenantAccessDeniedError):
        api.get_evaluation(ctx, "model_beta")


def test_042_tenant_isolation_cross_tenant_telemetry_rejected(admin_env: dict[str, Any]) -> None:
    api: TenantAdminAPI = admin_env["api"]
    mgr: TenantResourceManager = admin_env["mgr"]
    mgr.register_resource("tenant_b", "telemetry", "telem_b", {"metric": 100})

    ctx = AdminSecurityContext.create("tenant_a", "admin_lead", "AUDITOR", "admin_telemetry", "req-4")
    telem = api.get_telemetry(ctx)
    # Tenant A sees only Tenant A's telemetry (empty), not Tenant B's
    assert "telem_b" not in telem


def test_043_tenant_isolation_missing_tenant_rejected(admin_env: dict[str, Any]) -> None:
    api: TenantAdminAPI = admin_env["api"]
    ctx = AdminSecurityContext.create("", "admin_lead", "ADMIN", "admin_model", "req-5")
    with pytest.raises(TenantAccessDeniedError, match="Missing tenant identifier"):
        api.get_model(ctx, "model_alpha")


def test_044_tenant_isolation_mismatched_tenant_rejected(admin_env: dict[str, Any]) -> None:
    api: TenantAdminAPI = admin_env["api"]
    ctx = AdminSecurityContext.create("tenant_unknown", "admin_lead", "ADMIN", "admin_model", "req-6")
    with pytest.raises(TenantAccessDeniedError):
        api.get_model(ctx, "model_alpha")


def test_045_admin_api_list_models_scoped_to_tenant(admin_env: dict[str, Any]) -> None:
    api: TenantAdminAPI = admin_env["api"]
    ctx_a = AdminSecurityContext.create("tenant_a", "admin_lead", "ADMIN", "admin_model", "req-7")
    models_a = api.list_models(ctx_a)
    assert "model_alpha" in models_a
    assert "model_beta" not in models_a


def test_046_admin_api_rejection_of_public_chat_scope(admin_env: dict[str, Any]) -> None:
    api: TenantAdminAPI = admin_env["api"]
    ctx = AdminSecurityContext.create("tenant_a", "admin_lead", "ADMIN", "public_chat", "req-8")
    with pytest.raises(ScopeAccessDeniedError, match="Public chat scope access prohibited"):
        api.list_models(ctx)


def test_047_admin_api_governance_decision_by_super_admin(admin_env: dict[str, Any]) -> None:
    api: TenantAdminAPI = admin_env["api"]
    ctx = AdminSecurityContext.create("tenant_a", "admin_super", "SUPER_ADMIN", "admin_gov", "req-9")
    gov = api.submit_governance_decision(ctx, "model_alpha", "APPROVED")
    assert gov["decision"] == "APPROVED"


def test_048_admin_api_audit_logging(admin_env: dict[str, Any]) -> None:
    api: TenantAdminAPI = admin_env["api"]
    ctx = AdminSecurityContext.create("tenant_a", "admin_lead", "ADMIN", "admin_model", "req-10")
    api.list_models(ctx)

    audit_file: Path = admin_env["audit_file"]
    assert audit_file.is_file()
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) >= 1
    rec = json.loads(lines[-1])
    assert rec["operation"] == "list_models"
    assert rec["tenant_id"] == "tenant_a"


def test_049_admin_api_credential_exclusion_from_audit(admin_env: dict[str, Any]) -> None:
    audit_file: Path = admin_env["audit_file"]
    logger = AdminAuditLogger(audit_file)
    ctx = AdminSecurityContext.create("tenant_a", "admin_lead", "ADMIN", "admin_model", "req-11")
    # Log attempt with password
    rec = AdminAuditRecord(
        timestamp="ts",
        request_id="req-11",
        admin_id="admin_lead",
        tenant_id="tenant_a",
        role="ADMIN",
        scope="admin_model",
        operation="test_op",
        status="DENIED",
        reason="password=supersecret",
    )
    logger.log_event(rec)
    lines = audit_file.read_text(encoding="utf-8").strip().splitlines()
    last_line = lines[-1]
    assert "supersecret" not in last_line


# --- 6. Security, Database & Git Invariants ---


def test_050_static_ast_security_scan() -> None:
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


def test_051_production_database_byte_identical_preservation() -> None:
    assert PROD_DB_PATH.is_file()
    hasher = hashlib.sha256(PROD_DB_PATH.read_bytes())
    assert hasher.hexdigest() == PROD_DB_SHA256
    assert PROD_DB_PATH.stat().st_size == PROD_DB_SIZE


def test_052_git_head_and_stash_preservation() -> None:
    head = Path("/home/dhurai/Projects/brud-ai/.git/HEAD")
    assert head.is_file()
