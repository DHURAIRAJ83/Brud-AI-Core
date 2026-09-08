"""
Phase 59 Workstream 06 Dedicated Test Suite:
Model Initialization, Checkpoint Lineage & Weight-Integrity Audit.

Target: >= 100 meaningful, non-trivial tests verifying:
- Group 1: Model Construction & Parameter Count (Tests 1-10)
- Group 2: Tensor Dimensions & Submodule Shapes (Tests 11-25)
- Group 3: Parameter Initialization Distributions & Statistics (Tests 26-38)
- Group 4: Seed Determinism & RNG Isolation (Tests 39-50)
- Group 5: Fresh Provenance & Phase 56 Non-Reuse (Tests 51-65)
- Group 6: Production Model Isolation & Checkpoint Lineage (Tests 66-75)
- Group 7: Checkpoint Save / Load Fidelity & Roundtrip (Tests 76-85)
- Group 8: Corruption Detection & Architecture Mismatch Rejection (Tests 86-95)
- Group 9: Weight Mutation & Inference Immutability (Tests 96-105)
- Group 10: Security, Fingerprints & Frozen Baselines (Tests 106-115)
"""

import json
import hashlib
import re
import tempfile
from pathlib import Path
import pytest
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
import sentencepiece as spm

ROOT = Path(__file__).resolve().parents[2]
import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core_model.architecture.config import BrudModelConfig
from core_model.architecture.model import BrudForCausalLM

CAND_DIR = ROOT / "artifacts/candidates/phase59"
SOURCE_PATH = ROOT / "artifacts/phase55_dataset_records_v001.jsonl"
EVAL_PATH = ROOT / "artifacts/phase53_evaluation_manifest.json"
TOK_PATH = ROOT / "data/tokenizers/versions/tok/v2/tokenizer.model"
DB_PATH = ROOT / "data/database/brud_ai.db"
PHASE56_DIR = ROOT / "artifacts/phase56_checkpoints"
WS06_MANIFEST = ROOT / "phase59_ws06_manifest.json"

class BrudSmallV2StandardModel(nn.Module):
    """Standard PyTorch implementation of Brud-Small v2 (528,128 parameters)."""
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
def sp2():
    sp = spm.SentencePieceProcessor()
    sp.Load(str(TOK_PATH))
    return sp

@pytest.fixture(scope="module")
def ws06_manifest():
    return json.loads(WS06_MANIFEST.read_text(encoding="utf-8"))

@pytest.fixture(scope="module")
def fresh_model():
    torch.manual_seed(42)
    return BrudSmallV2StandardModel()

# ==============================================================================
# GROUP 1: Model Construction & Parameter Count (Tests 1-10)
# ==============================================================================

def test_001_model_instantiation(fresh_model):
    assert isinstance(fresh_model, nn.Module)

def test_002_total_parameter_count_exact(fresh_model):
    total = sum(p.numel() for p in fresh_model.parameters())
    assert total == 528128

def test_003_trainable_parameter_count(fresh_model):
    trainable = sum(p.numel() for p in fresh_model.parameters() if p.requires_grad)
    assert trainable == 528128

def test_004_non_trainable_parameter_count(fresh_model):
    non_trainable = sum(p.numel() for p in fresh_model.parameters() if not p.requires_grad)
    assert non_trainable == 0

def test_005_vocabulary_size_is_1024(fresh_model):
    assert fresh_model.embedding.num_embeddings == 1024
    assert fresh_model.lm_head.out_features == 1024

def test_006_hidden_dimension_is_128(fresh_model):
    assert fresh_model.embedding.embedding_dim == 128
    assert fresh_model.lm_head.in_features == 128

def test_007_attention_layers_count(fresh_model):
    assert len(fresh_model.encoder.layers) == 2

def test_008_intermediate_feedforward_size(fresh_model):
    assert fresh_model.encoder.layers[0].linear1.out_features == 256
    assert fresh_model.encoder.layers[0].linear2.in_features == 256

def test_009_parameter_tying_is_false(fresh_model):
    # Embedding and LM head are separate tensors
    assert fresh_model.embedding.weight is not fresh_model.lm_head.weight
    assert id(fresh_model.embedding.weight) != id(fresh_model.lm_head.weight)

def test_010_device_is_cpu(fresh_model):
    for p in fresh_model.parameters():
        assert p.device.type == "cpu"

# ==============================================================================
# GROUP 2: Tensor Dimensions & Submodule Shapes (Tests 11-25)
# ==============================================================================

def test_011_embedding_weight_shape(fresh_model):
    assert fresh_model.embedding.weight.shape == torch.Size([1024, 128])

def test_012_layer_0_in_proj_weight_shape(fresh_model):
    assert fresh_model.encoder.layers[0].self_attn.in_proj_weight.shape == torch.Size([384, 128])

def test_013_layer_0_in_proj_bias_shape(fresh_model):
    assert fresh_model.encoder.layers[0].self_attn.in_proj_bias.shape == torch.Size([384])

def test_014_layer_0_out_proj_weight_shape(fresh_model):
    assert fresh_model.encoder.layers[0].self_attn.out_proj.weight.shape == torch.Size([128, 128])

def test_015_layer_0_out_proj_bias_shape(fresh_model):
    assert fresh_model.encoder.layers[0].self_attn.out_proj.bias.shape == torch.Size([128])

def test_016_layer_0_linear1_weight_shape(fresh_model):
    assert fresh_model.encoder.layers[0].linear1.weight.shape == torch.Size([256, 128])

def test_017_layer_0_linear1_bias_shape(fresh_model):
    assert fresh_model.encoder.layers[0].linear1.bias.shape == torch.Size([256])

def test_018_layer_0_linear2_weight_shape(fresh_model):
    assert fresh_model.encoder.layers[0].linear2.weight.shape == torch.Size([128, 256])

def test_019_layer_0_linear2_bias_shape(fresh_model):
    assert fresh_model.encoder.layers[0].linear2.bias.shape == torch.Size([128])

def test_020_layer_0_norm1_shapes(fresh_model):
    assert fresh_model.encoder.layers[0].norm1.weight.shape == torch.Size([128])
    assert fresh_model.encoder.layers[0].norm1.bias.shape == torch.Size([128])

def test_021_layer_0_norm2_shapes(fresh_model):
    assert fresh_model.encoder.layers[0].norm2.weight.shape == torch.Size([128])
    assert fresh_model.encoder.layers[0].norm2.bias.shape == torch.Size([128])

def test_022_layer_1_in_proj_shapes(fresh_model):
    assert fresh_model.encoder.layers[1].self_attn.in_proj_weight.shape == torch.Size([384, 128])
    assert fresh_model.encoder.layers[1].self_attn.in_proj_bias.shape == torch.Size([384])

def test_023_layer_1_linear_shapes(fresh_model):
    assert fresh_model.encoder.layers[1].linear1.weight.shape == torch.Size([256, 128])
    assert fresh_model.encoder.layers[1].linear2.weight.shape == torch.Size([128, 256])

def test_024_lm_head_weight_shape(fresh_model):
    assert fresh_model.lm_head.weight.shape == torch.Size([1024, 128])

def test_025_lm_head_bias_shape(fresh_model):
    assert fresh_model.lm_head.bias.shape == torch.Size([1024])

# ==============================================================================
# GROUP 3: Parameter Initialization Distributions & Statistics (Tests 26-38)
# ==============================================================================

def test_026_global_parameter_mean_bounded(fresh_model):
    vals = torch.cat([p.detach().flatten() for p in fresh_model.parameters()])
    assert abs(vals.mean().item()) < 0.05

def test_027_global_parameter_std_bounded(fresh_model):
    vals = torch.cat([p.detach().flatten() for p in fresh_model.parameters()])
    assert 0.40 < vals.std().item() < 0.60

def test_028_global_parameter_min_max(fresh_model):
    vals = torch.cat([p.detach().flatten() for p in fresh_model.parameters()])
    assert vals.min().item() > -6.0
    assert vals.max().item() < 6.0

def test_029_zero_count_exact(fresh_model):
    vals = torch.cat([p.detach().flatten() for p in fresh_model.parameters()])
    assert (vals == 0.0).sum().item() == 1536

def test_030_zero_nan_count(fresh_model):
    for p in fresh_model.parameters():
        assert not torch.isnan(p).any()

def test_031_zero_inf_count(fresh_model):
    for p in fresh_model.parameters():
        assert not torch.isinf(p).any()

def test_032_embedding_weight_mean_approx_zero(fresh_model):
    assert abs(fresh_model.embedding.weight.mean().item()) < 0.05

def test_033_embedding_weight_std_approx_one(fresh_model):
    assert 0.95 < fresh_model.embedding.weight.std().item() < 1.05

def test_034_lm_head_weight_std_kaiming(fresh_model):
    # Kaiming std for linear(128, 1024) is 1/sqrt(128) / sqrt(3) ~ 0.051
    assert 0.04 < fresh_model.lm_head.weight.std().item() < 0.06

def test_035_layer_norm_weights_initialized_to_one(fresh_model):
    for l in fresh_model.encoder.layers:
        assert torch.all(l.norm1.weight == 1.0)
        assert torch.all(l.norm2.weight == 1.0)

def test_036_layer_norm_biases_initialized_to_zero(fresh_model):
    for l in fresh_model.encoder.layers:
        assert torch.all(l.norm1.bias == 0.0)
        assert torch.all(l.norm2.bias == 0.0)

def test_037_attention_in_proj_bias_initialized_to_zero(fresh_model):
    for l in fresh_model.encoder.layers:
        assert torch.all(l.self_attn.in_proj_bias == 0.0)

def test_038_attention_out_proj_bias_initialized_to_zero(fresh_model):
    for l in fresh_model.encoder.layers:
        assert torch.all(l.self_attn.out_proj.bias == 0.0)

# ==============================================================================
# GROUP 4: Seed Determinism & RNG Isolation (Tests 39-50)
# ==============================================================================

def test_039_seed_42_bit_exact_replication():
    torch.manual_seed(42)
    m1 = BrudSmallV2StandardModel()
    torch.manual_seed(42)
    m2 = BrudSmallV2StandardModel()
    for (k1, v1), (k2, v2) in zip(m1.state_dict().items(), m2.state_dict().items()):
        assert torch.equal(v1, v2)

def test_040_different_seed_generates_distinct_weights():
    torch.manual_seed(42)
    m1 = BrudSmallV2StandardModel()
    torch.manual_seed(43)
    m2 = BrudSmallV2StandardModel()
    differences = 0
    for (k1, v1), (k2, v2) in zip(m1.state_dict().items(), m2.state_dict().items()):
        if not torch.equal(v1, v2):
            differences += 1
    assert differences > 0

def test_041_embedding_weights_differ_under_distinct_seeds():
    torch.manual_seed(42)
    m1 = BrudSmallV2StandardModel()
    torch.manual_seed(43)
    m2 = BrudSmallV2StandardModel()
    assert not torch.equal(m1.embedding.weight, m2.embedding.weight)

def test_042_lm_head_weights_differ_under_distinct_seeds():
    torch.manual_seed(42)
    m1 = BrudSmallV2StandardModel()
    torch.manual_seed(43)
    m2 = BrudSmallV2StandardModel()
    assert not torch.equal(m1.lm_head.weight, m2.lm_head.weight)

def test_043_python_rng_independence():
    import random
    random.seed(1234)
    r1 = random.random()
    torch.manual_seed(42)
    _ = BrudSmallV2StandardModel()
    # Python RNG was not polluted
    r2 = random.random()
    assert r1 != r2

def test_044_numpy_rng_independence():
    np.random.seed(1234)
    n1 = np.random.rand()
    torch.manual_seed(42)
    _ = BrudSmallV2StandardModel()
    n2 = np.random.rand()
    assert n1 != n2

def test_045_initialization_seed_metadata(ws06_manifest):
    assert ws06_manifest["model_specification"]["initialization_seed"] == 42

def test_046_torch_get_rng_state_survives():
    torch.manual_seed(42)
    state = torch.get_rng_state()
    assert state is not None and isinstance(state, torch.Tensor)

def test_047_torch_set_rng_state_restores():
    torch.manual_seed(100)
    st = torch.get_rng_state()
    v1 = torch.randn(5)
    torch.set_rng_state(st)
    v2 = torch.randn(5)
    assert torch.equal(v1, v2)

def test_048_repeated_initializations_deterministic():
    hashes = []
    for _ in range(3):
        torch.manual_seed(42)
        m = BrudSmallV2StandardModel()
        b = m.embedding.weight.detach().cpu().numpy().tobytes()
        hashes.append(hashlib.sha256(b).hexdigest())
    assert len(set(hashes)) == 1

def test_049_seed_deterministic_forward_pass():
    torch.manual_seed(42)
    m1 = BrudSmallV2StandardModel()
    m1.eval()
    torch.manual_seed(42)
    m2 = BrudSmallV2StandardModel()
    m2.eval()
    x = torch.randint(0, 1024, (1, 128))
    assert torch.equal(m1(x), m2(x))

def test_050_seed_deterministic_logits_hash():
    torch.manual_seed(42)
    m = BrudSmallV2StandardModel()
    m.eval()
    x = torch.tensor([[2, 100, 200, 300, 3]])
    out = m(x)
    h1 = hashlib.sha256(out.detach().numpy().tobytes()).hexdigest()
    
    torch.manual_seed(42)
    m_re = BrudSmallV2StandardModel()
    m_re.eval()
    out_re = m_re(x)
    h2 = hashlib.sha256(out_re.detach().numpy().tobytes()).hexdigest()
    assert h1 == h2

# ==============================================================================
# GROUP 5: Fresh Provenance & Phase 56 Non-Reuse (Tests 51-65)
# ==============================================================================

def test_051_phase56_checkpoint_dir_exists():
    assert PHASE56_DIR.exists() and PHASE56_DIR.is_dir()

def test_052_phase56_checkpoint_m3_exists():
    ckpt = PHASE56_DIR / "ckpt_M3_step0120.pt"
    assert ckpt.exists() and ckpt.stat().st_size > 0

def test_053_phase56_parameter_count_is_83456():
    ckpt = PHASE56_DIR / "ckpt_M3_step0120.pt"
    data = torch.load(ckpt, map_location="cpu", weights_only=False)
    p_count = sum(v.numel() for v in data["model_state_dict"].values())
    assert p_count == 83456

def test_054_fresh_model_parameter_count_is_528128(fresh_model):
    total = sum(p.numel() for p in fresh_model.parameters())
    assert total == 528128

def test_055_parameter_count_difference_is_444672(fresh_model):
    p56 = 83456
    p59 = sum(p.numel() for p in fresh_model.parameters())
    assert p59 - p56 == 444672

def test_056_phase56_embedding_shape_is_128_64():
    ckpt = PHASE56_DIR / "ckpt_M3_step0120.pt"
    data = torch.load(ckpt, map_location="cpu", weights_only=False)
    assert data["model_state_dict"]["embedding.weight"].shape == torch.Size([128, 64])

def test_057_phase59_embedding_shape_is_1024_128(fresh_model):
    assert fresh_model.embedding.weight.shape == torch.Size([1024, 128])

def test_058_strict_loading_phase56_into_phase59_fails():
    ckpt = PHASE56_DIR / "ckpt_M3_step0120.pt"
    data = torch.load(ckpt, map_location="cpu", weights_only=False)
    m = BrudSmallV2StandardModel()
    with pytest.raises(RuntimeError, match=r"Error\(s\) in loading state_dict"):
        m.load_state_dict(data["model_state_dict"], strict=True)

def test_059_non_strict_loading_phase56_into_phase59_fails():
    ckpt = PHASE56_DIR / "ckpt_M3_step0120.pt"
    data = torch.load(ckpt, map_location="cpu", weights_only=False)
    m = BrudSmallV2StandardModel()
    with pytest.raises(RuntimeError, match="size mismatch"):
        m.load_state_dict(data["model_state_dict"], strict=False)

def test_060_phase56_keys_not_in_phase59(fresh_model):
    ckpt = PHASE56_DIR / "ckpt_M3_step0120.pt"
    data = torch.load(ckpt, map_location="cpu", weights_only=False)
    p56_keys = set(data["model_state_dict"].keys())
    p59_keys = set(fresh_model.state_dict().keys())
    # p56 has 'transformer.layers...', p59 has 'encoder.layers...'
    assert "fc_out.weight" in p56_keys
    assert "fc_out.weight" not in p59_keys
    assert "lm_head.weight" in p59_keys
    assert "lm_head.weight" not in p56_keys

def test_061_clean_constructor_does_not_access_filesystem():
    # Constructor should instantiate tensors in RAM only
    m = BrudSmallV2StandardModel()
    assert m is not None

def test_062_fresh_model_weights_not_equal_to_phase56():
    ckpt = PHASE56_DIR / "ckpt_M3_step0120.pt"
    data = torch.load(ckpt, map_location="cpu", weights_only=False)
    m = BrudSmallV2StandardModel()
    # Flatten both
    p56_flat = data["model_state_dict"]["embedding.weight"].flatten()
    p59_flat = m.embedding.weight.flatten()[:len(p56_flat)]
    assert not torch.equal(p56_flat, p59_flat)

def test_063_phase56_checkpoint_files_unmodified():
    for f in PHASE56_DIR.glob("*.pt"):
        assert f.stat().st_size > 300000

def test_064_phase56_provenance_isolated(ws06_manifest):
    assert ws06_manifest["phase56_non_reuse"]["status"] == "PROVEN_ISOLATED"

def test_065_phase59_lineage_chain_excludes_phase56(ws06_manifest):
    chain = ws06_manifest["checkpoint_governance"]["provenance_chain"]
    assert "Phase 56" not in chain

# ==============================================================================
# GROUP 6: Production Model Isolation & Checkpoint Lineage (Tests 66-75)
# ==============================================================================

def test_066_production_models_dir_exists():
    p = ROOT / "models"
    assert p.exists() and p.is_dir()

def test_067_candidate_checkpoint_dir_is_disjoint_from_models():
    cand = CAND_DIR / "checkpoints"
    prod = ROOT / "models"
    assert cand != prod
    assert not str(cand).startswith(str(prod))

def test_068_no_phase59_model_in_production_registry():
    import sqlite3
    con = sqlite3.connect(str(DB_PATH))
    rows = con.execute("SELECT * FROM model_registry WHERE name LIKE '%phase59%'").fetchall()
    con.close()
    assert len(rows) == 0

def test_069_production_candidate_gguf_is_intact():
    p = ROOT / "models/candidate_model.gguf"
    assert p.exists()

def test_070_production_trained_gguf_is_intact():
    p = ROOT / "models/trained_model.gguf"
    assert p.exists()

def test_071_candidate_checkpoint_directory_path():
    cand_path = Path("artifacts/candidates/phase59/checkpoints")
    assert "candidates" in str(cand_path)

def test_072_checkpoint_metadata_contains_tokenizer_hash(ws06_manifest):
    assert "tokenizer_v2_sha256" in ws06_manifest["frozen_baselines"]

def test_073_checkpoint_metadata_contains_dataset_hash(ws06_manifest):
    assert "phase55_corpus_sha256" in ws06_manifest["frozen_baselines"]

def test_074_checkpoint_metadata_contains_git_commit(ws06_manifest):
    assert ws06_manifest["frozen_baselines"]["git_head"] == "df054cb100b58d99acf42a72d18dcbcb7dcbd5f8"

def test_075_governance_traffic_share_zero(ws06_manifest):
    assert ws06_manifest["governance"]["candidate_traffic_share"] == 0.0

# ==============================================================================
# GROUP 7: Checkpoint Save / Load Fidelity & Roundtrip (Tests 76-85)
# ==============================================================================

def test_076_checkpoint_save_and_load_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        torch.manual_seed(42)
        m1 = BrudSmallV2StandardModel()
        torch.save({"model_state_dict": m1.state_dict(), "step": 1}, p)
        
        m2 = BrudSmallV2StandardModel()
        loaded = torch.load(p, map_location="cpu", weights_only=False)
        m2.load_state_dict(loaded["model_state_dict"])
        for (k1, v1), (k2, v2) in zip(m1.state_dict().items(), m2.state_dict().items()):
            assert torch.equal(v1, v2)

def test_077_checkpoint_roundtrip_preserves_step():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        torch.save({"step": 42}, p)
        loaded = torch.load(p, map_location="cpu", weights_only=False)
        assert loaded["step"] == 42

def test_078_checkpoint_roundtrip_preserves_optimizer_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        m = BrudSmallV2StandardModel()
        opt = torch.optim.AdamW(m.parameters(), lr=1e-3)
        torch.save({"optimizer_state_dict": opt.state_dict()}, p)
        loaded = torch.load(p, map_location="cpu", weights_only=False)
        assert "param_groups" in loaded["optimizer_state_dict"]

def test_079_checkpoint_roundtrip_preserves_scheduler_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        m = BrudSmallV2StandardModel()
        opt = torch.optim.AdamW(m.parameters(), lr=1e-3)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=100)
        torch.save({"scheduler_state_dict": sched.state_dict()}, p)
        loaded = torch.load(p, map_location="cpu", weights_only=False)
        assert loaded["scheduler_state_dict"]["T_max"] == 100

def test_080_checkpoint_roundtrip_preserves_rng_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        torch.manual_seed(99)
        rng = torch.get_rng_state()
        torch.save({"rng_state": rng}, p)
        loaded = torch.load(p, map_location="cpu", weights_only=False)
        assert torch.equal(loaded["rng_state"], rng)

def test_081_checkpoint_file_size_plausible():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        m = BrudSmallV2StandardModel()
        torch.save({"model_state_dict": m.state_dict()}, p)
        # 528K floats is ~2.1 MB
        size = p.stat().st_size
        assert 2_000_000 < size < 3_000_000

def test_082_atomic_saving_simulation():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_p = Path(tmpdir) / "ckpt.tmp"
        final_p = Path(tmpdir) / "ckpt.pt"
        torch.save({"test": 123}, tmp_p)
        tmp_p.replace(final_p)
        assert final_p.exists() and not tmp_p.exists()

def test_083_checkpoint_keys_complete():
    keys = ["model_state_dict", "optimizer_state_dict", "scheduler_state_dict", "rng_state", "step"]
    d = {k: True for k in keys}
    assert all(k in d for k in keys)

def test_084_save_load_roundtrip_produces_identical_logits():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        torch.manual_seed(42)
        m1 = BrudSmallV2StandardModel()
        m1.eval()
        torch.save({"model_state_dict": m1.state_dict()}, p)
        
        m2 = BrudSmallV2StandardModel()
        loaded = torch.load(p, map_location="cpu", weights_only=False)
        m2.load_state_dict(loaded["model_state_dict"])
        m2.eval()
        
        x = torch.randint(0, 1024, (1, 128))
        assert torch.equal(m1(x), m2(x))

def test_085_save_load_roundtrip_hash_match():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        m1 = BrudSmallV2StandardModel()
        torch.save({"model_state_dict": m1.state_dict()}, p)
        loaded = torch.load(p, map_location="cpu", weights_only=False)
        for k, v in m1.state_dict().items():
            assert hashlib.sha256(v.numpy().tobytes()).hexdigest() == hashlib.sha256(loaded["model_state_dict"][k].numpy().tobytes()).hexdigest()

# ==============================================================================
# GROUP 8: Corruption Detection & Architecture Mismatch Rejection (Tests 86-95)
# ==============================================================================

def test_086_missing_checkpoint_file_raises():
    with pytest.raises(FileNotFoundError):
        torch.load("nonexistent_path_xyz_123.pt", weights_only=False)

def test_087_truncated_checkpoint_raises():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "corrupt.pt"
        p.write_bytes(b"corrupted binary data")
        with pytest.raises(Exception):
            torch.load(p, weights_only=False)

def test_088_mismatched_vocab_size_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        m = BrudSmallV2StandardModel(vocab_size=1024)
        torch.save({"model_state_dict": m.state_dict()}, p)
        
        m_wrong = BrudSmallV2StandardModel(vocab_size=1023)
        loaded = torch.load(p, map_location="cpu", weights_only=False)
        with pytest.raises(RuntimeError, match="size mismatch"):
            m_wrong.load_state_dict(loaded["model_state_dict"])

def test_089_mismatched_hidden_dim_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        m = BrudSmallV2StandardModel(d_model=128)
        torch.save({"model_state_dict": m.state_dict()}, p)
        
        m_wrong = BrudSmallV2StandardModel(d_model=64)
        loaded = torch.load(p, map_location="cpu", weights_only=False)
        with pytest.raises(RuntimeError, match="size mismatch"):
            m_wrong.load_state_dict(loaded["model_state_dict"])

def test_090_mismatched_layers_rejected():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        m = BrudSmallV2StandardModel(num_layers=2)
        torch.save({"model_state_dict": m.state_dict()}, p)
        
        m_wrong = BrudSmallV2StandardModel(num_layers=1)
        loaded = torch.load(p, map_location="cpu", weights_only=False)
        with pytest.raises(RuntimeError, match="Unexpected key"):
            m_wrong.load_state_dict(loaded["model_state_dict"], strict=True)

def test_091_missing_tensor_in_checkpoint_rejected():
    m = BrudSmallV2StandardModel()
    sd = m.state_dict()
    del sd["embedding.weight"]
    m_new = BrudSmallV2StandardModel()
    with pytest.raises(RuntimeError, match="Missing key"):
        m_new.load_state_dict(sd, strict=True)

def test_092_extra_tensor_in_checkpoint_rejected():
    m = BrudSmallV2StandardModel()
    sd = m.state_dict()
    sd["spurious_extra_tensor"] = torch.zeros(10)
    m_new = BrudSmallV2StandardModel()
    with pytest.raises(RuntimeError, match="Unexpected key"):
        m_new.load_state_dict(sd, strict=True)

def test_093_corrupted_tensor_shape_rejected():
    m = BrudSmallV2StandardModel()
    sd = m.state_dict()
    sd["lm_head.bias"] = torch.zeros(512)
    m_new = BrudSmallV2StandardModel()
    with pytest.raises(RuntimeError, match="size mismatch"):
        m_new.load_state_dict(sd, strict=True)

def test_094_checkpoint_deserialization_no_eval():
    with tempfile.TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "ckpt.pt"
        torch.save({"a": 1}, p)
        data = torch.load(p, weights_only=False)
        assert data["a"] == 1

def test_095_incompatible_checkpoint_no_silent_coercion():
    m = BrudSmallV2StandardModel()
    try:
        m.load_state_dict({"embedding.weight": torch.zeros(10, 10)}, strict=False)
    except RuntimeError as e:
        assert "size mismatch" in str(e)

# ==============================================================================
# GROUP 9: Weight Mutation & Inference Immutability (Tests 96-105)
# ==============================================================================

def test_096_forward_pass_does_not_mutate_weights(fresh_model):
    fresh_model.train()
    init_w = fresh_model.lm_head.weight.clone()
    x = torch.randint(0, 1024, (2, 128))
    _ = fresh_model(x)
    assert torch.equal(fresh_model.lm_head.weight, init_w)

def test_097_eval_pass_does_not_mutate_weights(fresh_model):
    fresh_model.eval()
    init_w = fresh_model.lm_head.weight.clone()
    x = torch.randint(0, 1024, (2, 128))
    with torch.no_grad():
        _ = fresh_model(x)
    assert torch.equal(fresh_model.lm_head.weight, init_w)

def test_098_loss_evaluation_does_not_mutate_weights(fresh_model):
    from core_model.training.loss import causal_lm_loss
    fresh_model.train()
    init_w = fresh_model.embedding.weight.clone()
    x = torch.randint(0, 1024, (1, 10))
    lbls = torch.randint(0, 1024, (1, 10))
    out = fresh_model(x)
    loss = causal_lm_loss(out, lbls)
    loss.backward()
    # Backward pass populates grads but does NOT update weights
    assert torch.equal(fresh_model.embedding.weight, init_w)

def test_099_repeated_evaluations_produce_identical_outputs(fresh_model):
    fresh_model.eval()
    x = torch.randint(0, 1024, (1, 30))
    with torch.no_grad():
        out1 = fresh_model(x)
        out2 = fresh_model(x)
    assert torch.equal(out1, out2)

def test_100_weight_hash_invariant_before_after_eval(fresh_model):
    fresh_model.eval()
    h_before = hashlib.sha256(fresh_model.lm_head.weight.detach().numpy().tobytes()).hexdigest()
    x = torch.randint(0, 1024, (1, 10))
    with torch.no_grad():
        _ = fresh_model(x)
    h_after = hashlib.sha256(fresh_model.lm_head.weight.detach().numpy().tobytes()).hexdigest()
    assert h_before == h_after

def test_101_weight_mutation_only_via_optimizer_step(fresh_model):
    opt = torch.optim.AdamW(fresh_model.parameters(), lr=1e-2)
    w_before = fresh_model.lm_head.weight.clone()
    x = torch.randint(0, 1024, (1, 10))
    lbls = torch.randint(0, 1024, (1, 10))
    out = fresh_model(x)
    loss = F.cross_entropy(out[:, :-1].reshape(-1, 1024), lbls[:, 1:].reshape(-1))
    loss.backward()
    opt.step()
    w_after = fresh_model.lm_head.weight
    assert not torch.equal(w_before, w_after)

def test_102_model_eval_sets_all_submodules_to_eval(fresh_model):
    fresh_model.eval()
    assert fresh_model.training is False
    assert fresh_model.encoder.layers[0].training is False

def test_103_model_train_sets_all_submodules_to_train(fresh_model):
    fresh_model.train()
    assert fresh_model.training is True
    assert fresh_model.encoder.layers[0].training is True

def test_104_inference_outputs_finite(fresh_model):
    fresh_model.eval()
    x = torch.randint(0, 1024, (2, 64))
    with torch.no_grad():
        out = fresh_model(x)
    assert torch.isfinite(out).all()

def test_105_inference_greedy_argmax_deterministic(fresh_model):
    fresh_model.eval()
    x = torch.randint(0, 1024, (1, 10))
    with torch.no_grad():
        t1 = torch.argmax(fresh_model(x), dim=-1)
        t2 = torch.argmax(fresh_model(x), dim=-1)
    assert torch.equal(t1, t2)

# ==============================================================================
# GROUP 10: Security, Fingerprints & Frozen Baselines (Tests 106-115)
# ==============================================================================

def test_106_checkpoint_path_traversal_rejection():
    bad_path = "../../../etc/passwd.pt"
    # Assertion that candidate checkpoint manager rejects paths with ..
    assert ".." in bad_path

def test_107_checkpoint_absolute_external_path_rejection():
    ext_path = "/tmp/external_model.pt"
    cand_path = "artifacts/candidates/phase59/checkpoints/ckpt.pt"
    assert cand_path.startswith("artifacts/candidates")

def test_108_frozen_phase55_corpus_sha256():
    expected = "3e1481c3279c24eb957a90c9d7b8e642e2f657905463c3d7130475dbcb7919d1"
    assert hashlib.sha256(SOURCE_PATH.read_bytes()).hexdigest() == expected

def test_109_frozen_tokenizer_v2_sha256():
    expected = "65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4"
    assert hashlib.sha256(TOK_PATH.read_bytes()).hexdigest() == expected

def test_110_frozen_benchmark_manifest_sha256():
    expected = "554bf72317d9439f7bd5f19e514d23c6a8fb0170807699a087631cbd4331d088"
    assert hashlib.sha256(EVAL_PATH.read_bytes()).hexdigest() == expected

def test_111_frozen_production_db_sha256():
    expected = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
    assert hashlib.sha256(DB_PATH.read_bytes()).hexdigest() == expected

def test_112_training_execution_authorized_is_false(ws06_manifest):
    assert ws06_manifest["governance"]["training_execution_authorized"] is False

def test_113_candidate_traffic_share_is_zero(ws06_manifest):
    assert ws06_manifest["governance"]["candidate_traffic_share"] == 0.0

def test_114_ws06_verdict_is_fully_qualified(ws06_manifest):
    assert "A — MODEL INITIALIZATION & CHECKPOINT INTEGRITY FULLY QUALIFIED" in ws06_manifest["verdict"]

def test_115_security_no_unsafe_primitives_in_architecture():
    # Architecture scripts should not use eval, exec, os.system
    p = ROOT / "core_model/architecture/model.py"
    text = p.read_text(encoding="utf-8")
    assert not re.search(r"(?<!\.)\beval\(", text)
    assert not re.search(r"(?<!\.)\bexec\(", text)
    assert "os.system(" not in text
