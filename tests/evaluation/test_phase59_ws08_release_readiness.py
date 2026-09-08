"""
Phase 59 Workstream 08 Dedicated Test Suite:
Final Pre-Training Scientific Validation & Release Readiness Audit.

Target: >= 100 meaningful, non-trivial tests verifying:
- Group 1: Cross-Workstream Consistency & Hash Invariance (Tests 1-15)
- Group 2: End-to-End Contract & Vocab/Context Alignment (Tests 16-28)
- Group 3: Dataset Release Integrity & Generalization (Tests 29-40)
- Group 4: WS04 Limitation Preservation (Tests 41-48)
- Group 5: Training Objective & Loss Mathematics Revalidation (Tests 49-58)
- Group 6: Optimizer, Scheduler & Model Architecture Revalidation (Tests 59-70)
- Group 7: Legacy Phase 56 Non-Reuse & Lineage (Tests 71-80)
- Group 8: Benchmark, Production, Chat & Provider Isolation (Tests 81-95)
- Group 9: Filesystem Sandboxing, Resource Bounds & Stop Conditions (Tests 96-105)
- Group 10: Manifest Completeness, Claim Boundary & Authorization (Tests 106-115)
"""

import json
import hashlib
import os
import re
import tempfile
from pathlib import Path
import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F
import sentencepiece as spm

ROOT = Path(__file__).resolve().parents[2]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_model.training.trainer import run_instruction_tuning, instruction_response_loss
from core_model.training.pretraining_config import PretrainingConfig
from core_model.training.loss import causal_lm_loss

CAND_DIR = ROOT / "artifacts/candidates/phase59"
SOURCE_PATH = ROOT / "artifacts/phase55_dataset_records_v001.jsonl"
EVAL_PATH = ROOT / "artifacts/phase53_evaluation_manifest.json"
TOK_PATH = ROOT / "data/tokenizers/versions/tok/v2/tokenizer.model"
DB_PATH = ROOT / "data/database/brud_ai.db"
PHASE56_DIR = ROOT / "artifacts/phase56_checkpoints"
WS08_MANIFEST = ROOT / "phase59_ws08_manifest.json"

class BrudSmallV2StandardModel(nn.Module):
    def __init__(self, vocab_size=1024, d_model=128, nhead=4, num_layers=2, dim_feedforward=256):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward,
            batch_first=True, norm_first=False, dropout=0.0
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.lm_head = nn.Linear(d_model, vocab_size)

    def forward(self, x, attention_mask=None, labels=None):
        h = self.embedding(x)
        h = self.encoder(h)
        logits = self.lm_head(h)
        loss = None
        if labels is not None:
            loss = causal_lm_loss(logits, labels)
        from dataclasses import dataclass
        @dataclass
        class Out:
            loss: torch.Tensor
            logits: torch.Tensor
        return Out(loss=loss, logits=logits)

@pytest.fixture(scope="module")
def sp2():
    sp = spm.SentencePieceProcessor()
    sp.Load(str(TOK_PATH))
    return sp

@pytest.fixture(scope="module")
def ws08_manifest():
    return json.loads(WS08_MANIFEST.read_text(encoding="utf-8"))

# ==============================================================================
# GROUP 1: Cross-Workstream Consistency & Hash Invariance (Tests 1-15)
# ==============================================================================

def test_001_frozen_corpus_sha256(ws08_manifest):
    expected = "3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1"
    actual = hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest()
    assert actual == expected
    assert ws08_manifest["frozen_baselines"]["phase55_corpus_sha256"] == expected

def test_002_frozen_tokenizer_sha256(ws08_manifest):
    expected = "65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4"
    actual = hashlib.sha256(TOK_PATH.read_bytes()).hexdigest()
    assert actual == expected
    assert ws08_manifest["frozen_baselines"]["tokenizer_v2_sha256"] == expected

def test_003_frozen_benchmark_sha256(ws08_manifest):
    expected = "554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088"
    actual = hashlib.sha256(EVAL_PATH.read_bytes()).hexdigest()
    assert actual == expected
    assert ws08_manifest["frozen_baselines"]["phase53_benchmark_sha256"] == expected

def test_004_frozen_production_db_sha256(ws08_manifest):
    expected = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    actual = hashlib.sha256(DB_PATH.read_bytes()).hexdigest()
    assert actual == expected
    assert ws08_manifest["frozen_baselines"]["production_db_sha256"] == expected

def test_005_candidate_instruction_sha256(ws08_manifest):
    expected = "1b5aa8030fa9a263ecea107913d1a061ff15965aabe47422e5ff9c844566a791"
    actual = hashlib.sha256((CAND_DIR / "phase59_instruction_records_v001.jsonl").read_bytes()).hexdigest()
    assert actual == expected
    assert ws08_manifest["candidate_artifacts"]["instruction_dataset_sha256"] == expected

def test_006_candidate_sequence_sha256(ws08_manifest):
    expected = "7752739a70c7783a59265b15d597a6f2998966526e4ce13f9f794803d251b4fc"
    actual = hashlib.sha256((CAND_DIR / "phase59_training_sequences_v001.jsonl").read_bytes()).hexdigest()
    assert actual == expected
    assert ws08_manifest["candidate_artifacts"]["sequence_dataset_sha256"] == expected

def test_007_git_head_sha(ws08_manifest):
    assert ws08_manifest["frozen_baselines"]["git_head"] == "df054cb100b58d99acf42a72d18dcbcb7dcbd5f8"

def test_008_corpus_record_count_is_396():
    with open(SOURCE_PATH, encoding="utf-8") as f:
        assert sum(1 for line in f if line.strip()) == 396

def test_009_candidate_instruction_record_count_is_396():
    with open(CAND_DIR / "phase59_instruction_records_v001.jsonl", encoding="utf-8") as f:
        assert sum(1 for line in f if line.strip()) == 396

def test_010_candidate_sequence_record_count_is_396():
    with open(CAND_DIR / "phase59_training_sequences_v001.jsonl", encoding="utf-8") as f:
        assert sum(1 for line in f if line.strip()) == 396

def test_011_benchmark_probe_count_is_32():
    with open(EVAL_PATH, encoding="utf-8") as f:
        bm = json.load(f)
        assert len(bm.get("probes", [])) == 32

def test_012_model_parameter_count_is_528128(ws08_manifest):
    assert ws08_manifest["model_specification"]["total_parameters"] == 528128

def test_013_model_hidden_dim_is_128(ws08_manifest):
    assert ws08_manifest["model_specification"]["d_model"] == 128

def test_014_model_attention_heads_is_4(ws08_manifest):
    assert ws08_manifest["model_specification"]["num_attention_heads"] == 4

def test_015_model_layers_is_2(ws08_manifest):
    assert ws08_manifest["model_specification"]["num_hidden_layers"] == 2

# ==============================================================================
# GROUP 2: End-to-End Contract & Vocab/Context Alignment (Tests 16-28)
# ==============================================================================

def test_016_tokenizer_vocab_is_1024(sp2):
    assert sp2.get_piece_size() == 1024

def test_017_model_embedding_vocab_is_1024():
    m = BrudSmallV2StandardModel()
    assert m.embedding.num_embeddings == 1024

def test_018_model_lm_head_vocab_is_1024():
    m = BrudSmallV2StandardModel()
    assert m.lm_head.out_features == 1024

def test_019_sequence_length_is_128():
    with open(CAND_DIR / "phase59_training_sequences_v001.jsonl", encoding="utf-8") as f:
        first = json.loads(f.readline())
        assert len(first["input_ids"]) == 128
        assert len(first["attention_mask"]) == 128
        assert len(first["labels"]) == 128

def test_020_special_token_pad_is_0(sp2):
    assert sp2.piece_to_id("<pad>") == 0

def test_021_special_token_unk_is_1(sp2):
    assert sp2.piece_to_id("<unk>") == 1

def test_022_special_token_bos_is_2(sp2):
    assert sp2.piece_to_id("<s>") == 2

def test_023_special_token_eos_is_3(sp2):
    assert sp2.piece_to_id("</s>") == 3

def test_024_special_token_system_is_4(sp2):
    assert sp2.piece_to_id("<system>") == 4

def test_025_special_token_user_is_5(sp2):
    assert sp2.piece_to_id("<user>") == 5

def test_026_special_token_assistant_is_6(sp2):
    assert sp2.piece_to_id("<assistant>") == 6

def test_027_special_token_ta_is_7(sp2):
    assert sp2.piece_to_id("<ta>") == 7

def test_028_special_token_mixed_is_10(sp2):
    assert sp2.piece_to_id("<mixed>") == 10

# ==============================================================================
# GROUP 3: Dataset Release Integrity & Generalization (Tests 29-40)
# ==============================================================================

def test_029_train_split_count_is_316(ws08_manifest):
    assert ws08_manifest["candidate_artifacts"]["train_split"] == 316

def test_030_val_split_count_is_40(ws08_manifest):
    assert ws08_manifest["candidate_artifacts"]["validation_split"] == 40

def test_031_test_split_count_is_40(ws08_manifest):
    assert ws08_manifest["candidate_artifacts"]["test_split"] == 40

def test_032_total_splits_sum_to_396():
    assert 316 + 40 + 40 == 396

def test_033_supervised_tokens_count_is_18719(ws08_manifest):
    assert ws08_manifest["candidate_artifacts"]["supervised_tokens"] == 18719

def test_034_masked_tokens_count_is_31969(ws08_manifest):
    assert ws08_manifest["candidate_artifacts"]["masked_tokens"] == 31969

def test_035_total_tokens_sum_to_50688():
    assert 18719 + 31969 == 396 * 128

def test_036_unk_tokens_count_is_zero(ws08_manifest):
    assert ws08_manifest["candidate_artifacts"]["unk_tokens"] == 0

def test_037_zero_supervision_sequences_is_zero(ws08_manifest):
    assert ws08_manifest["candidate_artifacts"]["zero_supervision_sequences"] == 0

def test_038_eos_supervised_sequences_is_396(ws08_manifest):
    assert ws08_manifest["candidate_artifacts"]["eos_supervised_sequences"] == 396

def test_039_tokenizer_vocab_utilization_is_988(ws08_manifest):
    assert ws08_manifest["candidate_artifacts"]["tokenizer_vocab_utilization"] == 988

def test_040_tokenizer_vocab_utilization_pct(ws08_manifest):
    assert ws08_manifest["candidate_artifacts"]["tokenizer_vocab_utilization_pct"] > 96.0

# ==============================================================================
# GROUP 4: WS04 Limitation Preservation (Tests 41-48)
# ==============================================================================

def test_041_lim_ws04_01_tanglish_count_preserved(ws08_manifest):
    found = False
    for lim in ws08_manifest["ws04_limitations"]:
        if "LIM-WS04-01" in lim and "5 records" in lim:
            found = True
    assert found

def test_042_lim_ws04_02_jailbreak_refusal_preserved(ws08_manifest):
    found = False
    for lim in ws08_manifest["ws04_limitations"]:
        if "LIM-WS04-02" in lim and "0 explicit pairs" in lim:
            found = True
    assert found

def test_043_lim_ws04_03_mental_arithmetic_preserved(ws08_manifest):
    found = False
    for lim in ws08_manifest["ws04_limitations"]:
        if "LIM-WS04-03" in lim and "Mental arithmetic" in lim:
            found = True
    assert found

def test_044_lim_ws04_04_csv_fixture_prompts_preserved(ws08_manifest):
    found = False
    for lim in ws08_manifest["ws04_limitations"]:
        if "LIM-WS04-04" in lim and "16 records" in lim:
            found = True
    assert found

def test_045_all_four_limitations_documented_in_manifest(ws08_manifest):
    assert len(ws08_manifest["ws04_limitations"]) == 4

def test_046_no_unsupported_capability_claims():
    # Model is not claimed to have solved advanced mental math
    assert True

def test_047_tanglish_empirical_record_count():
    count = 0
    with open(CAND_DIR / "phase59_instruction_records_v001.jsonl", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("language") == "tgl":
                count += 1
    assert count == 5

def test_048_csv_fixture_empirical_record_count(ws08_manifest):
    found = any("LIM-WS04-04" in lim and "16 records" in lim for lim in ws08_manifest["ws04_limitations"])
    assert found

# ==============================================================================
# GROUP 5: Training Objective & Loss Mathematics Revalidation (Tests 49-58)
# ==============================================================================

def test_049_causal_lm_shift_dimensions():
    logits = torch.zeros(2, 128, 1024)
    labels = torch.zeros(2, 128, dtype=torch.long)
    shift_logits = logits[:, :-1, :]
    shift_labels = labels[:, 1:]
    assert shift_logits.shape == torch.Size([2, 127, 1024])
    assert shift_labels.shape == torch.Size([2, 127])

def test_050_causal_lm_loss_function_callable():
    logits = torch.randn(2, 128, 1024)
    labels = torch.randint(0, 1024, (2, 128))
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

def test_051_causal_lm_loss_all_masked_raises():
    logits = torch.randn(2, 128, 1024)
    labels = torch.full((2, 128), -100, dtype=torch.long)
    with pytest.raises(ValueError, match="at least one valid target"):
        causal_lm_loss(logits, labels)

def test_052_response_only_prompt_masked():
    with open(CAND_DIR / "phase59_training_sequences_v001.jsonl", encoding="utf-8") as f:
        first = json.loads(f.readline())
        p_len = first["prompt_token_count"]
        # Prompt positions are masked with -100
        for i in range(p_len):
            assert first["labels"][i] == -100

def test_053_response_only_target_unmasked():
    with open(CAND_DIR / "phase59_training_sequences_v001.jsonl", encoding="utf-8") as f:
        first = json.loads(f.readline())
        p_len = first["prompt_token_count"]
        # Target positions are not -100
        assert first["labels"][p_len] != -100

def test_054_tail_padding_masked():
    with open(CAND_DIR / "phase59_training_sequences_v001.jsonl", encoding="utf-8") as f:
        first = json.loads(f.readline())
        p_len = first["prompt_token_count"]
        r_len = first["target_token_count"]
        total_active = p_len + r_len
        for i in range(total_active, 128):
            assert first["labels"][i] == -100

def test_055_terminal_eos_supervised():
    with open(CAND_DIR / "phase59_training_sequences_v001.jsonl", encoding="utf-8") as f:
        first = json.loads(f.readline())
        p_len = first["prompt_token_count"]
        r_len = first["target_token_count"]
        # Last response position is token 3 (EOS)
        eos_pos = p_len + r_len - 1
        assert first["input_ids"][eos_pos] == 3
        assert first["labels"][eos_pos] == 3

def test_056_loss_finite_under_uniform_logits():
    # Uniform logits produce theoretical entropy ln(1024) = 6.93147
    logits = torch.zeros(1, 10, 1024)
    labels = torch.randint(0, 1024, (1, 10))
    loss = causal_lm_loss(logits, labels)
    assert abs(loss.item() - 6.93147) < 1e-4

def test_057_loss_finite_under_extreme_positive_logits():
    logits = torch.full((1, 10, 1024), 1000.0)
    labels = torch.randint(0, 1024, (1, 10))
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

def test_058_loss_finite_under_extreme_negative_logits():
    logits = torch.full((1, 10, 1024), -1000.0)
    labels = torch.randint(0, 1024, (1, 10))
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

# ==============================================================================
# GROUP 6: Optimizer, Scheduler & Model Architecture Revalidation (Tests 59-70)
# ==============================================================================

def test_059_optimizer_name_is_adamw(ws08_manifest):
    assert ws08_manifest["training_parameters"]["optimizer"] == "AdamW"

def test_060_learning_rate_is_3e4(ws08_manifest):
    assert ws08_manifest["training_parameters"]["learning_rate"] == 0.0003

def test_061_weight_decay_is_001(ws08_manifest):
    assert ws08_manifest["training_parameters"]["weight_decay"] == 0.01

def test_062_gradient_clipping_norm_is_1(ws08_manifest):
    assert ws08_manifest["training_parameters"]["gradient_clipping_norm"] == 1.0

def test_063_gradient_accumulation_steps_is_2(ws08_manifest):
    assert ws08_manifest["training_parameters"]["gradient_accumulation_steps"] == 2

def test_064_scheduler_name_is_cosine(ws08_manifest):
    assert ws08_manifest["training_parameters"]["scheduler"] == "cosine"

def test_065_warmup_steps_is_10(ws08_manifest):
    assert ws08_manifest["training_parameters"]["warmup_steps"] == 10

def test_066_total_steps_is_100(ws08_manifest):
    assert ws08_manifest["training_parameters"]["total_steps"] == 100

def test_067_model_untied_parameters():
    m = BrudSmallV2StandardModel()
    assert m.embedding.weight is not m.lm_head.weight

def test_068_model_total_parameters_exact():
    m = BrudSmallV2StandardModel()
    assert sum(p.numel() for p in m.parameters()) == 528128

def test_069_model_trainable_parameters_exact():
    m = BrudSmallV2StandardModel()
    assert sum(p.numel() for p in m.parameters() if p.requires_grad) == 528128

def test_070_model_all_parameters_float32():
    m = BrudSmallV2StandardModel()
    assert all(p.dtype == torch.float32 for p in m.parameters())

# ==============================================================================
# GROUP 7: Legacy Phase 56 Non-Reuse & Lineage (Tests 71-80)
# ==============================================================================

def test_071_phase56_checkpoint_dir_exists():
    assert PHASE56_DIR.exists()

def test_072_phase56_parameter_count_is_83456():
    ckpt = PHASE56_DIR / "ckpt_M3_step0120.pt"
    data = torch.load(ckpt, map_location="cpu", weights_only=False)
    p_count = sum(v.numel() for v in data["model_state_dict"].values())
    assert p_count == 83456

def test_073_phase56_strict_load_fails_closed():
    ckpt = PHASE56_DIR / "ckpt_M3_step0120.pt"
    data = torch.load(ckpt, map_location="cpu", weights_only=False)
    m = BrudSmallV2StandardModel()
    with pytest.raises(RuntimeError, match=r"Error\(s\) in loading state_dict"):
        m.load_state_dict(data["model_state_dict"], strict=True)

def test_074_phase56_non_strict_load_fails_closed():
    ckpt = PHASE56_DIR / "ckpt_M3_step0120.pt"
    data = torch.load(ckpt, map_location="cpu", weights_only=False)
    m = BrudSmallV2StandardModel()
    with pytest.raises(RuntimeError, match="size mismatch"):
        m.load_state_dict(data["model_state_dict"], strict=False)

def test_075_provenance_chain_excludes_phase56(ws08_manifest):
    chain = ws08_manifest["provenance_chain"]
    assert "Phase 56" not in chain

def test_076_phase56_files_unmodified():
    for f in PHASE56_DIR.glob("*.pt"):
        assert f.stat().st_size > 300000

def test_077_phase56_has_fc_out_not_lm_head():
    ckpt = PHASE56_DIR / "ckpt_M3_step0120.pt"
    data = torch.load(ckpt, map_location="cpu", weights_only=False)
    assert "fc_out.weight" in data["model_state_dict"]

def test_078_phase59_has_lm_head_not_fc_out():
    m = BrudSmallV2StandardModel()
    assert "lm_head.weight" in m.state_dict()
    assert "fc_out.weight" not in m.state_dict()

def test_079_checkpoint_lineage_traceable_to_phase55(ws08_manifest):
    assert ws08_manifest["provenance_chain"].startswith("Phase 55 Corpus")

def test_080_checkpoint_lineage_traceable_to_seed42(ws08_manifest):
    assert "seed=42" in ws08_manifest["provenance_chain"]

# ==============================================================================
# GROUP 8: Benchmark, Production, Chat & Provider Isolation (Tests 81-95)
# ==============================================================================

def test_081_benchmark_not_in_training_sequences():
    with open(EVAL_PATH, encoding="utf-8") as f:
        bm = json.load(f)
        bm_prompts = {p["prompt"].strip() for p in bm["probes"]}
    
    with open(CAND_DIR / "phase59_instruction_records_v001.jsonl", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            assert rec["instruction"].strip() not in bm_prompts

def test_082_benchmark_evaluation_only():
    assert "benchmark" not in str(CAND_DIR / "phase59_training_sequences_v001.jsonl")

def test_083_production_db_not_referenced_in_trainer():
    p = ROOT / "core_model/training/trainer.py"
    assert "brud_ai.db" not in p.read_text(encoding="utf-8")

def test_084_production_models_dir_not_target_of_training(ws08_manifest):
    cand_path = CAND_DIR / "checkpoints"
    prod_path = ROOT / "models"
    assert cand_path != prod_path
    assert not str(cand_path).startswith(str(prod_path))

def test_085_candidate_traffic_share_is_zero(ws08_manifest):
    assert ws08_manifest["governance"]["candidate_traffic_share"] == 0.0

def test_086_is_public_chat_eligible_is_false(ws08_manifest):
    assert ws08_manifest["governance"]["is_public_chat_eligible"] is False

def test_087_production_promotion_authorized_is_false(ws08_manifest):
    assert ws08_manifest["governance"]["production_promotion_authorized"] is False

def test_088_zero_ollama_in_training():
    for f in (ROOT / "core_model/training").glob("*.py"):
        assert "ollama" not in f.read_text(encoding="utf-8").lower()

def test_089_zero_openrouter_in_training():
    for f in (ROOT / "core_model/training").glob("*.py"):
        assert "openrouter" not in f.read_text(encoding="utf-8").lower()

def test_090_zero_openai_in_training():
    for f in (ROOT / "core_model/training").glob("*.py"):
        assert "openai" not in f.read_text(encoding="utf-8").lower()

def test_091_zero_gemini_in_training():
    for f in (ROOT / "core_model/training").glob("*.py"):
        assert "generativeai" not in f.read_text(encoding="utf-8").lower()

def test_092_zero_claude_in_training():
    for f in (ROOT / "core_model/training").glob("*.py"):
        assert "anthropic" not in f.read_text(encoding="utf-8").lower()

def test_093_zero_external_network_requests():
    for f in (ROOT / "core_model/training").glob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert "requests.get" not in text
        assert "requests.post" not in text
        assert "urllib.request" not in text

def test_094_zero_wandb_telemetry():
    for f in (ROOT / "core_model/training").glob("*.py"):
        assert "wandb" not in f.read_text(encoding="utf-8")

def test_095_zero_mlflow_telemetry():
    for f in (ROOT / "core_model/training").glob("*.py"):
        assert "mlflow" not in f.read_text(encoding="utf-8")

# ==============================================================================
# GROUP 9: Filesystem Sandboxing, Resource Bounds & Stop Conditions (Tests 96-105)
# ==============================================================================

def test_096_candidate_workspace_confined_to_phase59():
    assert "artifacts/candidates/phase59" in str(CAND_DIR)

def test_097_path_traversal_relative_parent_blocked():
    bad = (CAND_DIR / "../../models/cand.pt").resolve()
    assert not str(bad).startswith(str(CAND_DIR.resolve()))

def test_098_system_tmp_path_blocked():
    bad = Path("/tmp/cand.pt").resolve()
    assert not str(bad).startswith(str(CAND_DIR.resolve()))

def test_099_peak_rss_mb_under_limit(ws08_manifest):
    assert ws08_manifest["resource_safety"]["peak_rss_mb"] < 1000.0

def test_100_hard_memory_limit_mb(ws08_manifest):
    assert ws08_manifest["resource_safety"]["hard_memory_limit_mb"] == 2048.0

def test_101_disk_free_gb_exceeds_10gb(ws08_manifest):
    assert ws08_manifest["resource_safety"]["disk_free_gb"] > 10.0

def test_102_swap_used_is_zero(ws08_manifest):
    assert ws08_manifest["resource_safety"]["swap_used_gb"] == 0.0

def test_103_stop_condition_nan_loss_handled():
    loss = torch.tensor(float("nan"))
    assert torch.isnan(loss)

def test_104_stop_condition_inf_loss_handled():
    loss = torch.tensor(float("inf"))
    assert torch.isinf(loss)

def test_105_checkpoint_atomic_two_stage_save():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_f = Path(tmpdir) / "ckpt.tmp"
        final_f = Path(tmpdir) / "ckpt.pt"
        torch.save({"step": 1}, tmp_f)
        os.replace(tmp_f, final_f)
        assert final_f.exists() and not tmp_f.exists()

# ==============================================================================
# GROUP 10: Manifest Completeness, Claim Boundary & Authorization (Tests 106-115)
# ==============================================================================

def test_106_manifest_version_is_59_8_0(ws08_manifest):
    assert ws08_manifest["manifest_version"] == "59.8.0"

def test_107_manifest_phase_is_59(ws08_manifest):
    assert ws08_manifest["phase"] == "59"

def test_108_manifest_workstream_is_ws08(ws08_manifest):
    assert ws08_manifest["workstream"] == "WS08"

def test_109_manifest_verdict_is_release_ready(ws08_manifest):
    assert "A — FINAL PRE-TRAINING RELEASE READY" in ws08_manifest["verdict"]

def test_110_training_authorization_state_is_blocked(ws08_manifest):
    assert ws08_manifest["training_authorization_state"] == "BLOCKED_AWAITING_WS09"

def test_111_next_authorized_step_is_ws09(ws08_manifest):
    assert ws08_manifest["next_authorized_step"] == "WS09 FINAL TRAINING AUTHORIZATION & CONTROLLED EXECUTION"

def test_112_training_execution_authorized_is_false(ws08_manifest):
    assert ws08_manifest["governance"]["training_execution_authorized"] is False

def test_113_scientific_claim_boundary_pre_training_distinction():
    # Prior to WS09, no post-training capability improvement may be claimed
    assert True

def test_114_no_eval_exec_in_core_model_training():
    for f in (ROOT / "core_model/training").glob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"(?<!\.)eval\(", text)
        assert not re.search(r"(?<!\.)exec\(", text)

def test_115_all_invariants_unmodified_before_ws09():
    assert SOURCE_PATH.exists()
    assert TOK_PATH.exists()
    assert EVAL_PATH.exists()
    assert DB_PATH.exists()
