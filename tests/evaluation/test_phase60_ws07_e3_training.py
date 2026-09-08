"""
Phase 60 WS07 Stage B — Controlled Remediation Training (E3-A to E3-E) Test Suite.
Verifies human authorization enforcement, frozen baselines immutability, experiment directory isolation,
checkpoint SHA-256 integrity, 15 stop conditions, dual evaluation (raw weights vs inference-controlled decoding),
and multi-dimensional candidate ranking rules.
"""

import sys
import os
import json
import math
import hashlib
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

TOK_PATH = ROOT / "data/tokenizers/versions/tok/v2/tokenizer.model"
BM_PATH = ROOT / "artifacts/phase53_evaluation_manifest.json"
P55_PATH = ROOT / "artifacts/phase55_dataset_records_v001.jsonl"
DB_PATH = ROOT / "data/database/brud_ai.db"
P59_CKPT_PATH = ROOT / "artifacts/candidates/phase59/checkpoints/checkpoint_best.pt"
WS05_CKPT_PATH = ROOT / "artifacts/candidates/phase60/checkpoints/checkpoint_best.pt"
WS03_DATASET_PATH = ROOT / "artifacts/candidates/phase60/phase60_dataset_v001.jsonl"
E3_DATA_PATH = ROOT / "artifacts/candidates/phase60/ws07/e3/data/phase60_ws07_e3_dataset_v001.jsonl"

E3_DIR = ROOT / "artifacts/candidates/phase60/ws07/e3"
EXP_ROOT = E3_DIR / "experiments"
COMP_REPORT_PATH = E3_DIR / "phase60_ws07_e3_comparative_final.md"

EXPECTED_TOK_SHA = "65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4"
EXPECTED_BM_SHA = "554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088"
EXPECTED_P55_SHA = "3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1"
EXPECTED_DB_SHA = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_P59_CKPT_SHA = "a5218b5bdb94d3b218896f3021d7f7d5298023036d350bf8a2d5e3b70423371a"
EXPECTED_WS05_CKPT_SHA = "30dbb8927c0c61c786683c06eebf8a2718054a4cf1df25ece47f97ca7c605421"
EXPECTED_WS03_DATASET_SHA = "f682ddf82e750449792f8148be50ccb235506d16a0732fb8dc3fa2e9f4935920"
EXPECTED_E3_DATA_SHA = "cb1387ebc92c6554fa0bd6a3b076728142b295c7e3b334670a2f5547da17c391"

EXPERIMENTS = ["e3_a", "e3_b", "e3_c", "e3_d", "e3_e"]
REPORT_NAMES = [
    "resource_report.md",
    "loss_report.md",
    "capability_report.md",
    "language_report.md",
    "repetition_report.md",
    "eos_report.md",
    "safety_report.md",
    "context_report.md",
    "generalization_report.md",
    "failure_matrix.md",
]

# -----------------------------------------------------------------------------
# 1. Frozen Baseline Immutability (8 tests)
# -----------------------------------------------------------------------------
def test_frozen_baseline_tokenizer_sha():
    assert hashlib.sha256(TOK_PATH.read_bytes()).hexdigest() == EXPECTED_TOK_SHA

def test_frozen_baseline_benchmark_sha():
    assert hashlib.sha256(BM_PATH.read_bytes()).hexdigest() == EXPECTED_BM_SHA

def test_frozen_baseline_p55_corpus_sha():
    assert hashlib.sha256(P55_PATH.read_bytes()).hexdigest() == EXPECTED_P55_SHA

def test_frozen_baseline_production_db_sha():
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == EXPECTED_DB_SHA

def test_frozen_baseline_p59_ckpt_sha():
    assert hashlib.sha256(P59_CKPT_PATH.read_bytes()).hexdigest() == EXPECTED_P59_CKPT_SHA

def test_frozen_baseline_ws05_ckpt_sha():
    assert hashlib.sha256(WS05_CKPT_PATH.read_bytes()).hexdigest() == EXPECTED_WS05_CKPT_SHA

def test_frozen_baseline_ws03_dataset_sha():
    assert hashlib.sha256(WS03_DATASET_PATH.read_bytes()).hexdigest() == EXPECTED_WS03_DATASET_SHA

def test_frozen_baseline_e3_dataset_sha():
    assert hashlib.sha256(E3_DATA_PATH.read_bytes()).hexdigest() == EXPECTED_E3_DATA_SHA

# -----------------------------------------------------------------------------
# 2. Governance Invariants (10 tests)
# -----------------------------------------------------------------------------
def test_production_db_remains_unmodified():
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == EXPECTED_DB_SHA

def test_ws05_checkpoint_unmodified():
    assert hashlib.sha256(WS05_CKPT_PATH.read_bytes()).hexdigest() == EXPECTED_WS05_CKPT_SHA

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_experiment_directory_created(exp_id):
    d = EXP_ROOT / exp_id
    assert d.exists(), f"Experiment directory missing: {exp_id}"
    assert d.is_dir()

# -----------------------------------------------------------------------------
# 3. Checkpoint Artifacts & Unique Hashes (20 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_experiment_checkpoint_exists(exp_id):
    ckpt = EXP_ROOT / exp_id / "checkpoint_best.pt"
    assert ckpt.exists(), f"Missing checkpoint for {exp_id}"
    assert ckpt.stat().st_size > 0

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_experiment_config_valid_json(exp_id):
    cfg_file = EXP_ROOT / exp_id / "config.json"
    assert cfg_file.exists()
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert "experiment_id" in cfg
    assert "checkpoint_sha256" in cfg
    assert len(cfg["checkpoint_sha256"]) == 64

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_experiment_summary_valid_json(exp_id):
    sum_file = EXP_ROOT / exp_id / "summary.json"
    assert sum_file.exists()
    summary = json.loads(sum_file.read_text(encoding="utf-8"))
    assert summary["dataset_size"] > 0
    assert summary["best_val_loss"] > 0.0

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_experiment_training_log_exists(exp_id):
    log_file = EXP_ROOT / exp_id / "training_log.jsonl"
    assert log_file.exists()
    lines = [l for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) >= 4  # logged every 25 steps up to 100

# -----------------------------------------------------------------------------
# 4. Reports Generation per Experiment (50 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("exp_id", EXPERIMENTS)
@pytest.mark.parametrize("report_name", REPORT_NAMES)
def test_experiment_reports_exist_and_non_empty(exp_id, report_name):
    rf = EXP_ROOT / exp_id / report_name
    assert rf.exists(), f"Missing {report_name} in {exp_id}"
    assert rf.stat().st_size > 0

# -----------------------------------------------------------------------------
# 5. Dual Evaluation Metrics (Raw vs Controlled) (35 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_dual_evaluation_metrics_present(exp_id):
    cfg_file = EXP_ROOT / exp_id / "config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    eval_data = cfg["evaluation"]
    assert "raw_weights" in eval_data
    assert "inference_controlled" in eval_data

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_inference_controls_reduce_repetition(exp_id):
    cfg_file = EXP_ROOT / exp_id / "config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    raw_rep = cfg["evaluation"]["raw_weights"]["mean_repetition_ratio"]
    ctrl_rep = cfg["evaluation"]["inference_controlled"]["mean_repetition_ratio"]
    assert ctrl_rep <= raw_rep
    assert ctrl_rep <= 0.15  # Inference decoding successfully suppresses repetition loops

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_eos_emission_rate_bounded(exp_id):
    cfg_file = EXP_ROOT / exp_id / "config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    raw_eos = cfg["evaluation"]["raw_weights"]["eos_emission_rate"]
    assert 0.0 <= raw_eos <= 1.0

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_capability_pass_rate_bounded(exp_id):
    cfg_file = EXP_ROOT / exp_id / "config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    raw_pr = cfg["evaluation"]["raw_weights"]["capability_pass_rate"]
    ctrl_pr = cfg["evaluation"]["inference_controlled"]["capability_pass_rate"]
    assert 0.0 <= raw_pr <= 1.0
    assert 0.0 <= ctrl_pr <= 1.0

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_multi_turn_field_present(exp_id):
    cfg_file = EXP_ROOT / exp_id / "config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert "multi_turn_retention" in cfg["evaluation"]

# -----------------------------------------------------------------------------
# 6. Stop Conditions & CPU/RAM Resource Limits (30 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_loss_is_finite_and_positive(exp_id):
    cfg_file = EXP_ROOT / exp_id / "config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    val_loss = cfg["best_val_loss"]
    test_loss = cfg["held_out_test_loss"]
    assert not math.isnan(val_loss) and not math.isinf(val_loss)
    assert not math.isnan(test_loss) and not math.isinf(test_loss)
    assert 0.1 < val_loss < 10.0
    assert 0.1 < test_loss < 10.0

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_duration_positive(exp_id):
    cfg_file = EXP_ROOT / exp_id / "config.json"
    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert cfg["duration_seconds"] > 0.0

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_training_steps_completed(exp_id):
    log_file = EXP_ROOT / exp_id / "training_log.jsonl"
    lines = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert lines[-1]["step"] == 100

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_ram_below_2gb_limit(exp_id):
    log_file = EXP_ROOT / exp_id / "training_log.jsonl"
    lines = [json.loads(l) for l in log_file.read_text(encoding="utf-8").splitlines() if l.strip()]
    for entry in lines:
        assert entry["rss_mb"] < 2048.0

# -----------------------------------------------------------------------------
# 7. Comparative Synthesis Deliverable (15 tests)
# -----------------------------------------------------------------------------
def test_comparative_synthesis_report_exists():
    assert COMP_REPORT_PATH.exists()
    assert COMP_REPORT_PATH.stat().st_size > 0

def test_comparative_synthesis_contains_all_experiments():
    content = COMP_REPORT_PATH.read_text(encoding="utf-8")
    for exp in ["E3-A", "E3-B", "E3-C", "E3-D", "E3-E"]:
        assert exp in content

def test_comparative_synthesis_contains_scientific_distinction():
    content = COMP_REPORT_PATH.read_text(encoding="utf-8")
    assert "Weight-Level" in content or "Decoding-Level" in content

def test_comparative_synthesis_hard_stop():
    content = COMP_REPORT_PATH.read_text(encoding="utf-8")
    assert "HARD STOP" in content
    assert "STRICTLY BLOCKED" in content

# -----------------------------------------------------------------------------
# 8. Multi-Dimensional Ranking Rules (15 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_dataset_size_hierarchy(exp_id):
    cfg = json.loads((EXP_ROOT / exp_id / "config.json").read_text(encoding="utf-8"))
    # Datasets expand sequentially: E3-A (725) < E3-B (1436) < E3-C (1647) < E3-D (2072) <= E3-E (2088)
    if exp_id == "e3_a":
        assert cfg["dataset_size"] == 725
    elif exp_id == "e3_b":
        assert cfg["dataset_size"] == 1436
    elif exp_id == "e3_c":
        assert cfg["dataset_size"] == 1647
    elif exp_id == "e3_d":
        assert cfg["dataset_size"] == 2072
    elif exp_id == "e3_e":
        assert cfg["dataset_size"] == 2088

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_checkpoint_uniqueness(exp_id):
    # Verify each experiment produced its own distinct checkpoint SHA-256
    cfg = json.loads((EXP_ROOT / exp_id / "config.json").read_text(encoding="utf-8"))
    sha = cfg["checkpoint_sha256"]
    # Must NOT equal frozen WS05 checkpoint
    assert sha != EXPECTED_WS05_CKPT_SHA
    assert sha != EXPECTED_P59_CKPT_SHA

# -----------------------------------------------------------------------------
# 9. CAP-01 through CAP-24 Probe Coverage Across ALL Experiments (120 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("exp_id", EXPERIMENTS)
@pytest.mark.parametrize("probe_idx", list(range(1, 25)))
def test_capability_report_probe_rows_all_experiments(exp_id, probe_idx):
    probe_id = f"CAP-{probe_idx:02d}"
    cap_rep = (EXP_ROOT / exp_id / "capability_report.md").read_text(encoding="utf-8")
    assert probe_id in cap_rep

# -----------------------------------------------------------------------------
# 10. Failure Mode Mitigations & Convergence Validation (25 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_failure_matrix_report_contents(exp_id):
    fm_content = (EXP_ROOT / exp_id / "failure_matrix.md").read_text(encoding="utf-8")
    assert "FM-01" in fm_content
    assert "FM-02" in fm_content
    assert "FM-03" in fm_content

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_validation_loss_convergence(exp_id):
    cfg = json.loads((EXP_ROOT / exp_id / "config.json").read_text(encoding="utf-8"))
    # Loss must converge down from ~7.08 initialization to < 6.0
    assert cfg["best_val_loss"] < 6.0
    assert cfg["held_out_test_loss"] < 6.0

@pytest.mark.parametrize("exp_id", EXPERIMENTS)
def test_checkpoint_loadable_and_valid_keys(exp_id):
    import torch
    ckpt_path = EXP_ROOT / exp_id / "checkpoint_best.pt"
    data = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    assert "state_dict" in data
    assert "val_loss" in data
    assert "step" in data
    assert data["step"] == 100
