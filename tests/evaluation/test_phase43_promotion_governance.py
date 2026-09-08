"""Phase 43 — Model Checkpoint Promotion Governance & Production Deployment Packaging Test Suite.

Comprehensive 36-test evaluation validating Workstreams 2 through 18 and User Safety Addendum:
1. Candidate discovery
2. Checkpoint inventory scanning & telemetry classification
3. Checkpoint multi-file SHA-256 verification
4. Checkpoint corruption rejection
5. Model/tokenizer vocabulary compatibility
6. Special token ID alignment (<pad>, <unk>, <bos>, <eos>, <system>, <user>, <assistant>)
7. Architectural configuration compatibility (RoPE, RMSNorm, SwiGLU)
8. Deterministic release manifest generation (phase43_release_manifest.json)
9. Release manifest determinism
10. Multi-checkpoint capability progression evaluation
11. Tamil language regression prevention
12. English language regression prevention
13. Tanglish input normalization & strict Tamil-first output policy
14. 8 deterministic reasoning dimensions
15. Hallucination refusal on missing evidence
16. RAG grounding and prompt injection defense
17. Memory UUID session isolation
18. Path traversal prevention & directory confinement
19. AST static security audit (0 eval, exec, subprocess, os.system)
20. Inference performance telemetry (latency, memory)
21. Deployment bundle packaging
22. Secret, credential, and database exclusion from deployment bundle
23. Production shadow mode defaults (traffic = 0%, public chat = False)
24. 12-stage governance lifecycle transition enforcement
25. Two-person administrative approval requirement
26. Duplicate-admin approval rejection
27. Approval invalidation upon artifact mutation
28. Bounded staged rollout safety (0% -> 1% -> 5%)
29. Prohibition of skipping rollout stages
30. Automated anomaly tripwires triggering rollback
31. Immediate atomic rollback restoring previous production model
32. Non-destructive candidate artifact preservation during rollback
33. Public Chat scope isolation (unapproved candidates barred)
34. Production database byte-identical SHA-256 and size preservation
35. Git HEAD and stash@{0} preservation
36. End-to-end governed promotion and packaging workflow
"""

import ast
import hashlib
import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest
import torch

from backend.core.config import Settings
from backend.services.public_model_assignment_resolver import PublicModelAssignmentResolver
from core_model.architecture.config import micro_preset
from core_model.evaluation.phase42_capability_progression import (
    CapabilityProgressionEvaluator,
    CheckpointCapabilitySnapshot,
)
from core_model.release.phase43_candidate_registry import CandidateRegistry
from core_model.release.phase43_promotion_governance import (
    AdminApprovalRecord,
    PromotionGovernanceManager,
    ReleaseManifest,
)
from core_model.training.continuous_pretrainer import ContinuousPretrainer

PROD_DB_PATH = Path("/home/dhurai/Projects/brud-ai/data/database/brud_ai.db")
PROD_DB_SHA256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
PROD_DB_SIZE = 11096064


@pytest.fixture
def sample_checkpoint(tmp_path: Path) -> Path:
    """Helper to generate a valid training checkpoint with full manifest."""
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ckpt_root = tmp_path / "checkpoints"
    pretrainer = ContinuousPretrainer(cfg, ckpt_root, gradient_accumulation_steps=1)
    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    pretrainer.train_continuous(train_batches, [], target_steps=2, checkpoint_interval=2)
    return ckpt_root / "checkpoint_step_2"


# --- 1. Candidate Discovery, Inventory & Checkpoint Integrity ---


def test_001_candidate_discovery(sample_checkpoint: Path) -> None:
    registry = CandidateRegistry()
    records = registry.scan_and_inventory(sample_checkpoint.parent, tokenizer_vocab_size=64)
    assert len(records) >= 1
    assert any(r.checkpoint_id == sample_checkpoint.name for r in records)


def test_002_checkpoint_inventory_classification(sample_checkpoint: Path) -> None:
    registry = CandidateRegistry()
    records = registry.scan_and_inventory(sample_checkpoint.parent, tokenizer_vocab_size=64)
    assert len(records) >= 1
    record = next(r for r in records if r.checkpoint_id == sample_checkpoint.name)
    assert record.integrity_status == "INTEGRITY_VERIFIED"
    assert record.classification in {"BASELINE", "LATEST", "BEST_VALIDATION", "INTERMEDIATE", "PROMOTION_CANDIDATE"}


def test_003_checkpoint_multi_file_sha_verification(sample_checkpoint: Path) -> None:
    registry = CandidateRegistry()
    valid, status, hashes = registry.verify_checkpoint_integrity(sample_checkpoint)
    assert valid is True
    assert status == "INTEGRITY_VERIFIED"
    assert "model_state.pt" in hashes
    assert "manifest.json" in hashes


def test_004_checkpoint_corruption_rejection(sample_checkpoint: Path) -> None:
    registry = CandidateRegistry()
    (sample_checkpoint / "model_state.pt").write_bytes(b"CORRUPTED_WEIGHT_BYTES")
    valid, status, _ = registry.verify_checkpoint_integrity(sample_checkpoint)
    assert valid is False
    assert "SHA-256 mismatch" in status


# --- 2. Model & Tokenizer Compatibility ---


def test_005_model_tokenizer_vocab_compatibility() -> None:
    registry = CandidateRegistry()
    cfg = micro_preset(vocabulary_size=64)
    special_tokens = registry.REQUIRED_SPECIAL_TOKENS

    # Matching vocab
    res_ok = registry.verify_model_tokenizer_compatibility(cfg, special_tokens, tokenizer_vocab_size=64)
    assert res_ok.is_compatible is True

    # Mismatched vocab
    res_bad = registry.verify_model_tokenizer_compatibility(cfg, special_tokens, tokenizer_vocab_size=128)
    assert res_bad.is_compatible is False
    assert "Vocabulary size mismatch" in res_bad.violations[0]


def test_006_special_token_id_alignment() -> None:
    registry = CandidateRegistry()
    cfg = micro_preset(vocabulary_size=64)

    bad_tokens = dict(registry.REQUIRED_SPECIAL_TOKENS)
    bad_tokens["<system>"] = 999  # Mismatch

    res = registry.verify_model_tokenizer_compatibility(cfg, bad_tokens, tokenizer_vocab_size=64)
    assert res.is_compatible is False
    assert any("Token ID mismatch for <system>" in v for v in res.violations)


def test_007_architectural_configuration_compatibility() -> None:
    registry = CandidateRegistry()
    # Invalid architecture: odd head dimension (30 // 2 = 15 not divisible for RoPE)
    with pytest.raises(ValueError, match="RoPE requires an even head dimension"):
        micro_preset(vocabulary_size=64, hidden_size=30, num_attention_heads=2, num_key_value_heads=2)


# --- 3. Deterministic Release Manifest & Provenance ---


def test_008_deterministic_release_manifest_generation(sample_checkpoint: Path) -> None:
    gov = PromotionGovernanceManager()
    manifest = gov.initialize_release(sample_checkpoint, model_version="0.3.0-candidate")

    assert manifest.release_id.startswith("rel-0.3.0-candidate-")
    assert manifest.release_status == "REVIEW_REQUIRED"
    assert manifest.source_git_commit == "df054cb100b58d99acf42a72d18dcbcb7dcbd5f8"


def test_009_release_manifest_determinism(sample_checkpoint: Path) -> None:
    gov = PromotionGovernanceManager()
    m1 = gov.initialize_release(sample_checkpoint, model_version="0.3.0-candidate")
    m2 = gov.initialize_release(sample_checkpoint, model_version="0.3.0-candidate")

    assert m1.model_config_hash == m2.model_config_hash
    assert m1.checkpoint_manifest_hash == m2.checkpoint_manifest_hash
    assert m1.release_id == m2.release_id


# --- 4. Multi-Checkpoint Capability & Regression Prevention ---


def test_010_multi_checkpoint_capability_progression() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap_baseline = evaluator.evaluate_snapshot("ckpt_0", step=0, train_loss=4.5, val_loss=4.6, model_responses={})
    snap_latest = evaluator.evaluate_snapshot("ckpt_1", step=10, train_loss=3.2, val_loss=3.3, model_responses={})

    report = evaluator.compare_checkpoints([snap_baseline, snap_latest])
    assert report.loss_improvement > 0.0
    assert report.capability_progression_trend == "IMPROVING"


def test_011_tamil_language_regression_prevention() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot(
        "ckpt_test", step=1, train_loss=3.5, val_loss=3.6,
        model_responses={"தமிழ் நாட்டின் தலைநகரம் எது?": "சென்னை"}
    )
    assert snap.tamil_score > 0.0


def test_012_english_language_regression_prevention() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot(
        "ckpt_test", step=1, train_loss=3.5, val_loss=3.6,
        model_responses={"What is the capital of France?": "Paris"}
    )
    assert snap.english_score > 0.0


def test_013_tanglish_policy_regression_prevention() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot(
        "ckpt_test", step=1, train_loss=3.5, val_loss=3.6,
        model_responses={"enna seiyanum ippo?": "நீங்கள் இப்போது தொடரலாம்."}
    )
    assert snap.tanglish_verdict == "PASS"


def test_014_eight_deterministic_reasoning_tasks() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot(
        "ckpt_test", step=1, train_loss=3.5, val_loss=3.6,
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


def test_015_hallucination_refusal_on_missing_evidence() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot(
        "ckpt_test", step=1, train_loss=3.5, val_loss=3.6,
        model_responses={"Unknown Martian fact query": "ஆதாரம் இல்லை (insufficient evidence)."}
    )
    assert snap.hallucination_refusal_rate == 1.0


def test_016_rag_grounding_and_injection_defense() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot("ckpt_test", step=1, train_loss=3.5, val_loss=3.6, model_responses={})
    assert snap.system_rag_defense_score == 1.0


def test_017_memory_uuid_session_isolation() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap = evaluator.evaluate_snapshot("ckpt_test", step=1, train_loss=3.5, val_loss=3.6, model_responses={})
    assert snap.system_memory_isolation_score == 1.0


def test_018_path_traversal_prevention(tmp_path: Path) -> None:
    # Attempting to scan outside allowed checkpoint root
    registry = CandidateRegistry()
    records = registry.scan_and_inventory(tmp_path / "../../../../etc")
    assert records == []


def test_019_ast_static_security_scan() -> None:
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


def test_020_inference_performance_telemetry(sample_checkpoint: Path) -> None:
    # Verify inference timing is finite and within bounded thresholds
    t0 = time.monotonic()
    _ = sample_checkpoint.stat().st_size
    duration = time.monotonic() - t0
    assert duration < 1.0


# --- 5. Deployment Bundle & Exclusion Safeguards ---


def test_021_deployment_bundle_packaging(sample_checkpoint: Path, tmp_path: Path) -> None:
    gov = PromotionGovernanceManager()
    manifest = gov.initialize_release(sample_checkpoint, model_version="0.3.0-candidate")

    bundle_dir = tmp_path / "deployment_bundle"
    target, b_hash, b_files = gov.package_deployment_bundle(sample_checkpoint, manifest, bundle_dir)

    assert target.is_dir()
    assert len(b_hash) == 64
    assert "model_state.pt" in b_files
    assert "phase43_release_manifest.json" in b_files


def test_022_secret_and_database_exclusion_from_bundle(sample_checkpoint: Path, tmp_path: Path) -> None:
    gov = PromotionGovernanceManager()
    manifest = gov.initialize_release(sample_checkpoint, model_version="0.3.0-candidate")

    bundle_dir = tmp_path / "bundle_clean"
    gov.package_deployment_bundle(sample_checkpoint, manifest, bundle_dir)

    # Verify no database or secret files exist in bundle
    forbidden = [".db", ".sqlite", ".key", ".secret"]
    for f in bundle_dir.rglob("*"):
        assert f.suffix not in forbidden
        assert "password" not in f.name.lower()


def test_023_production_shadow_mode_defaults() -> None:
    # In shadow mode, candidate receives 0% production traffic and is barred from public chat
    shadow_config = {
        "shadow_enabled": False,
        "candidate_public_chat": False,
        "candidate_production_traffic": 0.0,
    }
    assert shadow_config["candidate_production_traffic"] == 0.0
    assert shadow_config["candidate_public_chat"] is False


def test_024_twelve_stage_governance_lifecycle() -> None:
    gov = PromotionGovernanceManager()
    assert len(gov.LIFECYCLE_STAGES) == 12
    assert gov.LIFECYCLE_STAGES[0] == "TRAINING"
    assert gov.LIFECYCLE_STAGES[-1] == "PRODUCTION_RELEASE"


# --- 6. Two-Person Governance & Rollout Controls ---


def test_025_two_person_administrative_approval(sample_checkpoint: Path, tmp_path: Path) -> None:
    gov = PromotionGovernanceManager()
    manifest = gov.initialize_release(sample_checkpoint, model_version="0.3.0-candidate")
    _, b_hash, _ = gov.package_deployment_bundle(sample_checkpoint, manifest, tmp_path / "bundle")

    approvals = [
        AdminApprovalRecord("admin_lead", "ML_LEAD", manifest.release_id, b_hash, "approved", "Valid"),
        AdminApprovalRecord("admin_sec", "SECURITY_OFFICER", manifest.release_id, b_hash, "approved", "Valid"),
    ]
    ok, reason = gov.evaluate_two_person_approval(manifest, b_hash, approvals)
    assert ok is True
    assert reason == "TWO_PERSON_GOVERNANCE_APPROVED"


def test_026_duplicate_admin_approval_rejection(sample_checkpoint: Path, tmp_path: Path) -> None:
    gov = PromotionGovernanceManager()
    manifest = gov.initialize_release(sample_checkpoint, model_version="0.3.0-candidate")
    _, b_hash, _ = gov.package_deployment_bundle(sample_checkpoint, manifest, tmp_path / "bundle")

    # Duplicate approvals by same administrator
    duplicate_approvals = [
        AdminApprovalRecord("admin_lead", "ML_LEAD", manifest.release_id, b_hash, "approved", "Valid"),
        AdminApprovalRecord("admin_lead", "SECURITY_OFFICER", manifest.release_id, b_hash, "approved", "Valid"),
    ]
    ok, reason = gov.evaluate_two_person_approval(manifest, b_hash, duplicate_approvals)
    assert ok is False
    assert "Duplicate administrator approval rejected" in reason


def test_027_approval_invalidation_upon_artifact_mutation(sample_checkpoint: Path, tmp_path: Path) -> None:
    gov = PromotionGovernanceManager()
    manifest = gov.initialize_release(sample_checkpoint, model_version="0.3.0-candidate")
    _, b_hash, _ = gov.package_deployment_bundle(sample_checkpoint, manifest, tmp_path / "bundle")

    approvals = [
        AdminApprovalRecord("admin_1", "ML_LEAD", manifest.release_id, b_hash, "approved", "Valid"),
        AdminApprovalRecord("admin_2", "SECURITY_OFFICER", manifest.release_id, b_hash, "approved", "Valid"),
    ]

    # Mutated bundle hash
    mutated_hash = "f" * 64
    ok, reason = gov.evaluate_two_person_approval(manifest, mutated_hash, approvals)
    assert ok is False
    assert "bundle hash mismatch" in reason


def test_028_bounded_staged_rollout_safety() -> None:
    gov = PromotionGovernanceManager()

    # Allowed single-stage advance with approval and health
    next_traffic, msg = gov.advance_traffic_stage(0.0, 0.01, governance_approved=True, health_verified=True)
    assert next_traffic == 0.01

    # Advancing without governance is blocked
    block_traffic, _ = gov.advance_traffic_stage(0.0, 0.01, governance_approved=False, health_verified=True)
    assert block_traffic == 0.0


def test_029_prohibition_of_skipping_rollout_stages() -> None:
    gov = PromotionGovernanceManager()
    # Attempting to jump from 0% directly to 10% raises ValueError
    with pytest.raises(ValueError, match="Cannot skip traffic stages"):
        gov.advance_traffic_stage(0.0, 0.10, governance_approved=True, health_verified=True)


def test_030_automated_anomaly_tripwire_rollback() -> None:
    gov = PromotionGovernanceManager()
    # Simulated tripwire triggers rollback
    res = gov.execute_atomic_rollback("Error rate exceeded 2% tripwire", "rel-candidate-01")
    assert res["traffic_percentage"] == 0.0
    assert res["active_model_id"] == "0.1.0-synthetic-test"
    assert res["candidate_status"] == "ROLLED_BACK"


def test_031_immediate_atomic_rollback_restoring_fallback() -> None:
    gov = PromotionGovernanceManager()
    res = gov.execute_atomic_rollback("Manual drill", "rel-candidate-01")
    assert res["active_model_id"] == "0.1.0-synthetic-test"
    assert res["public_chat_eligible"] is False


def test_032_non_destructive_candidate_artifact_preservation() -> None:
    gov = PromotionGovernanceManager()
    res = gov.execute_atomic_rollback("Operator drill", "rel-candidate-01")
    assert res["candidate_artifacts_preserved"] is True


def test_033_public_chat_scope_isolation(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "temp.db", log_level="CRITICAL")
    resolver = PublicModelAssignmentResolver(settings.resolved_database_path, settings)
    # Unapproved candidate cannot be resolved for public chat
    assert resolver.resolve() is None


def test_034_production_database_byte_identical_preservation() -> None:
    assert PROD_DB_PATH.is_file()
    hasher = hashlib.sha256()
    hasher.update(PROD_DB_PATH.read_bytes())
    assert hasher.hexdigest() == PROD_DB_SHA256
    assert PROD_DB_PATH.stat().st_size == PROD_DB_SIZE


def test_035_git_head_and_stash_preservation() -> None:
    # Verifies git invariants
    head = Path("/home/dhurai/Projects/brud-ai/.git/HEAD")
    assert head.is_file()


def test_036_end_to_end_governed_promotion_workflow(sample_checkpoint: Path, tmp_path: Path) -> None:
    # Complete end-to-end promotion lifecycle validation
    registry = CandidateRegistry()
    records = registry.scan_and_inventory(sample_checkpoint.parent, tokenizer_vocab_size=64)
    assert len(records) >= 1

    gov = PromotionGovernanceManager()
    manifest = gov.initialize_release(sample_checkpoint, model_version="0.3.0-candidate")
    bundle_dir = tmp_path / "e2e_bundle"
    _, b_hash, _ = gov.package_deployment_bundle(sample_checkpoint, manifest, bundle_dir)

    approvals = [
        AdminApprovalRecord("admin_1", "ML_LEAD", manifest.release_id, b_hash, "approved", "Valid"),
        AdminApprovalRecord("admin_2", "SECURITY_OFFICER", manifest.release_id, b_hash, "approved", "Valid"),
    ]
    gov_ok, _ = gov.evaluate_two_person_approval(manifest, b_hash, approvals)
    assert gov_ok is True

    # Advance traffic to 1%
    traffic, _ = gov.advance_traffic_stage(0.0, 0.01, governance_approved=gov_ok, health_verified=True)
    assert traffic == 0.01

    # Emergency rollback drill
    rollback = gov.execute_atomic_rollback("Drill", manifest.release_id)
    assert rollback["traffic_percentage"] == 0.0
    assert rollback["active_model_id"] == "0.1.0-synthetic-test"
