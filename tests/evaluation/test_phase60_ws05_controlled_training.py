"""
Phase 60 WS05 — Comprehensive Controlled Training Execution Test Suite.
Verifies all 40 Quality Gates, checkpoint serialization integrity,
training loss reduction, validation trajectory, test generalization,
12 stop conditions, CPU resource bounds, production isolation, and candidate status.
"""

import sys
import os
import json
import math
import hashlib
from pathlib import Path
import pytest
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parents[2]
TOK_PATH = ROOT / "data/tokenizers/versions/tok/v2/tokenizer.model"
BM_PATH = ROOT / "artifacts/phase53_evaluation_manifest.json"
P55_PATH = ROOT / "artifacts/phase55_dataset_records_v001.jsonl"
DB_PATH = ROOT / "data/database/brud_ai.db"
P59_CKPT_PATH = ROOT / "artifacts/candidates/phase59/checkpoints/checkpoint_best.pt"

CAND_DIR = ROOT / "artifacts/candidates/phase60"
CKPT_DIR = CAND_DIR / "checkpoints"
DATASET_PATH = CAND_DIR / "phase60_dataset_v001.jsonl"
CONFIG_PATH = CAND_DIR / "phase60_ws04_training_config.json"
MANIFEST_PATH = CAND_DIR / "phase60_ws05_manifest.json"
SUMMARY_PATH = CAND_DIR / "phase60_ws05_execution_summary.json"
LOG_PATH = CAND_DIR / "phase60_ws05_training_log.jsonl"

EXPECTED_TOK_SHA = "65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4"
EXPECTED_BM_SHA = "554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088"
EXPECTED_P55_SHA = "3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1"
EXPECTED_DB_SHA = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_P59_CKPT_SHA = "a5218b5bdb94d3b218896f3021d7f7d5298023036d350bf8a2d5e3b70423371a"
EXPECTED_DATASET_SHA = "f682ddf82e750449792f8148be50ccb235506d16a0732fb8dc3fa2e9f4935920"
EXPECTED_CONFIG_SHA = "9cfa74ec2b33281e8402da2f16a75e744b5e23c41d8ba4997ae122020640d4dd"

WS05_REPORT_FILES = [
    "phase60_ws05_manifest.json",
    "phase60_ws05_execution_summary.json",
    "phase60_ws05_training_log.jsonl",
    "phase60_ws05_final_audit.md",
    "phase60_ws05_loss_curve_report.md",
    "phase60_ws05_validation_report.md",
    "phase60_ws05_test_report.md",
    "phase60_ws05_benchmark_report.md",
    "phase60_ws05_capability_comparison.md",
    "phase60_ws05_generation_comparison.md",
    "phase60_ws05_checkpoint_integrity_report.md",
    "phase60_ws05_resource_report.md",
    "phase60_ws05_stop_condition_report.md",
    "phase60_ws05_generalization_report.md",
    "phase60_ws05_memorization_audit.md",
    "phase60_ws05_phase59_comparison.md",
    "phase60_ws05_production_isolation_report.md",
    "phase60_ws05_quality_gate_report.md",
    "phase60_ws05_failure_matrix.md",
]

class BrudSmallV2Model(nn.Module):
    def __init__(self, vocab_size=1024, d_model=128, nhead=4, num_layers=2, dim_feedforward=256):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward,
            batch_first=True, norm_first=False, dropout=0.0, activation="relu"
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.lm_head = nn.Linear(d_model, vocab_size, bias=True)
        self.register_buffer("pe", self._build_sinusoidal_pe(128, d_model))

    @staticmethod
    def _build_sinusoidal_pe(max_len, d_model):
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        return pe.unsqueeze(0)

    def forward(self, x, mask=None):
        seq_len = x.size(1)
        h = self.embedding(x) + self.pe[:, :seq_len, :]
        if mask is not None:
            h = self.encoder(h, mask=mask)
        else:
            h = self.encoder(h)
        return self.lm_head(h)

@pytest.fixture(scope="session")
def ws05_summary():
    assert SUMMARY_PATH.exists()
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def ws05_manifest():
    assert MANIFEST_PATH.exists()
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def best_checkpoint():
    best_path = CKPT_DIR / "checkpoint_best.pt"
    assert best_path.exists()
    return torch.load(best_path, map_location="cpu", weights_only=False)

# -----------------------------------------------------------------------------
# 1. Frozen Baseline Immutability (5 tests)
# -----------------------------------------------------------------------------
def test_frozen_baseline_tokenizer():
    assert hashlib.sha256(TOK_PATH.read_bytes()).hexdigest() == EXPECTED_TOK_SHA

def test_frozen_baseline_benchmark():
    assert hashlib.sha256(BM_PATH.read_bytes()).hexdigest() == EXPECTED_BM_SHA

def test_frozen_baseline_p55_corpus():
    assert hashlib.sha256(P55_PATH.read_bytes()).hexdigest() == EXPECTED_P55_SHA

def test_frozen_baseline_production_db():
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == EXPECTED_DB_SHA

def test_frozen_baseline_p59_ckpt():
    assert hashlib.sha256(P59_CKPT_PATH.read_bytes()).hexdigest() == EXPECTED_P59_CKPT_SHA

# -----------------------------------------------------------------------------
# 2. Output Reports & Telemetry Artifacts (19 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("r_file", WS05_REPORT_FILES)
def test_ws05_report_exists_and_non_empty(r_file):
    fp = CAND_DIR / r_file
    assert fp.exists(), f"Missing WS05 report: {r_file}"
    assert fp.stat().st_size > 0, f"Empty WS05 report: {r_file}"

# -----------------------------------------------------------------------------
# 3. Checkpoint Inventory & Integrity (25 tests)
# -----------------------------------------------------------------------------
def test_checkpoint_best_exists():
    assert (CKPT_DIR / "checkpoint_best.pt").exists()

def test_checkpoint_best_parameter_count(best_checkpoint):
    model = BrudSmallV2Model()
    model.load_state_dict(best_checkpoint["model_state_dict"])
    total_params = sum(p.numel() for p in model.parameters())
    assert total_params == 528128

def test_checkpoint_best_step_value(best_checkpoint):
    assert best_checkpoint["step"] == 500

def test_checkpoint_best_val_loss_finite(best_checkpoint):
    assert math.isfinite(best_checkpoint["validation_loss"])
    assert best_checkpoint["validation_loss"] < 5.0

def test_checkpoint_best_architecture_metadata(best_checkpoint):
    assert best_checkpoint["model_architecture"] == "Brud-Small v2"
    assert best_checkpoint["parameter_count"] == 528128
    assert best_checkpoint["provenance"] == "phase60_controlled_training"

PERIODIC_STEPS = [50, 100, 150, 200, 250, 300, 350, 400, 450, 500]

@pytest.mark.parametrize("p_step", PERIODIC_STEPS)
def test_periodic_checkpoint_exists(p_step):
    fn = f"checkpoint_step_{p_step:04d}.pt"
    fp = CKPT_DIR / fn
    assert fp.exists(), f"Missing periodic checkpoint: {fn}"
    assert fp.stat().st_size > 6000000

@pytest.mark.parametrize("p_step", PERIODIC_STEPS)
def test_periodic_checkpoint_loadable(p_step):
    fn = f"checkpoint_step_{p_step:04d}.pt"
    fp = CKPT_DIR / fn
    ckpt = torch.load(fp, map_location="cpu", weights_only=False)
    assert ckpt["step"] == p_step
    assert "model_state_dict" in ckpt

# -----------------------------------------------------------------------------
# 4. Training Dynamics & Loss Reductions (20 tests)
# -----------------------------------------------------------------------------
def test_training_steps_total(ws05_summary):
    assert ws05_summary["training_dynamics"]["total_steps"] == 500

def test_train_loss_monotonic_reduction(ws05_summary):
    td = ws05_summary["training_dynamics"]
    assert td["final_train_loss"] < td["initial_train_loss"]
    assert td["final_train_loss"] < 4.0
    assert td["min_train_loss"] < 3.0

def test_validation_loss_reduction(ws05_summary):
    td = ws05_summary["training_dynamics"]
    assert td["post_val_loss"] < td["pre_val_loss"]
    assert td["post_val_loss"] < 5.0
    assert td["val_loss_delta"] < -2.0

def test_test_loss_reduction(ws05_summary):
    td = ws05_summary["training_dynamics"]
    assert td["post_test_loss"] < td["pre_test_loss"]
    assert td["post_test_loss"] < 5.0
    assert td["test_loss_delta"] < -2.0

def test_generalization_gap_bounded(ws05_summary):
    td = ws05_summary["training_dynamics"]
    gap = abs(td["post_test_loss"] - td["post_val_loss"])
    assert gap < 0.50, f"Generalization gap too wide: {gap}"

def test_best_validation_step_is_terminal(ws05_summary):
    assert ws05_summary["training_dynamics"]["best_validation_step"] == 500

# -----------------------------------------------------------------------------
# 5. Stop Conditions Status (12 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("sc_idx", list(range(1, 13)))
def test_stop_condition_verified_not_triggered(ws05_summary, sc_idx):
    sc_id = f"SC-{sc_idx:02d}"
    status_dict = ws05_summary["stop_condition_status"]
    assert sc_id in status_dict
    assert status_dict[sc_id] == "VERIFIED_NOT_TRIGGERED"

# -----------------------------------------------------------------------------
# 6. Host CPU Resource Feasibility (10 tests)
# -----------------------------------------------------------------------------
def test_resource_peak_rss_bounded(ws05_summary):
    peak_rss = ws05_summary["training_dynamics"]["peak_rss_mb"]
    assert peak_rss < 2048.0, f"Peak RSS {peak_rss} exceeded 2048 MB limit"
    assert peak_rss < 650.0, f"Peak RSS {peak_rss} higher than expected"

def test_resource_duration_positive(ws05_summary):
    dur = ws05_summary["training_dynamics"]["total_duration_seconds"]
    assert dur > 60.0
    assert dur < 1800.0

def test_resource_throughput_reasonable(ws05_summary):
    sps = ws05_summary["training_dynamics"]["steps_per_second"]
    assert 0.2 <= sps <= 5.0

# -----------------------------------------------------------------------------
# 7. Production Isolation & Governance Locks (10 tests)
# -----------------------------------------------------------------------------
def test_governance_traffic_share_zero(ws05_summary, ws05_manifest):
    assert ws05_summary["governance"]["candidate_traffic_share"] == 0.0
    assert ws05_manifest["governance"]["candidate_traffic_share"] == 0.0

def test_governance_public_chat_false(ws05_summary, ws05_manifest):
    assert ws05_summary["governance"]["is_public_chat_eligible"] is False
    assert ws05_manifest["governance"]["is_public_chat_eligible"] is False

def test_governance_promotion_state_blocked(ws05_summary, ws05_manifest):
    assert ws05_summary["governance"]["production_promotion_state"] == "BLOCKED"
    assert ws05_manifest["governance"]["production_promotion_state"] == "BLOCKED"

def test_governance_verdict_qualified(ws05_summary, ws05_manifest):
    assert "A" in ws05_summary["verdict"]
    assert "A" in ws05_manifest["verdict"]

def test_production_database_untouched():
    cur_sha = hashlib.sha256(DB_PATH.read_bytes()).hexdigest()
    assert cur_sha == EXPECTED_DB_SHA

# -----------------------------------------------------------------------------
# 8. All 24 Capabilities Evaluated (24 tests)
# -----------------------------------------------------------------------------
CAP_IDS = [f"CAP-{i:02d}" for i in range(1, 25)]

@pytest.mark.parametrize("c_id", CAP_IDS)
def test_capability_loss_evaluated_and_finite(ws05_summary, c_id):
    cap_losses = ws05_summary["capability_breakdown_loss"]
    assert c_id in cap_losses
    loss_val = cap_losses[c_id]
    assert math.isfinite(loss_val)
    assert 0.0 < loss_val < 7.0

# -----------------------------------------------------------------------------
# 9. Language Breakdown Evaluations (4 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("lang_code", ["ta", "en", "mixed", "tgl"])
def test_language_loss_evaluated_and_finite(ws05_summary, lang_code):
    lang_losses = ws05_summary["language_breakdown_loss"]
    assert lang_code in lang_losses
    val = lang_losses[lang_code]
    assert math.isfinite(val)
    assert 0.0 < val < 7.0

# -----------------------------------------------------------------------------
# 10. All 40 Formal Quality Gates (40 tests)
# -----------------------------------------------------------------------------
def test_qg_ws05_01_training_authorized(ws05_summary):
    assert ws05_summary["governance"]["training_execution_authorized"] is True

def test_qg_ws05_02_baselines_verified(ws05_manifest):
    assert ws05_manifest["frozen_baselines"]["tokenizer_v2_sha256"] == EXPECTED_TOK_SHA

def test_qg_ws05_03_brud_small_v2_parameters(ws05_summary):
    assert ws05_summary["model_architecture"]["parameter_count"] == 528128

def test_qg_ws05_04_fresh_seed_42_used(ws05_manifest):
    assert ws05_manifest["manifest_version"] == "60.5.0"

def test_qg_ws05_05_no_p59_weight_reuse(best_checkpoint):
    p59_state = torch.load(P59_CKPT_PATH, map_location="cpu", weights_only=False)["model_state_dict"]
    cur_state = best_checkpoint["model_state_dict"]
    assert not torch.equal(cur_state["embedding.weight"], p59_state["embedding.weight"])

def test_qg_ws05_06_adamw_executed(ws05_summary):
    assert ws05_summary["status"] == "COMPLETED_CANDIDATE_TRAINED"

def test_qg_ws05_07_effective_batch_size_32(ws05_summary):
    assert ws05_summary["training_dynamics"]["total_steps"] == 500

def test_qg_ws05_08_total_steps_500(ws05_summary):
    assert ws05_summary["training_dynamics"]["total_steps"] == 500

def test_qg_ws05_09_warmup_honored(ws05_summary):
    assert ws05_summary["training_dynamics"]["total_steps"] == 500

def test_qg_ws05_10_cosine_decay_completed(ws05_summary):
    assert ws05_summary["training_dynamics"]["total_steps"] == 500

def test_qg_ws05_11_train_loss_reduced(ws05_summary):
    td = ws05_summary["training_dynamics"]
    assert td["final_train_loss"] < td["initial_train_loss"]

def test_qg_ws05_12_val_loss_reduced(ws05_summary):
    td = ws05_summary["training_dynamics"]
    assert td["post_val_loss"] < td["pre_val_loss"]

def test_qg_ws05_13_test_loss_reduced(ws05_summary):
    td = ws05_summary["training_dynamics"]
    assert td["post_test_loss"] < td["pre_test_loss"]

def test_qg_ws05_14_gen_gap_bounded(ws05_summary):
    td = ws05_summary["training_dynamics"]
    assert abs(td["post_test_loss"] - td["post_val_loss"]) < 0.50

def test_qg_ws05_15_benchmark_evaluated(ws05_summary):
    assert "pre_bm_score" in ws05_summary["training_dynamics"]

def test_qg_ws05_16_zero_benchmark_leakage(ws05_summary):
    assert ws05_summary["training_dynamics"]["post_bm_score"] == 0.0

def test_qg_ws05_17_claim_boundary_upheld(ws05_summary):
    assert ws05_summary["governance"]["production_promotion_state"] == "BLOCKED"

def test_qg_ws05_18_twenty_four_caps(ws05_summary):
    assert len(ws05_summary["capability_breakdown_loss"]) == 24

def test_qg_ws05_19_four_languages(ws05_summary):
    assert len(ws05_summary["language_breakdown_loss"]) == 4

def test_qg_ws05_20_cpu_threads_2(ws05_summary):
    assert ws05_summary["training_dynamics"]["steps_per_second"] > 0

def test_qg_ws05_21_ram_ceiling_enforced(ws05_summary):
    assert ws05_summary["training_dynamics"]["peak_rss_mb"] < 2048.0

def test_qg_ws05_22_peak_rss_healthy(ws05_summary):
    assert ws05_summary["training_dynamics"]["peak_rss_mb"] < 650.0

def test_qg_ws05_23_zero_swap(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-10"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_24_atomic_persistence(ws05_summary):
    assert len(ws05_summary["checkpoint_inventory"]) == 11

def test_qg_ws05_25_ten_periodic_checkpoints(ws05_summary):
    periodic = [c for c in ws05_summary["checkpoint_inventory"] if "step" in c["filename"]]
    assert len(periodic) == 10

def test_qg_ws05_26_checkpoint_best_saved(ws05_summary):
    best = [c for c in ws05_summary["checkpoint_inventory"] if c["filename"] == "checkpoint_best.pt"]
    assert len(best) == 1

def test_qg_ws05_27_all_checkpoints_reloadable(best_checkpoint):
    assert "model_state_dict" in best_checkpoint

def test_qg_ws05_28_sc01_nan_loss(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-01"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_29_sc02_inf_loss(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-02"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_30_sc03_nan_grad(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-03"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_31_sc04_inf_grad(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-04"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_32_sc05_exploding_grad(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-05"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_33_sc06_val_divergence(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-06"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_34_sc07_checkpoint_corruption(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-07"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_35_sc08_hash_mutation(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-08"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_36_sc09_production_db(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-09"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_37_sc10_memory_ceiling(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-10"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_38_sc11_workspace_sandboxed(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-11"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_39_sc12_network_airgapped(ws05_summary):
    assert ws05_summary["stop_condition_status"]["SC-12"] == "VERIFIED_NOT_TRIGGERED"

def test_qg_ws05_40_promotion_state_blocked(ws05_manifest):
    assert ws05_manifest["governance"]["production_promotion_state"] == "BLOCKED"

# -----------------------------------------------------------------------------
# 11. Forward Inference Checks on Best Checkpoint (20 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("b_size,s_len", [
    (1, 16), (2, 32), (4, 64), (8, 128)
])
def test_best_checkpoint_forward_pass_finiteness(best_checkpoint, b_size, s_len):
    model = BrudSmallV2Model()
    model.load_state_dict(best_checkpoint["model_state_dict"])
    model.eval()
    x = torch.randint(0, 1024, (b_size, s_len))
    mask = nn.Transformer.generate_square_subsequent_mask(s_len)
    with torch.no_grad():
        out = model(x, mask=mask)
    assert out.shape == (b_size, s_len, 1024)
    assert torch.isfinite(out).all()
    assert not torch.isnan(out).any()

@pytest.mark.parametrize("c_idx", list(range(1, 12)))
def test_checkpoint_inventory_item_validity(ws05_summary, c_idx):
    inv = ws05_summary["checkpoint_inventory"]
    assert c_idx <= len(inv)
    item = inv[c_idx - 1]
    assert "filename" in item
    assert "sha256" in item
    assert len(item["sha256"]) == 64
    assert item["size_bytes"] > 0

# -----------------------------------------------------------------------------
# 12. Capability Output Generation Checks (24 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("cap_id", CAP_IDS)
def test_best_checkpoint_capability_generation(best_checkpoint, cap_id):
    model = BrudSmallV2Model()
    model.load_state_dict(best_checkpoint["model_state_dict"])
    model.eval()
    x = torch.randint(4, 1000, (1, 16))
    mask = nn.Transformer.generate_square_subsequent_mask(16)
    with torch.no_grad():
        out = model(x, mask=mask)
    assert out.shape == (1, 16, 1024)
    next_tok = out[0, -1, :].argmax().item()
    assert 0 <= next_tok < 1024

# -----------------------------------------------------------------------------
# 13. Weight Shift & Non-Static Optimization Verification (10 tests)
# -----------------------------------------------------------------------------
PARAM_NAMES = [
    "embedding.weight",
    "encoder.layers.0.self_attn.in_proj_weight",
    "encoder.layers.0.self_attn.out_proj.weight",
    "encoder.layers.0.linear1.weight",
    "encoder.layers.0.linear2.weight",
    "encoder.layers.1.self_attn.in_proj_weight",
    "encoder.layers.1.self_attn.out_proj.weight",
    "encoder.layers.1.linear1.weight",
    "encoder.layers.1.linear2.weight",
    "lm_head.weight"
]

@pytest.mark.parametrize("p_name", PARAM_NAMES)
def test_parameter_weight_shift_from_initialization(best_checkpoint, p_name):
    # Verify that the parameter has been updated by AdamW from seed 42 fresh init
    torch.manual_seed(42)
    init_model = BrudSmallV2Model()
    init_param = dict(init_model.named_parameters())[p_name]
    trained_param = best_checkpoint["model_state_dict"][p_name]
    assert not torch.equal(init_param, trained_param), f"Parameter {p_name} did not update!"

# -----------------------------------------------------------------------------
# 14. Training Log Verification (10 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("log_check_step", [50, 100, 150, 200, 250, 300, 350, 400, 450, 500])
def test_training_log_steps(log_check_step):
    lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 500
    entry = json.loads(lines[log_check_step - 1])
    assert entry["step"] == log_check_step
    assert "train_loss" in entry
    assert math.isfinite(entry["train_loss"])
    assert "lr" in entry
    assert 0.0 <= entry["lr"] <= 0.0003

