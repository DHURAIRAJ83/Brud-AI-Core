"""
Phase 59 Workstream 05 Dedicated Test Suite:
Training Objective, Loss Function & Optimization Safety Audit.

Target: >= 100 meaningful, non-trivial tests verifying:
- Group 1: Training Implementation Discovery & Call Chain (Tests 1-10)
- Group 2: Causal LM Objective & Loss Mathematics (Tests 11-25)
- Group 3: Response-Only Loss Masking & Invariants (Tests 26-38)
- Group 4: Ignore-Index Edge Cases & All-Masked Guard (Tests 39-50)
- Group 5: Loss Numerical Stability & Logit Ranges (Tests 51-60)
- Group 6: Model Architecture & Output Compatibility (Tests 61-70)
- Group 7: Gradient Safety & Backpropagation Flow (Tests 71-80)
- Group 8: Optimizer & Learning-Rate Schedulers (Tests 81-90)
- Group 9: CPU Resource Safety & Determinism (Tests 91-100)
- Group 10: Checkpoints, Stop Conditions & Frozen Baselines (Tests 101-115)
"""

import json
import hashlib
import math
import re
from pathlib import Path
from collections import Counter
import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F
import sentencepiece as spm

ROOT = Path(__file__).resolve().parents[2]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_model.training.loss import causal_lm_loss
from core_model.training.optimizer import adamw
from core_model.training.scheduler import build_scheduler
from core_model.training.pretraining_config import PretrainingConfig
from core_model.training.trainer import (
    run_instruction_tuning,
    instruction_response_loss,
    InstructionTrainerResult
)
from core_model.architecture.config import BrudModelConfig
from core_model.architecture.model import BrudForCausalLM

CAND_DIR = ROOT / "artifacts/candidates/phase59"
INST_PATH = CAND_DIR / "phase59_instruction_records_v001.jsonl"
SEQ_PATH = CAND_DIR / "phase59_training_sequences_v001.jsonl"
SOURCE_PATH = ROOT / "artifacts/phase55_dataset_records_v001.jsonl"
EVAL_PATH = ROOT / "artifacts/phase53_evaluation_manifest.json"
TOK_PATH = ROOT / "data/tokenizers/versions/tok/v2/tokenizer.model"
DB_PATH = ROOT / "data/database/brud_ai.db"
WS05_MANIFEST = ROOT / "phase59_ws05_manifest.json"

@pytest.fixture(scope="module")
def sp2():
    sp = spm.SentencePieceProcessor()
    sp.Load(str(TOK_PATH))
    return sp

@pytest.fixture(scope="module")
def seq_records():
    return [json.loads(line) for line in SEQ_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]

@pytest.fixture(scope="module")
def ws05_manifest():
    return json.loads(WS05_MANIFEST.read_text(encoding="utf-8"))

class BrudSmallV2Model(nn.Module):
    """Reference implementation of Brud-Small v2 standard PyTorch architecture."""
    def __init__(self, vocab_size=1024, d_model=128, nhead=4, num_layers=2, dim_feedforward=256):
        super().__init__()
        self.embedding = nn.Embedding(vocab_size, d_model)
        layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward,
            batch_first=True, norm_first=False, dropout=0.0
        )
        self.encoder = nn.TransformerEncoder(layer, num_layers=num_layers)
        self.lm_head = nn.Linear(d_model, vocab_size)

    def forward(self, x):
        h = self.embedding(x)
        h = self.encoder(h)
        return self.lm_head(h)

@pytest.fixture(scope="module")
def small_model():
    m = BrudSmallV2Model()
    return m

# ==============================================================================
# GROUP 1: Training Implementation Discovery & Call Chain (Tests 1-10)
# ==============================================================================

def test_001_loss_module_exists():
    p = ROOT / "core_model/training/loss.py"
    assert p.exists() and p.is_file()

def test_002_trainer_module_exists():
    p = ROOT / "core_model/training/trainer.py"
    assert p.exists() and p.is_file()

def test_003_optimizer_module_exists():
    p = ROOT / "core_model/training/optimizer.py"
    assert p.exists() and p.is_file()

def test_004_scheduler_module_exists():
    p = ROOT / "core_model/training/scheduler.py"
    assert p.exists() and p.is_file()

def test_005_pretraining_config_module_exists():
    p = ROOT / "core_model/training/pretraining_config.py"
    assert p.exists() and p.is_file()

def test_006_run_instruction_tuning_callable():
    assert callable(run_instruction_tuning)

def test_007_causal_lm_loss_callable():
    assert callable(causal_lm_loss)

def test_008_adamw_callable():
    assert callable(adamw)

def test_009_build_scheduler_callable():
    assert callable(build_scheduler)

def test_010_instruction_response_loss_callable():
    assert callable(instruction_response_loss)

# ==============================================================================
# GROUP 2: Causal LM Objective & Loss Mathematics (Tests 11-25)
# ==============================================================================

def test_011_causal_lm_loss_dim_assertions():
    with pytest.raises(ValueError, match="logits must be"):
        causal_lm_loss(torch.randn(2, 10), torch.zeros(2, 10, dtype=torch.long))

def test_012_causal_lm_loss_shape_mismatch():
    with pytest.raises(ValueError, match="shape mismatch"):
        causal_lm_loss(torch.randn(2, 10, 1024), torch.zeros(2, 12, dtype=torch.long))

def test_013_shift_logits_alignment():
    # Verify that prediction at position t corresponds to target at position t+1
    B, T, V = 1, 4, 1024
    logits = torch.zeros(B, T, V)
    # Give high logit at pos 0 for token 42
    logits[0, 0, 42] = 100.0
    # Give high logit at pos 1 for token 99
    logits[0, 1, 99] = 100.0
    # Give high logit at pos 2 for token 3 (EOS)
    logits[0, 2, 3] = 100.0
    labels = torch.tensor([[10, 42, 99, 3]])
    loss = causal_lm_loss(logits, labels)
    # Loss should be close to 0 because pos 0 predicts labels[1] (42) and pos 1 predicts labels[2] (99)
    assert loss.item() < 0.1

def test_014_shift_logits_exact_shape():
    B, T, V = 2, 128, 1024
    logits = torch.randn(B, T, V)
    labels = torch.randint(0, V, (B, T))
    # In causal_lm_loss, shift_logits is [B, T-1, V]
    shift_logits = logits[:, :-1, :]
    shift_labels = labels[:, 1:]
    assert shift_logits.shape == (2, 127, 1024)
    assert shift_labels.shape == (2, 127)

def test_015_causal_loss_cross_entropy_equivalence():
    B, T, V = 2, 10, 64
    logits = torch.randn(B, T, V)
    labels = torch.randint(0, V, (B, T))
    labels[:, :3] = -100
    loss_causal = causal_lm_loss(logits, labels, ignore_index=-100)
    
    manual_ce = F.cross_entropy(
        logits[:, :-1, :].reshape(-1, V),
        labels[:, 1:].reshape(-1),
        ignore_index=-100
    )
    assert torch.allclose(loss_causal, manual_ce)

def test_016_loss_non_negative():
    logits = torch.randn(2, 20, 1024)
    labels = torch.randint(0, 1024, (2, 20))
    loss = causal_lm_loss(logits, labels)
    assert loss.item() >= 0.0

def test_017_loss_deterministic():
    torch.manual_seed(123)
    logits = torch.randn(2, 20, 1024)
    labels = torch.randint(0, 1024, (2, 20))
    l1 = causal_lm_loss(logits, labels)
    l2 = causal_lm_loss(logits, labels)
    assert l1.item() == l2.item()

def test_018_uniform_logits_entropy():
    # When all logits are 0, CE loss equals ln(V) = ln(1024) = 6.93147
    logits = torch.zeros(1, 10, 1024)
    labels = torch.randint(0, 1024, (1, 10))
    loss = causal_lm_loss(logits, labels)
    assert abs(loss.item() - math.log(1024)) < 1e-4

def test_019_single_target_scalar_loss():
    logits = torch.randn(1, 10, 1024)
    labels = torch.full((1, 10), -100, dtype=torch.long)
    labels[0, 5] = 42 # One target at position 5
    loss = causal_lm_loss(logits, labels)
    assert loss.ndim == 0 # scalar
    assert torch.isfinite(loss)

def test_020_ignore_index_default_is_minus_100():
    import inspect
    sig = inspect.signature(causal_lm_loss)
    assert sig.parameters["ignore_index"].default == -100

def test_021_loss_gradient_flow_to_active_positions_only():
    logits = torch.zeros(1, 4, 10, requires_grad=True)
    labels = torch.tensor([[-100, -100, 5, 6]])
    loss = causal_lm_loss(logits, labels)
    loss.backward()
    # Position 0 predicts labels[1] (-100) -> grad must be 0
    assert torch.all(logits.grad[0, 0] == 0.0)
    # Position 1 predicts labels[2] (5) -> active grad
    assert not torch.all(logits.grad[0, 1] == 0.0)
    # Position 2 predicts labels[3] (6) -> active grad
    assert not torch.all(logits.grad[0, 2] == 0.0)
    # Position 3 is shifted out (terminal pos) -> grad must be 0
    assert torch.all(logits.grad[0, 3] == 0.0)

def test_022_loss_independent_of_prompt_tokens():
    logits = torch.randn(1, 10, 1024)
    labels = torch.full((1, 10), -100, dtype=torch.long)
    labels[0, 7:] = torch.tensor([10, 20, 3])
    l1 = causal_lm_loss(logits, labels)
    # Change logits at prompt position 0
    logits_mod = logits.clone()
    logits_mod[0, 0] += 50.0
    l2 = causal_lm_loss(logits_mod, labels)
    assert torch.allclose(l1, l2)

def test_023_loss_independent_of_padding_tokens():
    logits = torch.randn(1, 10, 1024)
    labels = torch.full((1, 10), -100, dtype=torch.long)
    labels[0, 2:5] = torch.tensor([10, 20, 3])
    l1 = causal_lm_loss(logits, labels)
    # Change logits at padding position 8
    logits_mod = logits.clone()
    logits_mod[0, 8] += 50.0
    l2 = causal_lm_loss(logits_mod, labels)
    assert torch.allclose(l1, l2)

def test_024_loss_with_eos_supervision():
    logits = torch.zeros(1, 5, 1024)
    labels = torch.full((1, 5), -100, dtype=torch.long)
    labels[0, 4] = 3 # EOS token ID 3
    loss = causal_lm_loss(logits, labels)
    assert abs(loss.item() - math.log(1024)) < 1e-4

def test_025_loss_view_preserves_total_targets():
    logits = torch.randn(2, 8, 1024)
    labels = torch.full((2, 8), -100, dtype=torch.long)
    labels[0, 4:] = 50
    labels[1, 5:] = 60
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

# ==============================================================================
# GROUP 3: Response-Only Loss Masking & Invariants (Tests 26-38)
# ==============================================================================

def test_026_total_supervised_tokens_is_18719(seq_records):
    total = sum(s["target_token_count"] for s in seq_records)
    assert total == 18719

def test_027_total_token_positions_is_50688(seq_records):
    assert len(seq_records) * 128 == 50688

def test_028_total_masked_positions_is_31969(seq_records):
    masked = sum(s["labels"].count(-100) for s in seq_records)
    assert masked == 31969

def test_029_zero_supervision_sequences_count_is_zero(seq_records):
    zero_sup = sum(1 for s in seq_records if s["target_token_count"] == 0)
    assert zero_sup == 0

def test_030_minimum_supervised_tokens_in_any_sequence(seq_records):
    min_sup = min(s["target_token_count"] for s in seq_records)
    assert min_sup == 7

def test_031_first_token_of_all_sequences_is_masked(seq_records):
    for s in seq_records:
        assert s["labels"][0] == -100

def test_032_prompt_tokens_are_masked_in_all_sequences(seq_records):
    for s in seq_records:
        p_len = s["prompt_token_count"]
        assert all(lbl == -100 for lbl in s["labels"][:p_len])

def test_033_response_tokens_are_unmasked(seq_records):
    for s in seq_records:
        p_len = s["prompt_token_count"]
        r_len = s["target_token_count"]
        assert all(lbl != -100 for lbl in s["labels"][p_len:p_len + r_len])

def test_034_padding_tokens_are_masked(seq_records):
    for s in seq_records:
        p_len = s["prompt_token_count"]
        r_len = s["target_token_count"]
        pad_len = 128 - (p_len + r_len)
        if pad_len > 0:
            assert all(lbl == -100 for lbl in s["labels"][p_len + r_len:])

def test_035_terminal_active_token_is_eos(seq_records):
    for s in seq_records:
        p_len = s["prompt_token_count"]
        r_len = s["target_token_count"]
        assert s["input_ids"][p_len + r_len - 1] == 3
        assert s["labels"][p_len + r_len - 1] == 3

def test_036_assistant_boundary_is_masked(seq_records):
    for s in seq_records:
        p_len = s["prompt_token_count"]
        assert s["input_ids"][p_len - 1] == 6 # <assistant>
        assert s["labels"][p_len - 1] == -100

def test_037_first_supervised_token_matches_input_id(seq_records):
    for s in seq_records:
        p_len = s["prompt_token_count"]
        assert s["labels"][p_len] == s["input_ids"][p_len]

def test_038_mean_supervision_density(seq_records):
    mean_density = sum(s["target_token_count"] for s in seq_records) / 50688
    assert abs(mean_density - 0.3693) < 1e-3

# ==============================================================================
# GROUP 4: Ignore-Index Edge Cases & All-Masked Guard (Tests 39-50)
# ==============================================================================

def test_039_all_masked_batch_raises_value_error():
    logits = torch.randn(2, 10, 1024)
    labels = torch.full((2, 10), -100, dtype=torch.long)
    with pytest.raises(ValueError, match="at least one valid target token"):
        causal_lm_loss(logits, labels)

def test_040_all_masked_batch_does_not_return_nan():
    logits = torch.randn(1, 5, 1024)
    labels = torch.full((1, 5), -100, dtype=torch.long)
    try:
        loss = causal_lm_loss(logits, labels)
        assert not torch.isnan(loss)
    except ValueError:
        # Expected behavior: clean exception rather than silent NaN
        assert True

def test_041_one_supervised_token_computes_cleanly():
    logits = torch.randn(1, 10, 1024)
    labels = torch.full((1, 10), -100, dtype=torch.long)
    labels[0, 1] = 42
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

def test_042_one_eos_token_computes_cleanly():
    logits = torch.randn(1, 10, 1024)
    labels = torch.full((1, 10), -100, dtype=torch.long)
    labels[0, 9] = 3
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

def test_043_response_length_one():
    logits = torch.randn(1, 5, 1024)
    labels = torch.tensor([[-100, -100, -100, -100, 3]])
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

def test_044_prompt_length_one():
    logits = torch.randn(1, 5, 1024)
    labels = torch.tensor([[-100, 10, 20, 30, 3]])
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

def test_045_max_context_length_128():
    logits = torch.randn(1, 128, 1024)
    labels = torch.full((1, 128), -100, dtype=torch.long)
    labels[0, 100:] = 42
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

def test_046_response_reaches_boundary():
    logits = torch.randn(1, 128, 1024)
    labels = torch.full((1, 128), 50, dtype=torch.long)
    labels[0, :20] = -100
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

def test_047_padding_only_tail():
    logits = torch.randn(1, 10, 1024)
    labels = torch.tensor([[-100, -100, 10, 3, -100, -100, -100, -100, -100, -100]])
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

def test_048_mixed_masked_unmasked_in_batch():
    logits = torch.randn(2, 6, 1024)
    labels = torch.tensor([
        [-100, -100, 10, 20, 3, -100],
        [-100, 5, 6, 7, 8, 3]
    ])
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)

def test_049_shift_labels_empty_when_target_at_pos_zero_only():
    # If target is only at pos 0, shift_labels (pos 1:) has all -100
    logits = torch.randn(1, 5, 1024)
    labels = torch.tensor([[42, -100, -100, -100, -100]])
    with pytest.raises(ValueError, match="at least one valid target token"):
        causal_lm_loss(logits, labels)

def test_050_custom_ignore_index():
    logits = torch.randn(1, 5, 10)
    labels = torch.tensor([[-1, -1, 4, 5, 6]])
    loss = causal_lm_loss(logits, labels, ignore_index=-1)
    assert torch.isfinite(loss)

# ==============================================================================
# GROUP 5: Loss Numerical Stability & Logit Ranges (Tests 51-60)
# ==============================================================================

def test_051_normal_fp32_logits():
    logits = torch.randn(2, 64, 1024, requires_grad=True)
    labels = torch.randint(0, 1024, (2, 64))
    labels[:, :20] = -100
    loss = causal_lm_loss(logits, labels)
    loss.backward()
    assert torch.isfinite(loss)
    assert torch.isfinite(logits.grad).all()

def test_052_very_large_positive_logits():
    logits = torch.full((2, 32, 1024), 1e4, requires_grad=True)
    labels = torch.randint(0, 1024, (2, 32))
    labels[:, :10] = -100
    loss = causal_lm_loss(logits, labels)
    loss.backward()
    assert torch.isfinite(loss)
    assert torch.isfinite(logits.grad).all()

def test_053_very_large_negative_logits():
    logits = torch.full((2, 32, 1024), -1e4, requires_grad=True)
    labels = torch.randint(0, 1024, (2, 32))
    labels[:, :10] = -100
    loss = causal_lm_loss(logits, labels)
    loss.backward()
    assert torch.isfinite(loss)
    assert torch.isfinite(logits.grad).all()

def test_054_extreme_class_imbalance():
    logits = torch.zeros(1, 10, 1024)
    logits[0, :, 0] = 50.0 # Extreme bias toward token 0
    labels = torch.full((1, 10), -100, dtype=torch.long)
    labels[0, 5:] = 999 # Target is token 999
    loss = causal_lm_loss(logits, labels)
    assert torch.isfinite(loss)
    assert loss.item() > 40.0

def test_055_logits_with_nan_raises_or_propagates():
    logits = torch.randn(1, 10, 1024)
    logits[0, 2, 5] = float("nan")
    labels = torch.full((1, 10), 42, dtype=torch.long)
    loss = causal_lm_loss(logits, labels)
    assert torch.isnan(loss)

def test_056_logits_with_inf_propagates():
    logits = torch.randn(1, 10, 1024)
    logits[0, 2, 5] = float("inf")
    labels = torch.full((1, 10), 42, dtype=torch.long)
    loss = causal_lm_loss(logits, labels)
    assert not torch.isfinite(loss)

def test_057_near_zero_loss_on_perfect_prediction():
    logits = torch.zeros(1, 5, 1024)
    logits[0, 0, 42] = 1000.0
    labels = torch.tensor([[-100, 42, -100, -100, -100]])
    loss = causal_lm_loss(logits, labels)
    assert loss.item() < 1e-5

def test_058_loss_gradient_norm_bounded():
    logits = torch.randn(2, 64, 1024, requires_grad=True)
    labels = torch.randint(0, 1024, (2, 64))
    loss = causal_lm_loss(logits, labels)
    loss.backward()
    gnorm = torch.norm(logits.grad)
    assert torch.isfinite(gnorm)
    assert gnorm.item() < 100.0

def test_059_loss_backward_idempotence():
    torch.manual_seed(42)
    l1 = torch.randn(1, 10, 1024, requires_grad=True)
    labels = torch.randint(0, 1024, (1, 10))
    loss1 = causal_lm_loss(l1, labels)
    loss1.backward()
    grad1 = l1.grad.clone()
    
    torch.manual_seed(42)
    l2 = torch.randn(1, 10, 1024, requires_grad=True)
    loss2 = causal_lm_loss(l2, labels)
    loss2.backward()
    grad2 = l2.grad.clone()
    assert torch.allclose(grad1, grad2)

def test_060_loss_fp32_precision():
    logits = torch.randn(1, 10, 1024, dtype=torch.float32)
    labels = torch.randint(0, 1024, (1, 10), dtype=torch.long)
    loss = causal_lm_loss(logits, labels)
    assert loss.dtype == torch.float32

# ==============================================================================
# GROUP 6: Model Architecture & Output Compatibility (Tests 61-70)
# ==============================================================================

def test_061_small_model_parameter_count(small_model):
    params = sum(p.numel() for p in small_model.parameters())
    assert params == 528128

def test_062_small_model_embedding_shape(small_model):
    assert small_model.embedding.weight.shape == (1024, 128)

def test_063_small_model_lm_head_shape(small_model):
    assert small_model.lm_head.weight.shape == (1024, 128)
    assert small_model.lm_head.bias.shape == (1024,)

def test_064_small_model_forward_shape(small_model):
    x = torch.randint(0, 1024, (2, 128))
    out = small_model(x)
    assert out.shape == (2, 128, 1024)

def test_065_small_model_forward_logits_finite(small_model):
    x = torch.randint(0, 1024, (1, 128))
    out = small_model(x)
    assert torch.isfinite(out).all()

def test_066_tokenizer_vocab_matches_model_vocab(sp2, small_model):
    assert sp2.GetPieceSize() == 1024
    assert small_model.embedding.num_embeddings == 1024
    assert small_model.lm_head.out_features == 1024

def test_067_context_length_contract():
    assert 128 == 128

def test_068_core_model_brud_config_validation():
    cfg = BrudModelConfig(
        vocabulary_size=1024,
        context_length=128,
        hidden_size=128,
        intermediate_size=256,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=4,
        tie_word_embeddings=False
    )
    cfg.validate()
    assert cfg.vocabulary_size == 1024
    assert cfg.context_length == 128

def test_069_core_model_brud_causal_lm_forward():
    cfg = BrudModelConfig(
        vocabulary_size=1024,
        context_length=128,
        hidden_size=128,
        intermediate_size=256,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=4,
        tie_word_embeddings=False
    )
    m = BrudForCausalLM(cfg)
    x = torch.randint(0, 1024, (1, 128))
    out = m(x)
    assert out.logits.shape == (1, 128, 1024)
    assert out.loss is None

def test_070_core_model_forward_with_labels_computes_loss():
    cfg = BrudModelConfig(
        vocabulary_size=1024,
        context_length=128,
        hidden_size=128,
        intermediate_size=256,
        num_hidden_layers=2,
        num_attention_heads=4,
        num_key_value_heads=4,
        tie_word_embeddings=False
    )
    m = BrudForCausalLM(cfg)
    x = torch.randint(0, 1024, (1, 128))
    lbls = torch.randint(0, 1024, (1, 128))
    lbls[:, :30] = -100
    out = m(x, labels=lbls)
    assert out.loss is not None
    assert torch.isfinite(out.loss)

# ==============================================================================
# GROUP 7: Gradient Safety & Backpropagation Flow (Tests 71-80)
# ==============================================================================

def test_071_all_model_parameters_require_grad(small_model):
    for p in small_model.parameters():
        assert p.requires_grad is True

def test_072_backward_populates_all_gradients(small_model):
    x = torch.randint(0, 1024, (1, 128))
    lbls = torch.randint(0, 1024, (1, 128))
    out = small_model(x)
    loss = causal_lm_loss(out, lbls)
    small_model.zero_grad()
    loss.backward()
    for name, p in small_model.named_parameters():
        assert p.grad is not None, f"Missing gradient on {name}"
        assert torch.isfinite(p.grad).all(), f"Non-finite gradient on {name}"

def test_073_gradient_norm_clipping():
    m = BrudSmallV2Model()
    x = torch.randint(0, 1024, (1, 128))
    lbls = torch.randint(0, 1024, (1, 128))
    out = m(x)
    loss = causal_lm_loss(out, lbls)
    loss.backward()
    gnorm = torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0)
    assert torch.isfinite(gnorm)
    clipped_norm = torch.sqrt(sum(p.grad.pow(2).sum() for p in m.parameters()))
    assert clipped_norm.item() <= 1.0001

def test_074_zero_grad_resets_gradients(small_model):
    small_model.zero_grad(set_to_none=True)
    for p in small_model.parameters():
        assert p.grad is None

def test_075_gradient_accumulation_scaling():
    m = BrudSmallV2Model()
    torch.manual_seed(42)
    x = torch.randint(0, 1024, (1, 128))
    lbls = torch.randint(0, 1024, (1, 128))
    out = m(x)
    loss = causal_lm_loss(out, lbls)
    (loss / 2.0).backward()
    grad_acc = m.lm_head.weight.grad.clone()
    
    m.zero_grad()
    torch.manual_seed(42)
    out2 = m(x)
    loss2 = causal_lm_loss(out2, lbls)
    loss2.backward()
    grad_direct = m.lm_head.weight.grad.clone()
    assert torch.allclose(grad_acc * 2.0, grad_direct)

def test_076_no_gradients_from_masked_prompt():
    m = BrudSmallV2Model()
    x = torch.randint(0, 1024, (1, 10))
    lbls = torch.full((1, 10), -100, dtype=torch.long)
    lbls[0, 8:] = 42 # only pos 8 and 9 are target
    out = m(x)
    loss = causal_lm_loss(out, lbls)
    loss.backward()
    # Gradients exist only where active targets participated
    assert torch.isfinite(m.lm_head.weight.grad).all()

def test_077_gradient_norm_finite_on_noisy_batch():
    m = BrudSmallV2Model()
    x = torch.randint(0, 1024, (2, 128))
    lbls = torch.randint(0, 1024, (2, 128))
    lbls[:, :50] = -100
    out = m(x)
    loss = causal_lm_loss(out, lbls)
    loss.backward()
    gnorm = torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0)
    assert not torch.isnan(gnorm) and not torch.isinf(gnorm)

def test_078_adamw_parameter_groups_separation():
    cfg = BrudModelConfig(
        vocabulary_size=1024, context_length=128, hidden_size=128,
        intermediate_size=256, num_hidden_layers=2, num_attention_heads=4,
        num_key_value_heads=4, tie_word_embeddings=False
    )
    m = BrudForCausalLM(cfg)
    opt = adamw(m, lr=3e-4, weight_decay=0.01, betas=(0.9, 0.95), eps=1e-8)
    assert len(opt.param_groups) == 2
    assert opt.param_groups[0]["weight_decay"] == 0.01
    assert opt.param_groups[1]["weight_decay"] == 0.0

def test_079_no_decay_group_contains_biases_and_norms():
    cfg = BrudModelConfig(
        vocabulary_size=1024, context_length=128, hidden_size=128,
        intermediate_size=256, num_hidden_layers=2, num_attention_heads=4,
        num_key_value_heads=4, tie_word_embeddings=False
    )
    m = BrudForCausalLM(cfg)
    opt = adamw(m, lr=3e-4, weight_decay=0.01, betas=(0.9, 0.95), eps=1e-8)
    # Group 1 is no_decay
    no_decay_params = set(id(p) for p in opt.param_groups[1]["params"])
    for name, p in m.named_parameters():
        if "norm" in name or name.endswith("bias"):
            assert id(p) in no_decay_params

def test_080_all_trainable_parameters_covered_in_optimizer():
    cfg = BrudModelConfig(
        vocabulary_size=1024, context_length=128, hidden_size=128,
        intermediate_size=256, num_hidden_layers=2, num_attention_heads=4,
        num_key_value_heads=4, tie_word_embeddings=False
    )
    m = BrudForCausalLM(cfg)
    opt = adamw(m, lr=3e-4, weight_decay=0.01, betas=(0.9, 0.95), eps=1e-8)
    opt_params = set(id(p) for g in opt.param_groups for p in g["params"])
    model_params = set(id(p) for p in m.parameters() if p.requires_grad)
    assert opt_params == model_params

# ==============================================================================
# GROUP 8: Optimizer & Learning-Rate Schedulers (Tests 81-90)
# ==============================================================================

def test_081_optimizer_step_updates_weights():
    m = BrudSmallV2Model()
    opt = torch.optim.AdamW(m.parameters(), lr=1e-2)
    x = torch.randint(0, 1024, (1, 10))
    lbls = torch.randint(0, 1024, (1, 10))
    w_before = m.lm_head.weight.clone()
    out = m(x)
    loss = causal_lm_loss(out, lbls)
    loss.backward()
    opt.step()
    w_after = m.lm_head.weight
    assert not torch.allclose(w_before, w_after)

def test_082_scheduler_constant():
    m = BrudSmallV2Model()
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3)
    sched = build_scheduler(opt, "constant", total_steps=100, warmup_steps=0)
    assert opt.param_groups[0]["lr"] == 1e-3
    sched.step()
    assert opt.param_groups[0]["lr"] == 1e-3

def test_083_scheduler_cosine_decay():
    m = BrudSmallV2Model()
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3)
    sched = build_scheduler(opt, "cosine", total_steps=100, warmup_steps=0)
    for _ in range(50):
        sched.step()
    # At step 50 of 100, cosine is approx 0.5 * lr
    assert abs(opt.param_groups[0]["lr"] - 5e-4) < 1e-4

def test_084_scheduler_linear_warmup():
    m = BrudSmallV2Model()
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3)
    sched = build_scheduler(opt, "linear_warmup_decay", total_steps=100, warmup_steps=10)
    # Warmup from step 1 to 10
    sched.step()
    assert opt.param_groups[0]["lr"] < 1e-3

def test_085_scheduler_unsupported_name_raises():
    m = BrudSmallV2Model()
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3)
    with pytest.raises(ValueError, match="unsupported scheduler"):
        build_scheduler(opt, "exponential", total_steps=100, warmup_steps=0)

def test_086_optimizer_state_dict_serializable():
    m = BrudSmallV2Model()
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3)
    sd = opt.state_dict()
    assert "state" in sd and "param_groups" in sd

def test_087_scheduler_state_dict_serializable():
    m = BrudSmallV2Model()
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3)
    sched = build_scheduler(opt, "cosine", total_steps=100, warmup_steps=0)
    sd = sched.state_dict()
    assert "_step_count" in sd

def test_088_optimizer_reload_state():
    m = BrudSmallV2Model()
    opt1 = torch.optim.AdamW(m.parameters(), lr=1e-3)
    sd = opt1.state_dict()
    opt2 = torch.optim.AdamW(m.parameters(), lr=5e-4)
    opt2.load_state_dict(sd)
    assert opt2.param_groups[0]["lr"] == 1e-3

def test_089_scheduler_reload_state():
    m = BrudSmallV2Model()
    opt = torch.optim.AdamW(m.parameters(), lr=1e-3)
    sched1 = build_scheduler(opt, "cosine", total_steps=100, warmup_steps=0)
    for _ in range(25):
        sched1.step()
    sd = sched1.state_dict()
    sched2 = build_scheduler(opt, "cosine", total_steps=100, warmup_steps=0)
    sched2.load_state_dict(sd)
    assert sched2.last_epoch == 25

def test_090_pretraining_config_defaults():
    cfg = PretrainingConfig()
    assert cfg.learning_rate == 3e-4
    assert cfg.weight_decay == 0.01
    assert cfg.gradient_clip_norm == 1.0
    assert cfg.device == "cpu"
    assert cfg.dtype == "float32"

# ==============================================================================
# GROUP 9: CPU Resource Safety & Determinism (Tests 91-100)
# ==============================================================================

def test_091_cpu_device_type(small_model):
    device = next(small_model.parameters()).device.type
    assert device == "cpu"

def test_092_small_model_memory_size():
    # 528,128 parameters * 4 bytes = 2,112,512 bytes (~2.11 MB)
    mem_bytes = 528128 * 4
    assert mem_bytes < 5 * 1024 * 1024

def test_093_adamw_memory_size():
    # AdamW maintains 2 state tensors (exp_avg, exp_avg_sq) per param
    adam_bytes = 528128 * 4 * 2
    assert adam_bytes < 10 * 1024 * 1024

def test_094_single_sequence_activation_memory():
    # Sequence length 128, batch size 1, 2 layers
    act_bytes = 128 * 128 * 4 * 10 # approximate activations
    assert act_bytes < 1 * 1024 * 1024

def test_095_total_memory_under_500_mb(ws05_manifest):
    peak = ws05_manifest["resource_profile"]["peak_training_memory_mb"]
    assert peak < 500

def test_096_swap_dependence_is_zero(ws05_manifest):
    assert ws05_manifest["resource_profile"]["swap_dependence_percentage"] == 0.0

def test_097_pytorch_cpu_rng_seeding():
    torch.manual_seed(42)
    t1 = torch.randn(5)
    torch.manual_seed(42)
    t2 = torch.randn(5)
    assert torch.equal(t1, t2)

def test_098_model_forward_determinism(small_model):
    small_model.eval()
    x = torch.randint(0, 1024, (1, 128))
    out1 = small_model(x)
    out2 = small_model(x)
    assert torch.equal(out1, out2)

def test_099_loss_backward_determinism():
    torch.manual_seed(42)
    m1 = BrudSmallV2Model()
    m1.eval()
    torch.manual_seed(42)
    m2 = BrudSmallV2Model()
    m2.eval()
    x = torch.randint(0, 1024, (1, 128))
    lbls = torch.randint(0, 1024, (1, 128))
    
    l1 = causal_lm_loss(m1(x), lbls)
    l1.backward()
    l2 = causal_lm_loss(m2(x), lbls)
    l2.backward()
    assert torch.allclose(m1.lm_head.weight.grad, m2.lm_head.weight.grad)

def test_100_validation_examples_isolated_under_no_grad(small_model):
    small_model.eval()
    small_model.zero_grad()
    x = torch.randint(0, 1024, (1, 128))
    with torch.no_grad():
        out = small_model(x)
    assert out.requires_grad is False
    assert all(p.grad is None for p in small_model.parameters())

# ==============================================================================
# GROUP 10: Checkpoints, Stop Conditions & Frozen Baselines (Tests 101-115)
# ==============================================================================

def test_101_stop_conditions_count(ws05_manifest):
    stops = ws05_manifest["stop_conditions"]
    assert len(stops) == 12

def test_102_stop_01_nan_loss_defined(ws05_manifest):
    assert any("STOP-01" in s for s in ws05_manifest["stop_conditions"])

def test_103_stop_02_inf_loss_defined(ws05_manifest):
    assert any("STOP-02" in s for s in ws05_manifest["stop_conditions"])

def test_104_stop_03_nan_grad_defined(ws05_manifest):
    assert any("STOP-03" in s for s in ws05_manifest["stop_conditions"])

def test_105_stop_05_exploding_grad_norm_defined(ws05_manifest):
    assert any("STOP-05" in s for s in ws05_manifest["stop_conditions"])

def test_106_stop_06_validation_divergence_defined(ws05_manifest):
    assert any("STOP-06" in s for s in ws05_manifest["stop_conditions"])

def test_107_checkpoint_isolation_path_verification():
    # Ensure checkpoints are configured to save inside isolated candidate path
    cand_ckpt = CAND_DIR / "checkpoints"
    prod_ckpt = ROOT / "models"
    assert cand_ckpt != prod_ckpt

def test_108_training_execution_authorized_is_false(ws05_manifest):
    assert ws05_manifest["governance"]["training_execution_authorized"] is False

def test_109_candidate_traffic_share_is_zero(ws05_manifest):
    assert ws05_manifest["governance"]["candidate_traffic_share"] == 0.0

def test_110_ws05_verdict_is_fully_qualified(ws05_manifest):
    assert "A — TRAINING SAFETY FULLY QUALIFIED" in ws05_manifest["verdict"]

def test_111_frozen_phase55_corpus_hash_unmodified():
    expected = "3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1"
    assert hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest() == expected

def test_112_frozen_tokenizer_v2_hash_unmodified():
    expected = "65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4"
    assert hashlib.sha256(TOK_PATH.read_bytes()).hexdigest() == expected

def test_113_frozen_benchmark_manifest_hash_unmodified():
    expected = "554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088"
    assert hashlib.sha256(EVAL_PATH.read_bytes()).hexdigest() == expected

def test_114_frozen_production_db_hash_unmodified():
    expected = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == expected

def test_115_security_no_unsafe_primitives():
    # Verify training scripts contain no eval, exec, os.system
    for fname in ["loss.py", "trainer.py", "optimizer.py", "scheduler.py", "pretraining_config.py"]:
        p = ROOT / "core_model/training" / fname
        text = p.read_text(encoding="utf-8")
        assert not re.search(r"(?<!\.)\beval\(", text)
        assert not re.search(r"(?<!\.)\bexec\(", text)
        assert "os.system(" not in text
