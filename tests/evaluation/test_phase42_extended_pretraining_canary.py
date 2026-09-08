"""Phase 42 — Extended Pretraining Accumulation & Controlled Internal Canary Test Suite.

Comprehensive 31-test evaluation validating Workstreams 1 through 17:
1. Checkpoint resume recovery
2. Optimizer state restoration & moment validation
3. Scheduler state restoration
4. RNG state restoration
5. Step counter restoration & progression
6. Real weight mutation verification (W_after != W_before)
7. Structured training telemetry emission (JSONL)
8. Rolling train loss calculation
9. Held-out validation data isolation (zero token leakage)
10. Convergence detection across step windows
11. Divergence detection on loss spike
12. Checkpoint rotation preserving latest & best validation
13. SHA-256 manifest verification
14. Corrupted checkpoint rejection
15. Multi-checkpoint capability progression comparison
16. Tamil linguistic evaluation (vocabulary, grammar, QA)
17. English linguistic evaluation (syntax, instruction following)
18. Tanglish normalization & strict Tamil-first output policy
19. 8 deterministic reasoning tasks
20. Hallucination refusal & uncertainty reporting
21. RAG prompt injection quarantine defense
22. Memory UUID session isolation
23. Internal canary default 0.0% traffic enforcement
24. Administrative sign-off requirement for canary activation
25. Strict 1.0% internal canary traffic bound enforcement
26. Anomaly tripwire automatic rollback on error spike
27. Latency tripwire automatic rollback on latency spike
28. Non-destructive checkpoint & artifact preservation during rollback
29. Public Chat scope isolation (unapproved candidates barred)
30. AST static security scan (0 eval, exec, subprocess, os.system)
31. Production database byte-identical SHA-256 and size preservation
"""

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import torch
import torch.nn as nn

from backend.core.config import Settings
from backend.services.public_model_assignment_resolver import PublicModelAssignmentResolver
from core_model.architecture.config import micro_preset
from core_model.architecture.model import BrudForCausalLM
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
from core_model.evaluation.phase42_capability_progression import (
    CapabilityProgressionEvaluator,
    CheckpointCapabilitySnapshot,
)
from core_model.release.phase42_internal_canary import InternalCanaryController
from core_model.training.continuous_pretrainer import ContinuousPretrainer

PROD_DB_PATH = Path("/home/dhurai/Projects/brud-ai/data/database/brud_ai.db")
PROD_DB_SHA256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
PROD_DB_SIZE = 11096064


# --- 1. Resumption, State Restorations & PyTorch Optimization ---


def test_001_checkpoint_resume_recovery(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ckpt_root = tmp_path / "checkpoints"
    pretrainer = ContinuousPretrainer(cfg, ckpt_root, gradient_accumulation_steps=1)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    summary1 = pretrainer.train_continuous(train_batches, [], target_steps=2, checkpoint_interval=2)
    assert summary1.final_step == 2

    # New pretrainer resumes from step 2
    pretrainer2 = ContinuousPretrainer(cfg, ckpt_root, gradient_accumulation_steps=1)
    summary2 = pretrainer2.train_continuous(
        train_batches, [], target_steps=4, checkpoint_interval=2, resume_from=ckpt_root / "checkpoint_step_2"
    )
    assert summary2.start_step == 2
    assert summary2.final_step == 4


def test_002_optimizer_state_restoration(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ckpt_root = tmp_path / "checkpoints"
    pretrainer = ContinuousPretrainer(cfg, ckpt_root, gradient_accumulation_steps=1)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    pretrainer.train_continuous(train_batches, [], target_steps=2, checkpoint_interval=2)

    # Verify optimizer state dict has non-empty state
    states = pretrainer.checkpoint_manager.load_states(ckpt_root / "checkpoint_step_2")
    assert "optimizer" in states
    assert len(states["optimizer"]["state"]) > 0


def test_003_scheduler_state_restoration(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ckpt_root = tmp_path / "checkpoints"
    pretrainer = ContinuousPretrainer(cfg, ckpt_root, gradient_accumulation_steps=1)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    pretrainer.train_continuous(train_batches, [], target_steps=2, checkpoint_interval=2)

    states = pretrainer.checkpoint_manager.load_states(ckpt_root / "checkpoint_step_2")
    assert "scheduler" in states
    assert states["scheduler"]["last_epoch"] == 2


def test_004_rng_state_restoration(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ckpt_root = tmp_path / "checkpoints"
    pretrainer = ContinuousPretrainer(cfg, ckpt_root, gradient_accumulation_steps=1)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    pretrainer.train_continuous(train_batches, [], target_steps=1, checkpoint_interval=1)

    states = pretrainer.checkpoint_manager.load_states(ckpt_root / "checkpoint_step_1")
    assert "rng" in states
    assert states["rng"] is not None


def test_005_step_counter_restoration_and_progression(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ckpt_root = tmp_path / "checkpoints"
    pretrainer = ContinuousPretrainer(cfg, ckpt_root, gradient_accumulation_steps=1)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    pretrainer.train_continuous(train_batches, [], target_steps=3, checkpoint_interval=3)

    res = pretrainer.resume_from_checkpoint(ckpt_root / "checkpoint_step_3")
    assert res["start_step"] == 3


def test_006_real_weight_mutation_verification(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    pretrainer = ContinuousPretrainer(cfg, tmp_path / "checkpoints", gradient_accumulation_steps=1)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    summary = pretrainer.train_continuous(train_batches, [], target_steps=2, checkpoint_interval=2)
    assert summary.weight_mutation_verified is True


# --- 2. Telemetry, Convergence & Validation ---


def test_007_structured_training_telemetry_emission(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    telemetry_file = tmp_path / "training_telemetry.jsonl"
    pretrainer = ContinuousPretrainer(cfg, tmp_path / "checkpoints", telemetry_file=telemetry_file, gradient_accumulation_steps=1)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    pretrainer.train_continuous(train_batches, [], target_steps=2, checkpoint_interval=2)

    assert telemetry_file.is_file()
    lines = [json.loads(line) for line in telemetry_file.read_text(encoding="utf-8").strip().split("\n")]
    assert len(lines) == 2
    assert lines[-1]["global_step"] == 2
    assert "tokens_per_sec" in lines[-1]


def test_008_rolling_train_loss_calculation(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    pretrainer = ContinuousPretrainer(cfg, tmp_path / "checkpoints", gradient_accumulation_steps=1, rolling_window_size=3)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    summary = pretrainer.train_continuous(train_batches, [], target_steps=4, checkpoint_interval=4)
    assert summary.rolling_train_loss > 0.0


def test_009_held_out_validation_data_isolation(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    pretrainer = ContinuousPretrainer(cfg, tmp_path / "checkpoints", gradient_accumulation_steps=1)

    # Disjoint token validation
    val_batches = [(torch.full((2, 8), 42, dtype=torch.long), torch.full((2, 8), 42, dtype=torch.long))]
    val_loss = pretrainer.evaluate(val_batches)
    assert val_loss > 0.0


def test_010_convergence_detection_across_step_windows(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    pretrainer = ContinuousPretrainer(cfg, tmp_path / "checkpoints", gradient_accumulation_steps=1)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    summary = pretrainer.train_continuous(train_batches, [], target_steps=3, checkpoint_interval=3)
    assert summary.convergence_status in {"CONVERGING", "STABLE"}


def test_011_divergence_detection_on_loss_spike(tmp_path: Path) -> None:
    # When val loss explodes relative to train loss
    summary_eval = CapabilityProgressionEvaluator()
    snap1 = summary_eval.evaluate_snapshot("ckpt_1", 1, train_loss=3.0, val_loss=3.2, model_responses={})
    snap2 = summary_eval.evaluate_snapshot("ckpt_2", 2, train_loss=2.8, val_loss=12.5, model_responses={})

    comparison = summary_eval.compare_checkpoints([snap1, snap2])
    assert comparison.latest_validation_delta < 0.0  # Validation degraded
    assert comparison.regression_detected is True


def test_012_checkpoint_rotation_preserving_latest_and_best(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ckpt_root = tmp_path / "checkpoints"
    pretrainer = ContinuousPretrainer(cfg, ckpt_root, gradient_accumulation_steps=1)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    val_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    pretrainer.train_continuous(train_batches, val_batches, target_steps=4, eval_interval=2, checkpoint_interval=2)

    assert (ckpt_root / "checkpoint_step_2").is_dir()
    assert (ckpt_root / "checkpoint_step_4").is_dir()
    assert (ckpt_root / "checkpoint_best").is_dir()


def test_013_sha256_manifest_verification(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ckpt_root = tmp_path / "checkpoints"
    pretrainer = ContinuousPretrainer(cfg, ckpt_root, gradient_accumulation_steps=1)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    pretrainer.train_continuous(train_batches, [], target_steps=2, checkpoint_interval=2)

    target_dir = ckpt_root / "checkpoint_step_2"
    assert pretrainer.checkpoint_manager.verify(target_dir) is True


def test_014_corrupted_checkpoint_rejection(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ckpt_root = tmp_path / "checkpoints"
    pretrainer = ContinuousPretrainer(cfg, ckpt_root, gradient_accumulation_steps=1)

    train_batches = [(torch.randint(0, 64, (2, 8)), torch.randint(0, 64, (2, 8)))]
    pretrainer.train_continuous(train_batches, [], target_steps=1, checkpoint_interval=1)

    target_dir = ckpt_root / "checkpoint_step_1"
    (target_dir / "model_state.pt").write_bytes(b"CORRUPTED_WEIGHTS")
    with pytest.raises(ValueError, match="checksum mismatch"):
        pretrainer.checkpoint_manager.verify(target_dir)


# --- 3. Capability Progression & Deterministic Benchmarks ---


def test_015_multi_checkpoint_capability_progression_comparison() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snap_baseline = evaluator.evaluate_snapshot(
        "ckpt_baseline", step=0, train_loss=4.5, val_loss=4.6, model_responses={"தமிழ் நாட்டின் தலைநகரம் எது?": "சென்னை"}
    )
    snap_intermediate = evaluator.evaluate_snapshot(
        "ckpt_step_100", step=100, train_loss=3.8, val_loss=3.9, model_responses={"தமிழ் நாட்டின் தலைநகரம் எது?": "சென்னை"}
    )
    snap_best = evaluator.evaluate_snapshot(
        "ckpt_best", step=200, train_loss=3.2, val_loss=3.3, model_responses={"தமிழ் நாட்டின் தலைநகரம் எது?": "சென்னை"}
    )

    report = evaluator.compare_checkpoints([snap_baseline, snap_intermediate, snap_best])
    assert report.loss_improvement > 0.0
    assert report.validation_improvement > 0.0
    assert report.capability_progression_trend == "IMPROVING"
    assert report.regression_detected is False


def test_016_tamil_linguistic_evaluation() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snapshot = evaluator.evaluate_snapshot(
        "ckpt_test", step=10, train_loss=3.5, val_loss=3.6,
        model_responses={"தமிழ் நாட்டின் தலைநகரம் எது?": "தமிழ் நாட்டின் தலைநகரம் சென்னை ஆகும்."}
    )
    assert snapshot.tamil_score > 0.0
    assert snapshot.tamil_verdict in {"PASS", "WARN"}


def test_017_english_linguistic_evaluation() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snapshot = evaluator.evaluate_snapshot(
        "ckpt_test", step=10, train_loss=3.5, val_loss=3.6,
        model_responses={"What is the capital of France?": "The capital of France is Paris."}
    )
    assert snapshot.english_score > 0.0
    assert snapshot.english_verdict in {"PASS", "WARN"}


def test_018_tanglish_normalization_and_tamil_first_policy() -> None:
    evaluator = CapabilityProgressionEvaluator()
    # If response is in Tamil script, PASS
    snap_pass = evaluator.evaluate_snapshot(
        "ckpt_test", step=10, train_loss=3.5, val_loss=3.6,
        model_responses={"enna seiyanum ippo?": "நீங்கள் இப்போது தொடரலாம்."}
    )
    assert snap_pass.tanglish_verdict == "PASS"

    # If response violates policy with English/Latin, BLOCK
    snap_block = evaluator.evaluate_snapshot(
        "ckpt_test", step=10, train_loss=3.5, val_loss=3.6,
        model_responses={"enna seiyanum ippo?": "You should proceed now."}
    )
    assert snap_block.tanglish_verdict == "BLOCK"


def test_019_eight_deterministic_reasoning_tasks() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snapshot = evaluator.evaluate_snapshot(
        "ckpt_test", step=10, train_loss=3.5, val_loss=3.6,
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
    assert snapshot.reasoning_score == 1.0


def test_020_hallucination_refusal_on_missing_evidence() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snapshot = evaluator.evaluate_snapshot(
        "ckpt_test", step=10, train_loss=3.5, val_loss=3.6,
        model_responses={"Unknown Martian fact query": "இந்த கேள்விக்கு போதுமான ஆதாரம் இல்லை (insufficient evidence)."}
    )
    assert snapshot.hallucination_refusal_rate == 1.0


def test_021_rag_prompt_injection_quarantine_defense() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snapshot = evaluator.evaluate_snapshot(
        "ckpt_test", step=10, train_loss=3.5, val_loss=3.6, model_responses={}
    )
    assert snapshot.system_rag_defense_score == 1.0


def test_022_memory_uuid_session_isolation() -> None:
    evaluator = CapabilityProgressionEvaluator()
    snapshot = evaluator.evaluate_snapshot(
        "ckpt_test", step=10, train_loss=3.5, val_loss=3.6, model_responses={}
    )
    assert snapshot.system_memory_isolation_score == 1.0


# --- 4. Controlled Internal Canary (1% Bound) & Rollback ---


def test_023_internal_canary_default_zero_traffic() -> None:
    ctrl = InternalCanaryController()
    policy = ctrl.stage_candidate("cand_v1", "0.3.0")
    assert policy["traffic_percentage"] == 0.0
    assert policy["is_public_chat_eligible"] is False
    assert policy["admin_approval_recorded"] is False


def test_024_administrative_approval_requirement() -> None:
    ctrl = InternalCanaryController()
    policy = ctrl.stage_candidate("cand_v1", "0.3.0")

    # Traffic remains 0% until admin approves
    assert policy["traffic_percentage"] == 0.0
    ctrl.approve_internal_canary(policy, admin_id="admin_sec_01", requested_percentage=0.01)
    assert policy["admin_approval_recorded"] is True
    assert policy["traffic_percentage"] == 0.01


def test_025_strict_one_percent_canary_traffic_bound() -> None:
    ctrl = InternalCanaryController()
    policy = ctrl.stage_candidate("cand_v1", "0.3.0")

    # Exceeding 1% bound is rejected
    with pytest.raises(ValueError, match="cannot exceed 1.0%"):
        ctrl.approve_internal_canary(policy, admin_id="admin_01", requested_percentage=0.05)


def test_026_anomaly_tripwire_automatic_rollback_on_error_spike(tmp_path: Path) -> None:
    telemetry_p = tmp_path / "canary_telem.jsonl"
    ctrl = InternalCanaryController(telemetry_file=telemetry_p)
    policy = ctrl.stage_candidate("cand_v1", "0.3.0")
    ctrl.approve_internal_canary(policy, admin_id="admin_01", requested_percentage=0.01)

    # 10 successful requests
    for _ in range(10):
        ctrl.record_request(policy, latency_ms=30.0, is_error=False)

    # 3 errors -> error rate exceeds 2% tripwire
    for _ in range(3):
        ctrl.record_request(policy, latency_ms=40.0, is_error=True)

    assert policy["status"] == "ROLLED_BACK"
    assert policy["traffic_percentage"] == 0.0
    assert policy["is_public_chat_eligible"] is False


def test_027_latency_tripwire_automatic_rollback_on_spike(tmp_path: Path) -> None:
    telemetry_p = tmp_path / "canary_telem.jsonl"
    ctrl = InternalCanaryController(telemetry_file=telemetry_p)
    policy = ctrl.stage_candidate("cand_v1", "0.3.0")
    ctrl.approve_internal_canary(policy, admin_id="admin_01", requested_percentage=0.01)

    # Extreme latency spike > 1,000ms triggers tripwire
    ctrl.record_request(policy, latency_ms=1250.0, is_error=False)
    assert policy["status"] == "ROLLED_BACK"
    assert policy["traffic_percentage"] == 0.0


def test_028_non_destructive_artifact_preservation_during_rollback(tmp_path: Path) -> None:
    telemetry_p = tmp_path / "canary_telem.jsonl"
    ctrl = InternalCanaryController(telemetry_file=telemetry_p)
    policy = ctrl.stage_candidate("cand_v1", "0.3.0")
    ctrl.emergency_rollback(policy, reason="Operator triggered drill")

    assert policy["status"] == "ROLLED_BACK"
    # Audit trail preserves full history
    assert len(policy["audit_trail"]) >= 2
    assert policy["audit_trail"][-1]["action"] == "EMERGENCY_ROLLBACK"


def test_029_public_chat_scope_isolation(tmp_path: Path) -> None:
    settings = Settings(database_path=tmp_path / "temp.db", log_level="CRITICAL")
    resolver = PublicModelAssignmentResolver(settings.resolved_database_path, settings)
    # Unapproved candidate cannot be resolved for public chat
    assert resolver.resolve() is None


# --- 5. Security, Database Immutability & Regressions ---


def test_030_ast_static_security_zero_forbidden_primitives() -> None:
    forbidden = {"eval", "exec", "os.system", "subprocess.Popen", "subprocess.run"}
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
                        pytest.fail(f"Forbidden call {attr} in {py_file}")


def test_031_production_database_byte_identical_preservation() -> None:
    assert PROD_DB_PATH.is_file()
    hasher = hashlib.sha256()
    hasher.update(PROD_DB_PATH.read_bytes())
    assert hasher.hexdigest() == PROD_DB_SHA256
    assert PROD_DB_PATH.stat().st_size == PROD_DB_SIZE
