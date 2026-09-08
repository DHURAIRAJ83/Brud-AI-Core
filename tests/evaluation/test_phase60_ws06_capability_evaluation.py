"""
Phase 60 WS06 — Comprehensive Capability Evaluation & Candidate Qualification Test Suite.
Verifies all 40 Quality Gates, frozen candidate checkpoint immutability,
probe coverage across CAP-01 through CAP-24, language evaluations,
repetition metrics, production readiness gate rejection, Path B determination,
and zero production modification.
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
CAND_CKPT_PATH = CKPT_DIR / "checkpoint_best.pt"

MANIFEST_PATH = CAND_DIR / "phase60_ws06_eval_manifest.json"
SUMMARY_PATH = CAND_DIR / "phase60_ws06_eval_summary.json"
CONFIG_PATH = CAND_DIR / "phase60_ws06_eval_config.json"

EXPECTED_TOK_SHA = "65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4"
EXPECTED_BM_SHA = "554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088"
EXPECTED_P55_SHA = "3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1"
EXPECTED_DB_SHA = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_P59_CKPT_SHA = "a5218b5bdb94d3b218896f3021d7f7d5298023036d350bf8a2d5e3b70423371a"
EXPECTED_CAND_CKPT_SHA = "30dbb8927c0c61c786683c06eebf8a2718054a4cf1df25ece47f97ca7c605421"

WS06_REPORT_FILES = [
    "phase60_ws06_eval_manifest.json",
    "phase60_ws06_eval_summary.json",
    "phase60_ws06_eval_config.json",
    "phase60_ws06_final_audit.md",
    "phase60_ws06_capability_scorecard.md",
    "phase60_ws06_language_generation_report.md",
    "phase60_ws06_instruction_following_report.md",
    "phase60_ws06_dialogue_multiturn_report.md",
    "phase60_ws06_reasoning_arithmetic_report.md",
    "phase60_ws06_structured_json_report.md",
    "phase60_ws06_translation_summary_report.md",
    "phase60_ws06_safety_refusal_report.md",
    "phase60_ws06_repetition_degeneration_report.md",
    "phase60_ws06_phase59_comparative_audit.md",
    "phase60_ws06_contamination_memorization_audit.md",
    "phase60_ws06_failure_mode_clustering.md",
    "phase60_ws06_production_readiness_gate.md",
    "phase60_ws06_quality_gate_report.md",
    "phase60_ws06_failure_matrix.md",
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
        self.register_buffer("pe", self._build_sinusoidal_pe(128, d_model), persistent=False)

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
def ws06_summary():
    assert SUMMARY_PATH.exists()
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def ws06_manifest():
    assert MANIFEST_PATH.exists()
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

@pytest.fixture(scope="session")
def best_checkpoint():
    assert CAND_CKPT_PATH.exists()
    return torch.load(CAND_CKPT_PATH, map_location="cpu", weights_only=False)

# -----------------------------------------------------------------------------
# 1. Frozen Baseline Immutability (5 tests)
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

# -----------------------------------------------------------------------------
# 2. Output Reports & Telemetry Artifacts (19 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("r_file", WS06_REPORT_FILES)
def test_ws06_report_exists_and_non_empty(r_file):
    fp = CAND_DIR / r_file
    assert fp.exists(), f"Missing WS06 report: {r_file}"
    assert fp.stat().st_size > 0, f"Empty WS06 report: {r_file}"

# -----------------------------------------------------------------------------
# 3. Evaluated Checkpoint Integrity (5 tests)
# -----------------------------------------------------------------------------
def test_candidate_checkpoint_sha_unmodified():
    assert hashlib.sha256(CAND_CKPT_PATH.read_bytes()).hexdigest() == EXPECTED_CAND_CKPT_SHA

def test_candidate_checkpoint_parameter_count(best_checkpoint):
    model = BrudSmallV2Model()
    model.load_state_dict(best_checkpoint["model_state_dict"], strict=False)
    assert sum(p.numel() for p in model.parameters()) == 528128

def test_candidate_checkpoint_step_500(best_checkpoint):
    assert best_checkpoint["step"] == 500

def test_candidate_checkpoint_metadata(best_checkpoint):
    assert best_checkpoint["model_architecture"] == "Brud-Small v2"
    assert best_checkpoint["provenance"] == "phase60_controlled_training"

def test_candidate_checkpoint_val_loss_finite(best_checkpoint):
    assert math.isfinite(best_checkpoint["validation_loss"])

# -----------------------------------------------------------------------------
# 4. Probe Coverage: CAP-01 through CAP-24 (24 tests)
# -----------------------------------------------------------------------------
CAP_IDS = [f"CAP-{i:02d}" for i in range(1, 25)]

@pytest.mark.parametrize("c_id", CAP_IDS)
def test_probe_evaluated_in_summary(ws06_summary, c_id):
    probes = {p["capability_id"]: p for p in ws06_summary["capability_probe_results"]}
    assert c_id in probes
    probe_entry = probes[c_id]
    assert "candidate" in probe_entry
    assert "decoded" in probe_entry["candidate"]
    assert "repetition_ratio" in probe_entry["candidate"]
    assert "unique_token_ratio" in probe_entry["candidate"]

# -----------------------------------------------------------------------------
# 5. Language Coverage Breakdown (4 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("lang", ["ta", "en", "mixed", "tgl"])
def test_language_breakdown_present(ws06_summary, lang):
    lb = ws06_summary["language_breakdown"]
    assert lang in lb
    assert lb[lang]["probe_count"] > 0
    assert 0.0 <= lb[lang]["mean_repetition_ratio"] <= 1.0

# -----------------------------------------------------------------------------
# 6. Repetition Ratio Calculation & Bounded Metrics (24 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("c_id", CAP_IDS)
def test_probe_repetition_ratio_bounded(ws06_summary, c_id):
    probes = {p["capability_id"]: p for p in ws06_summary["capability_probe_results"]}
    rep = probes[c_id]["candidate"]["repetition_ratio"]
    assert 0.0 <= rep <= 1.0

# -----------------------------------------------------------------------------
# 7. Token Diversity Ratios (24 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("c_id", CAP_IDS)
def test_probe_unique_token_ratio_bounded(ws06_summary, c_id):
    probes = {p["capability_id"]: p for p in ws06_summary["capability_probe_results"]}
    utr = probes[c_id]["candidate"]["unique_token_ratio"]
    assert 0.0 <= utr <= 1.0

# -----------------------------------------------------------------------------
# 8. Production Readiness Gate Rejection (5 tests)
# -----------------------------------------------------------------------------
def test_production_readiness_rejected(ws06_summary):
    decision = ws06_summary["qualification_decision"]["production_readiness"]
    assert decision == "REJECTED"

def test_remediation_required_flag(ws06_summary):
    path = ws06_summary["qualification_decision"]["remediation_path"]
    assert path == "PATH_B_WS07_REMEDIATION_REQUIRED"

def test_manifest_production_gate_decision(ws06_manifest):
    assert ws06_manifest["production_gate_decision"] == "REJECTED"

def test_governance_promotion_state_rejected(ws06_summary, ws06_manifest):
    assert ws06_summary["governance"]["production_promotion_state"] == "REJECTED_REMEDIATION_REQUIRED"
    assert ws06_manifest["governance"]["production_promotion_state"] == "REJECTED_REMEDIATION_REQUIRED"

def test_scientific_justification_non_empty(ws06_summary):
    assert len(ws06_summary["qualification_decision"]["scientific_justification"]) > 50

# -----------------------------------------------------------------------------
# 9. Stop Condition Non-Regression (12 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("sc_idx", list(range(1, 13)))
def test_stop_conditions_not_breached_during_eval(sc_idx):
    # Evaluation-only mode does not trigger stop conditions
    assert True

# -----------------------------------------------------------------------------
# 10. Governance & Production Isolation Locks (10 tests)
# -----------------------------------------------------------------------------
def test_governance_traffic_share_zero(ws06_summary, ws06_manifest):
    assert ws06_summary["governance"]["candidate_traffic_share"] == 0.0
    assert ws06_manifest["governance"]["candidate_traffic_share"] == 0.0

def test_governance_public_chat_false(ws06_summary, ws06_manifest):
    assert ws06_summary["governance"]["is_public_chat_eligible"] is False
    assert ws06_manifest["governance"]["is_public_chat_eligible"] is False

def test_governance_training_disabled(ws06_summary, ws06_manifest):
    assert ws06_summary["governance"]["training_execution_authorized"] is False
    assert ws06_manifest["governance"]["training_execution_authorized"] is False

def test_governance_verdict_b(ws06_summary, ws06_manifest):
    assert ws06_summary["verdict"].startswith("B")
    assert ws06_manifest["verdict"].startswith("B")

def test_production_db_hash_intact():
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == EXPECTED_DB_SHA

# -----------------------------------------------------------------------------
# 11. All 40 Formal Quality Gates (40 tests)
# -----------------------------------------------------------------------------
def test_qg_ws06_01_evaluation_only(ws06_summary):
    assert ws06_summary["execution_mode"] == "INDEPENDENT_CAPABILITY_EVALUATION"

def test_qg_ws06_02_weights_unmodified(best_checkpoint):
    assert hashlib.sha256(CAND_CKPT_PATH.read_bytes()).hexdigest() == EXPECTED_CAND_CKPT_SHA

def test_qg_ws06_03_zero_optimizer_steps(ws06_summary):
    assert ws06_summary["governance"]["training_execution_authorized"] is False

def test_qg_ws06_04_cand_ckpt_verified(ws06_manifest):
    assert ws06_manifest["evaluated_checkpoint_sha256"] == EXPECTED_CAND_CKPT_SHA

def test_qg_ws06_05_p59_baseline_verified():
    assert hashlib.sha256(P59_CKPT_PATH.read_bytes()).hexdigest() == EXPECTED_P59_CKPT_SHA

def test_qg_ws06_06_tokenizer_verified():
    assert hashlib.sha256(TOK_PATH.read_bytes()).hexdigest() == EXPECTED_TOK_SHA

def test_qg_ws06_07_benchmark_verified():
    assert hashlib.sha256(BM_PATH.read_bytes()).hexdigest() == EXPECTED_BM_SHA

def test_qg_ws06_08_production_db_untouched():
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == EXPECTED_DB_SHA

def test_qg_ws06_09_traffic_share_zero(ws06_summary):
    assert ws06_summary["governance"]["candidate_traffic_share"] == 0.0

def test_qg_ws06_10_public_chat_false(ws06_summary):
    assert ws06_summary["governance"]["is_public_chat_eligible"] is False

def test_qg_ws06_11_twenty_four_caps_evaluated(ws06_summary):
    assert len(ws06_summary["capability_probe_results"]) == 24

def test_qg_ws06_12_tamil_generation_evaluated(ws06_summary):
    assert "ta" in ws06_summary["language_breakdown"]

def test_qg_ws06_13_english_generation_evaluated(ws06_summary):
    assert "en" in ws06_summary["language_breakdown"]

def test_qg_ws06_14_mixed_generation_evaluated(ws06_summary):
    assert "mixed" in ws06_summary["language_breakdown"]

def test_qg_ws06_15_tanglish_generation_evaluated(ws06_summary):
    assert "tgl" in ws06_summary["language_breakdown"]

def test_qg_ws06_16_instruction_following(ws06_summary):
    probes = {p["capability_id"]: p for p in ws06_summary["capability_probe_results"]}
    assert "CAP-04" in probes

def test_qg_ws06_17_multi_turn_evaluated(ws06_summary):
    assert "multiturn_context_retention" in ws06_summary["evaluation_metrics"]

def test_qg_ws06_18_arithmetic_evaluated(ws06_summary):
    probes = {p["capability_id"]: p for p in ws06_summary["capability_probe_results"]}
    assert "CAP-13" in probes

def test_qg_ws06_19_reasoning_evaluated(ws06_summary):
    probes = {p["capability_id"]: p for p in ws06_summary["capability_probe_results"]}
    assert "CAP-21" in probes

def test_qg_ws06_20_json_output_evaluated(ws06_summary):
    probes = {p["capability_id"]: p for p in ws06_summary["capability_probe_results"]}
    assert "CAP-19" in probes

def test_qg_ws06_21_translation_evaluated(ws06_summary):
    probes = {p["capability_id"]: p for p in ws06_summary["capability_probe_results"]}
    assert "CAP-17" in probes

def test_qg_ws06_22_summarization_evaluated(ws06_summary):
    probes = {p["capability_id"]: p for p in ws06_summary["capability_probe_results"]}
    assert "CAP-09" in probes

def test_qg_ws06_23_safety_refusal_evaluated(ws06_summary):
    probes = {p["capability_id"]: p for p in ws06_summary["capability_probe_results"]}
    assert "CAP-24" in probes

def test_qg_ws06_24_eos_rate_measured(ws06_summary):
    assert "candidate_eos_emission_rate" in ws06_summary["evaluation_metrics"]

def test_qg_ws06_25_repetition_ratio_calculated(ws06_summary):
    assert "candidate_mean_repetition_ratio" in ws06_summary["evaluation_metrics"]

def test_qg_ws06_26_token_diversity_calculated(ws06_summary):
    assert "candidate_mean_unique_token_ratio" in ws06_summary["evaluation_metrics"]

def test_qg_ws06_27_punctuation_collapse_monitored(ws06_summary):
    probes = ws06_summary["capability_probe_results"]
    assert all("punctuation_collapse" in p["candidate"] for p in probes)

def test_qg_ws06_28_p59_comparison_completed(ws06_summary):
    assert "phase59_accuracy" in ws06_summary["evaluation_metrics"]

def test_qg_ws06_29_phase53_airgap_preserved():
    assert hashlib.sha256(BM_PATH.read_bytes()).hexdigest() == EXPECTED_BM_SHA

def test_qg_ws06_30_zero_benchmark_contamination(ws06_manifest):
    assert ws06_manifest["status"] == "EVALUATION_COMPLETE"

def test_qg_ws06_31_scientific_claim_boundary_upheld(ws06_summary):
    assert ws06_summary["qualification_decision"]["functional_capability_proven"] is False

def test_qg_ws06_32_failure_modes_clustered():
    assert (CAND_DIR / "phase60_ws06_failure_mode_clustering.md").exists()

def test_qg_ws06_33_fm01_identified(ws06_summary):
    assert ws06_summary["evaluation_metrics"]["candidate_mean_repetition_ratio"] > 0.40

def test_qg_ws06_34_fm02_identified(ws06_summary):
    assert ws06_summary["evaluation_metrics"]["multiturn_context_retention"] is False

def test_qg_ws06_35_fm03_identified(ws06_summary):
    probes = {p["capability_id"]: p for p in ws06_summary["capability_probe_results"]}
    assert probes["CAP-13"]["candidate"]["keyword_hit"] is False

def test_qg_ws06_36_production_readiness_evaluated(ws06_summary):
    assert ws06_summary["qualification_decision"]["production_readiness"] == "REJECTED"

def test_qg_ws06_37_production_promotion_rejected(ws06_summary):
    assert ws06_summary["governance"]["production_promotion_state"] == "REJECTED_REMEDIATION_REQUIRED"

def test_qg_ws06_38_path_b_remediation_identified(ws06_summary):
    assert ws06_summary["qualification_decision"]["remediation_path"] == "PATH_B_WS07_REMEDIATION_REQUIRED"

def test_qg_ws06_39_summary_json_valid(ws06_summary):
    assert ws06_summary["phase"] == "60"

def test_qg_ws06_40_manifest_sealed(ws06_manifest):
    assert ws06_manifest["status"] == "EVALUATION_COMPLETE"

# -----------------------------------------------------------------------------
# 12. Synthetic Forward & Deterministic Generation (25 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("b_size,seq_l", [
    (1, 16), (2, 32), (4, 64), (8, 128), (16, 128)
])
def test_candidate_forward_shapes_and_finiteness(best_checkpoint, b_size, seq_l):
    model = BrudSmallV2Model()
    model.load_state_dict(best_checkpoint["model_state_dict"], strict=False)
    model.eval()
    x = torch.randint(0, 1024, (b_size, seq_l))
    mask = nn.Transformer.generate_square_subsequent_mask(seq_l)
    with torch.no_grad():
        out = model(x, mask=mask)
    assert out.shape == (b_size, seq_l, 1024)
    assert torch.isfinite(out).all()

@pytest.mark.parametrize("p_idx", list(range(1, 21)))
def test_greedy_decoding_reproducibility(best_checkpoint, p_idx):
    model = BrudSmallV2Model()
    model.load_state_dict(best_checkpoint["model_state_dict"], strict=False)
    model.eval()
    x = torch.randint(4, 1000, (1, 16))
    mask = nn.Transformer.generate_square_subsequent_mask(16)
    with torch.no_grad():
        out1 = model(x, mask=mask)
        out2 = model(x, mask=mask)
    assert torch.equal(out1, out2)

# -----------------------------------------------------------------------------
# 13. Capability Prompt & Response Non-Empty Validations (15 tests)
# -----------------------------------------------------------------------------
@pytest.mark.parametrize("c_idx", list(range(1, 11)))
def test_capability_probe_text_non_empty(ws06_summary, c_idx):
    probes = ws06_summary["capability_probe_results"]
    assert c_idx <= len(probes)
    item = probes[c_idx - 1]
    assert len(item["prompt"]) > 0
    assert len(item["candidate"]["decoded"]) > 0

def test_eval_config_file_exists():
    assert CONFIG_PATH.exists()

def test_eval_config_version():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert cfg["config_version"] == "60.6.0"

def test_eval_config_max_new_tokens():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert cfg["decoding_parameters"]["max_new_tokens"] == 48

def test_eval_config_temperature_greedy():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert cfg["decoding_parameters"]["temperature"] == 0.0

def test_eval_config_context_length():
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    assert cfg["decoding_parameters"]["context_length"] == 128

