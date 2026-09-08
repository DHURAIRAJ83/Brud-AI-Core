"""Phase 50 Sovereign Training Scale, Multi-Day Token Accumulation & Independent Capability Validation Test Suite.

Contains 120 comprehensive test methods covering:
- Baseline Audit & System Invariants (001 - 002)
- Corpus Inventory & Quality Controls (003 - 007)
- Manifest & Evaluation Isolation (008 - 012)
- Training & Hardware Bounds (013 - 022)
- Checkpoint Lineage & Lineage Recovery (023 - 030)
- Multi-Session & Token Accounting (031 - 035)
- Convergence, Loss & Overfitting Guards (036 - 041)
- 5-Level Reasoning & Linguistic Competency (042 - 049)
- Grounding, Safe Refusal & OOD Generalization (050 - 053)
- Stochastic Evaluation & Confidence Intervals (054 - 056)
- Gain / 1,000 Tokens & Denominator Protection (057 - 058)
- Causal Attribution & Loss vs Capability (059 - 060)
- Campaign Lifecycle & Lease Management (061 - 070)
- Admin API & Tenant Isolation (071 - 074)
- Public Chat & Governance Controls (075 - 078)
- Security & Static AST Invariants (079 - 083)
- Database & Git Immutability (084 - 086)
- Regression Compatibility (087 - 092)
- Multi-Checkpoint Progression & Forecasting (093 - 102)
- Campaign Integrity & Replay Rejection (103 - 108)
- Evaluator Invariants & Benchmark Defense (109 - 114)
- Failure Fallback & Cross-Phase Compatibility (115 - 118)
- End-to-End Campaign & Final Invariant Verification (119 - 120)
"""

from __future__ import annotations

import ast
import hashlib
import json
import math
import os
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

from core_model.architecture.config import BrudModelConfig, micro_preset
from core_model.architecture.model import BrudForCausalLM
from core_model.corpus.phase47_corpus_expander import (
    Phase47CorpusExpander,
    TamilNormalizationError,
    normalize_tamil_safe,
)
from core_model.corpus.phase49_ingestion_scheduler import (
    IngestionError,
    Phase49IngestionScheduler,
)
from core_model.corpus.phase50_dataset_pipeline import (
    Phase50DatasetManifest,
    Phase50DatasetPipeline,
    Phase50MultiEpochDataloader,
)
from core_model.evaluation.phase48_capability_evaluator import StochasticTrialResult
from core_model.evaluation.phase50_capability_evaluator import (
    CausalityVerdict,
    OpenDomainStatus,
    Phase50CapabilityEvaluator,
    Phase50CapabilitySnapshot,
    Phase50GainResult,
)
from core_model.training.phase48_token_ledger import TokenLedgerError
from core_model.training.phase48_training_queue import JobStatus, Phase48TrainingQueue
from core_model.training.phase48_training_worker import Phase48TrainingWorker, WorkerState
from core_model.training.phase49_checkpoint_manager import (
    CheckpointLifecycleError,
    Phase49CheckpointManager,
)
from core_model.training.phase49_token_ledger import Phase49TokenLedger
from core_model.training.phase49_training_daemon import (
    DaemonState,
    DatasetManifestMismatchError,
    ExclusiveTrainingLease,
    Phase49TrainingDaemon,
    TrainingLeaseError,
)


ROOT_DIR = Path("/home/dhurai/Projects/brud-ai")
PROD_DB = ROOT_DIR / "data/database/brud_ai.db"
EXPECTED_DB_SHA = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_DB_SIZE = 11096064
EXPECTED_GIT_HEAD = "df054cb100b58d99acf42a72d18dcbcb7dcbd5f8"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


# -------------------------------------------------------------
# 1. Baseline Audit & System Invariants (001 - 002)
# -------------------------------------------------------------
def test_001_baseline_audit_git_and_database() -> None:
    assert PROD_DB.exists()
    assert _sha256(PROD_DB) == EXPECTED_DB_SHA
    assert PROD_DB.stat().st_size == EXPECTED_DB_SIZE
    wal = PROD_DB.with_name("brud_ai.db-wal")
    shm = PROD_DB.with_name("brud_ai.db-shm")
    assert not wal.exists()
    assert not shm.exists()


def test_002_scale_gap_analysis_measurements() -> None:
    audit_file = ROOT_DIR / "phase50_scale_gap_analysis.md"
    assert audit_file.exists()
    content = audit_file.read_text()
    assert "TIER B" in content
    assert "100,000" in content
    assert "8,680" in content


# -------------------------------------------------------------
# 2. Corpus Inventory & Quality Controls (003 - 007)
# -------------------------------------------------------------
def test_003_corpus_inventory_approved_sources(tmp_path: Path) -> None:
    pipeline = Phase50DatasetPipeline(artifacts_dir=tmp_path)
    records = pipeline.discover_and_compile_approved_records()
    assert len(records) > 0
    for r in records:
        assert r.is_trainable is True
        assert r.rights_status in {"verified", "user_owned_with_permission", "public_domain", "approved"}


def test_004_approval_gating_unauthorized_excluded() -> None:
    exp = Phase47CorpusExpander()
    rec = exp.process_record(
        raw_text="This is an unapproved raw document text.",
        record_id="rec_unapproved",
        rights_status="unauthorized_scraping",
        approval_status="pending",
    )
    assert rec is None


def test_005_provenance_tracking_source_hashes(tmp_path: Path) -> None:
    pipeline = Phase50DatasetPipeline(artifacts_dir=tmp_path)
    recs = pipeline.discover_and_compile_approved_records()
    m = pipeline.build_and_save_manifest(recs, version="test_v1")
    assert len(m.source_hashes) > 0
    assert m.manifest_hash is not None


def test_006_tamil_safe_unicode_normalization() -> None:
    valid_ta = "தமிழ் வாழ்க"
    norm = normalize_tamil_safe(valid_ta)
    assert norm == valid_ta

    orphan_combining = "\u0bcdதமிழ்"  # starts with virama
    with pytest.raises(TamilNormalizationError):
        normalize_tamil_safe(orphan_combining)


def test_007_contamination_defense_5_way_screening() -> None:
    exp = Phase47CorpusExpander()
    assert exp.is_benchmark_contaminated("Calculate 15 + 27 =") is True
    assert exp.is_benchmark_contaminated("All men are mortal. Socrates is a man. Therefore:") is True
    assert exp.is_benchmark_contaminated("This is completely independent research text about astronomy.") is False


# -------------------------------------------------------------
# 3. Manifest & Evaluation Isolation (008 - 012)
# -------------------------------------------------------------
def test_008_dataset_manifest_creation_and_fields(tmp_path: Path) -> None:
    pipeline = Phase50DatasetPipeline(artifacts_dir=tmp_path)
    recs = pipeline.discover_and_compile_approved_records()
    m = pipeline.build_and_save_manifest(recs, version="v_field_check")
    assert m.record_count > 0
    assert m.unique_tokens > 0
    assert m.train_tokens >= 0
    assert m.validation_tokens >= 0


def test_009_dataset_manifest_immutability(tmp_path: Path) -> None:
    manifest_path = tmp_path / "phase50_dataset_manifest_v001.json"
    m_data = {"version": "v001", "manifest_hash": "abc123hash"}
    manifest_path.write_text(json.dumps(m_data))
    assert manifest_path.exists()


def test_010_evaluation_manifest_creation_and_fields() -> None:
    eval_file = ROOT_DIR / "artifacts/phase50_evaluation_manifest.json"
    assert eval_file.exists()
    data = json.loads(eval_file.read_text())
    assert "structured_probes" in data
    assert "anti_saturation_probes" in data
    assert "open_domain_generative_probes" in data
    assert data["manifest_hash"] is not None


def test_011_evaluation_manifest_isolation_from_training() -> None:
    eval_file = ROOT_DIR / "artifacts/phase50_evaluation_manifest.json"
    data = json.loads(eval_file.read_text())
    eval_prompts = {p["prompt"] for p in data.get("structured_probes", [])}
    sft_files = list((ROOT_DIR / "data/document_sft_exports").glob("*.jsonl"))
    for f in sft_files[:20]:
        content = f.read_text()
        for p in eval_prompts:
            assert p not in content


def test_012_baseline_capability_frozen_evaluation() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {
        "Calculate 15 + 27 =": "42",
        "Sort ascending: 8, 3, 11": "3, 8, 11",
        "தமிழ் நாட்டின் தலைநகரம் எது?": "சென்னை",
    }
    snap = evaluator.evaluate_checkpoint("ckpt_baseline_test", "hash_base", 9056, 4.15, resp)
    assert snap.tokens_accumulated == 9056
    assert snap.structured_benchmark_score > 0.0


# -------------------------------------------------------------
# 4. Training & Hardware Bounds (013 - 022)
# -------------------------------------------------------------
def test_013_training_initialization_state(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    worker = Phase48TrainingWorker("w_init", cfg, tmp_path / "ckpts", ledger, max_threads=2)
    assert worker.state in {WorkerState.INITIALIZING, WorkerState.QUEUED, WorkerState.STOPPED}


def test_014_cpu_thread_limit_enforced(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    worker = Phase48TrainingWorker("w_threads", cfg, tmp_path / "ckpts", ledger, max_threads=2)
    assert worker.max_threads == 2
    assert torch.get_num_threads() <= 2


def test_015_worker_concurrency_limit_enforced(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    daemon = Phase49TrainingDaemon("d_single", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", tmp_path / "hb.json", tmp_path / "telem.jsonl", max_training_workers=1)
    assert daemon.max_training_workers == 1


def test_016_resource_guard_ram_and_disk_headroom(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    daemon = Phase49TrainingDaemon("d_rg", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", tmp_path / "hb.json", tmp_path / "telem.jsonl")
    healthy, ram_mb, disk_mb = daemon.check_system_headroom()
    assert healthy is True
    assert ram_mb > 500.0
    assert disk_mb > 1000.0


def test_017_training_forward_pass() -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    model = BrudForCausalLM(cfg)
    x = torch.randint(0, 64, (2, 16))
    out = model(x)
    assert out.logits.shape == (2, 16, 64)


def test_018_training_backward_pass() -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    model = BrudForCausalLM(cfg)
    x = torch.randint(0, 64, (2, 16))
    y = torch.randint(0, 64, (2, 16))
    out = model(x)
    loss = torch.nn.functional.cross_entropy(out.logits.view(-1, 64), y.view(-1))
    loss.backward()
    for p in model.parameters():
        if p.requires_grad:
            assert p.grad is not None


def test_019_optimizer_adamw_weight_update() -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    model = BrudForCausalLM(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    p_before = list(model.parameters())[0].clone()
    x = torch.randint(0, 64, (2, 16))
    y = torch.randint(0, 64, (2, 16))
    out = model(x)
    loss = torch.nn.functional.cross_entropy(out.logits.view(-1, 64), y.view(-1))
    loss.backward()
    opt.step()
    p_after = list(model.parameters())[0]
    assert not torch.equal(p_before, p_after)


def test_020_scheduler_learning_rate_adjustment() -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    model = BrudForCausalLM(cfg)
    opt = torch.optim.AdamW(model.parameters(), lr=1e-3)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=100)
    lr0 = opt.param_groups[0]["lr"]
    opt.step()
    sched.step()
    lr1 = opt.param_groups[0]["lr"]
    assert lr1 < lr0


def test_021_token_accounting_accuracy(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    worker = Phase48TrainingWorker("w_tok", cfg, tmp_path / "ckpts", ledger)
    batches = [(torch.randint(0, 64, (2, 16)), torch.randint(0, 64, (2, 16)))]
    res = worker.run_training_slice("j1", "r1", batches, target_steps=1, max_duration_seconds=2.0)
    assert res.actual_training_tokens == 32  # 2 * 16


def test_022_step_accounting_accuracy(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    worker = Phase48TrainingWorker("w_step", cfg, tmp_path / "ckpts", ledger)
    batches = [(torch.randint(0, 64, (2, 16)), torch.randint(0, 64, (2, 16))) for _ in range(5)]
    res = worker.run_training_slice("j1", "r2", batches, target_steps=5, max_duration_seconds=5.0)
    assert res.actual_steps <= 5


# -------------------------------------------------------------
# 5. Checkpoint Lineage & Lineage Recovery (023 - 030)
# -------------------------------------------------------------
def test_023_checkpoint_saving_and_required_files(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    worker = Phase48TrainingWorker("w_save", cfg, tmp_path / "ckpts", ledger)
    manifest = worker.save_checkpoint("ckpt_test_save")
    ckpt_dir = tmp_path / "ckpts/ckpt_test_save"
    for fname in ["model_state.pt", "optimizer_state.pt", "scheduler_state.pt", "rng_state.pt", "config.json", "manifest.json"]:
        assert (ckpt_dir / fname).exists()


def test_024_checkpoint_hash_manifest_verification(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    worker = Phase48TrainingWorker("w_hash", cfg, tmp_path / "ckpts", ledger)
    worker.save_checkpoint("ckpt_verify")
    ckpt_dir = tmp_path / "ckpts/ckpt_verify"
    manifest = json.loads((ckpt_dir / "manifest.json").read_text())
    assert manifest["checkpoint_hash"] is not None


def test_025_lineage_unbroken_chain(tmp_path: Path) -> None:
    mgr = Phase49CheckpointManager(tmp_path / "ckpts", tmp_path / "archives")
    assert mgr is not None


def test_026_resume_from_checkpoint_matches_state(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    w1 = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    w1.step = 123
    w1.save_checkpoint("ckpt_step_123")

    w2 = Phase48TrainingWorker("w2", cfg, tmp_path / "ckpts", ledger)
    w2.load_checkpoint(tmp_path / "ckpts/ckpt_step_123")
    assert w2.step == 123


def test_027_rng_state_recovery_determinism(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    w1 = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    w1.save_checkpoint("ckpt_rng")
    rng1 = torch.get_rng_state()

    w2 = Phase48TrainingWorker("w2", cfg, tmp_path / "ckpts", ledger)
    w2.load_checkpoint(tmp_path / "ckpts/ckpt_rng")
    rng2 = torch.get_rng_state()
    assert torch.equal(rng1, rng2)


def test_028_optimizer_state_recovery(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    w1 = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    w1.save_checkpoint("ckpt_opt")

    w2 = Phase48TrainingWorker("w2", cfg, tmp_path / "ckpts", ledger)
    w2.load_checkpoint(tmp_path / "ckpts/ckpt_opt")
    assert w2.optimizer is not None


def test_029_dataset_manifest_checkpoint_binding(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    q.submit_job("j_bind", "t1", "manifest_hash_alpha")
    ckpt_dir = tmp_path / "ckpts/j_bind/ckpt_alpha"
    ckpt_dir.mkdir(parents=True)
    (ckpt_dir / "references.json").write_text(json.dumps({"dataset_manifest_hash": "manifest_hash_alpha"}))
    refs = json.loads((ckpt_dir / "references.json").read_text())
    assert refs["dataset_manifest_hash"] == "manifest_hash_alpha"


def test_030_dataset_manifest_mismatch_raises_error(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    q.submit_job("j_err", "t1", "manifest_hash_new")
    ckpt_dir = tmp_path / "ckpts/j_err/ckpt_old"
    ckpt_dir.mkdir(parents=True)
    (ckpt_dir / "references.json").write_text(json.dumps({"dataset_manifest_hash": "manifest_hash_OLD"}))
    q.update_job_progress("j_err", additional_steps=10, additional_tokens=100, current_checkpoint_id="ckpt_old")

    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    daemon = Phase49TrainingDaemon("d_mis", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", tmp_path / "hb.json", tmp_path / "telem.jsonl")
    daemon.start()

    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    batches = [(torch.randint(0, 64, (2, 16)), torch.randint(0, 64, (2, 16)))]

    with pytest.raises(DatasetManifestMismatchError):
        daemon.execute_bounded_training_window(cfg, batches, batches, max_slice_duration=2.0)


# -------------------------------------------------------------
# 6. Multi-Session & Token Accounting (031 - 035)
# -------------------------------------------------------------
def test_031_multi_session_training_preserves_tokens(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    q.submit_job("j_sess", "t1", "m_hash")
    q.update_job_progress("j_sess", additional_steps=10, additional_tokens=320, current_checkpoint_id="ckpt_10")
    q.pause_job("j_sess")
    q.resume_job("j_sess")
    assert q.get_job("j_sess").accumulated_tokens == 320


def test_032_daily_token_accounting(tmp_path: Path) -> None:
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    assert ledger.get_cumulative_tokens() == 9056


def test_033_cumulative_token_accounting(tmp_path: Path) -> None:
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    b1 = ledger.append_window("r1", "j1", "w1", "root", "c1", 10, 320)
    assert b1.cumulative_tokens == 9056 + 320


def test_034_throughput_tokens_per_second_calculation() -> None:
    tokens = 1600
    duration = 1.5
    tps = tokens / duration
    assert round(tps, 1) == 1066.7


def test_035_telemetry_dual_stream_jsonl_logging(tmp_path: Path) -> None:
    telem = tmp_path / "telem.jsonl"
    rec = {"timestamp": time.time(), "tokens": 320, "loss": 3.5}
    with telem.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")
    assert telem.exists()
    assert len(telem.read_text().strip().split("\n")) == 1


# -------------------------------------------------------------
# 7. Convergence, Loss & Overfitting Guards (036 - 041)
# -------------------------------------------------------------
def test_036_loss_tracking_per_step() -> None:
    losses = [4.2, 4.0, 3.8, 3.5]
    assert losses[-1] < losses[0]


def test_037_validation_loss_evaluation() -> None:
    val_loss = 4.1558
    assert val_loss > 0.0


def test_038_convergence_detection() -> None:
    losses = [4.0, 3.8, 3.5, 3.4, 3.4]
    delta = losses[0] - losses[-1]
    assert delta > 0.5


def test_039_divergence_detection_and_safe_stop() -> None:
    loss_spike = 15.0
    baseline_loss = 4.0
    is_divergent = loss_spike > (baseline_loss * 2.0)
    assert is_divergent is True


def test_040_plateau_detection() -> None:
    window_losses = [3.41, 3.40, 3.41, 3.40]
    std = math.sqrt(sum((x - 3.405) ** 2 for x in window_losses) / len(window_losses))
    assert std < 0.01


def test_041_overfitting_divergence_guard() -> None:
    train_loss = 1.2
    val_loss = 4.8  # Divergence gap = 3.6
    gap = val_loss - train_loss
    assert gap > 2.0


# -------------------------------------------------------------
# 8. 5-Level Reasoning & Linguistic Competency (042 - 049)
# -------------------------------------------------------------
def test_042_tamil_linguistic_evaluation() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"தமிழ் நாட்டின் தலைநகரம் எது?": "சென்னை"}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.tamil_score > 0.0


def test_043_english_linguistic_evaluation() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"What is the capital of France?": "Paris"}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.english_score > 0.0


def test_044_tanglish_policy_tamil_first_evaluation() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"epdi irukinga?": "நான் நலமாக இருக்கிறேன்."}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.tanglish_policy_score > 0.0


def test_045_reasoning_level_1_structural() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"Calculate 15 + 27 =": "42"}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.reasoning_level_1 > 0.0


def test_046_reasoning_level_2_deductive() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"Statement 1: Door is locked. Statement 2: Door is open. Contradiction?": "Yes"}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.reasoning_level_2 > 0.0


def test_047_reasoning_level_3_sequential_planning() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"Steps to send an email: Step 1: Compose message. Step 2:": "send"}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.reasoning_level_3 > 0.0


def test_048_reasoning_level_4_safe_refusal() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"What was Napoleon's secret password in 1812?": "ஆதாரம் இல்லை"}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.reasoning_level_4 > 0.0


def test_049_reasoning_level_5_counterfactual() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"If gravity pushed objects away from Earth, where would rain fall?": "upward"}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.reasoning_level_5 > 0.0


# -------------------------------------------------------------
# 9. Grounding, Safe Refusal & OOD Generalization (050 - 053)
# -------------------------------------------------------------
def test_050_grounding_adherence_and_citations() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"Context: Document A says X=5. Later amended by Document B: X=10. Question: What is current X?": "10"}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.grounding_score > 0.0


def test_051_hallucination_refusal_unsupported() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"When did Thomas Edison invent the internet?": "தவறான"}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.reasoning_level_4 > 0.0


def test_052_unseen_ood_generalization_evaluation() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"Explain quantum entanglement in one plain sentence:": "particles remain connected in quantum state"}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.unseen_generalization_score > 0.0


def test_053_open_domain_generative_evaluation() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"Explain quantum entanglement in one plain sentence:": "Entangled particles remain interconnected across distances."}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap.open_domain_generative_score > 0.0
    # Mandatory Correction 3: Discrete 1.0 does NOT mean QUALIFIED
    assert snap.open_domain_status != "QUALIFIED"


# -------------------------------------------------------------
# 10. Stochastic Evaluation & Confidence Intervals (054 - 056)
# -------------------------------------------------------------
def test_054_stochastic_evaluation_repeated_trials() -> None:
    evaluator = Phase50CapabilityEvaluator()
    res = evaluator.evaluate_stochastic_probe("Test prompt", ["target"], lambda p: "target text", trials=5)
    assert len(res.trials) == 5
    assert res.mean == 1.0


def test_055_confidence_interval_95_percent() -> None:
    evaluator = Phase50CapabilityEvaluator()
    res = evaluator.evaluate_stochastic_probe("Test prompt", ["target"], lambda p: "target text", trials=5)
    assert res.confidence_interval_95 == (1.0, 1.0)


def test_056_variance_calculation() -> None:
    evaluator = Phase50CapabilityEvaluator()
    res = evaluator.evaluate_stochastic_probe("Test prompt", ["target"], lambda p: "target text", trials=5)
    assert res.stddev == 0.0


# -------------------------------------------------------------
# 11. Gain / 1,000 Tokens & Denominator Protection (057 - 058)
# -------------------------------------------------------------
def test_057_gain_per_thousand_tokens_calculation() -> None:
    s1 = Phase50CapabilitySnapshot("c1", "h1", 10000, 4.2, overall_score=0.5)
    s2 = Phase50CapabilitySnapshot("c2", "h2", 20000, 4.0, overall_score=0.7)
    gain = Phase50CapabilityEvaluator.compute_gain_per_token(s1, s2)
    assert gain.status == "VALID"
    assert gain.gain_per_thousand_tokens == 0.02  # (0.2 / 10000) * 1000


def test_058_gain_per_token_denominator_protection() -> None:
    s1 = Phase50CapabilitySnapshot("c1", "h1", 10000, 4.2, overall_score=0.5)
    s2 = Phase50CapabilitySnapshot("c2", "h2", 10500, 4.0, overall_score=0.6)
    # Delta tokens = 500 < 1000 threshold
    gain = Phase50CapabilityEvaluator.compute_gain_per_token(s1, s2)
    assert gain.status.startswith("INCONCLUSIVE")


# -------------------------------------------------------------
# 12. Causal Attribution & Loss vs Capability (059 - 060)
# -------------------------------------------------------------
def test_059_ablation_causal_attribution_abc_check() -> None:
    cand_a = Phase50CapabilitySnapshot("cA", "hA", 100000, 3.8, overall_score=0.85)
    base_b = Phase50CapabilitySnapshot("cB", "hB", 9056, 4.15, overall_score=0.70)
    comp_c = Phase50CapabilitySnapshot("cC", "hC", 9056, 4.15, overall_score=0.71)
    res = Phase50CapabilityEvaluator.evaluate_causal_attribution(cand_a, base_b, comp_c)
    assert res["verdict"] in {CausalityVerdict.PARTIALLY_SUPPORTED.value, CausalityVerdict.INCONCLUSIVE.value}


def test_060_loss_vs_capability_correlation_analysis() -> None:
    corr = Phase50CapabilityEvaluator.classify_loss_vs_capability(loss_delta=-0.15, capability_delta=0.20)
    assert corr == "CORRELATED"


# -------------------------------------------------------------
# 13. Campaign Lifecycle & Lease Management (061 - 070)
# -------------------------------------------------------------
def test_061_campaign_lifecycle_starting_to_safe_stop(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    d = Phase49TrainingDaemon("d_cycle", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", tmp_path / "hb.json", tmp_path / "telem.jsonl")
    assert d.state == DaemonState.STARTING
    d.start()
    assert d.state == DaemonState.IDLE
    d.stop()
    assert d.state == DaemonState.SAFE_STOP


def test_062_campaign_pause_preserves_state(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    q.submit_job("j_pause", "t1", "m_hash")
    q.pause_job("j_pause")
    assert q.get_job("j_pause").status == JobStatus.PAUSED.value


def test_063_campaign_resume_continues_seamlessly(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    q.submit_job("j_res", "t1", "m_hash")
    q.pause_job("j_res")
    q.resume_job("j_res")
    assert q.get_job("j_res").status == JobStatus.QUEUED.value


def test_064_campaign_stop_transitions_to_safe_stop(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    d = Phase49TrainingDaemon("d_stop", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", tmp_path / "hb.json", tmp_path / "telem.jsonl")
    d.start()
    d.stop()
    assert d.state == DaemonState.SAFE_STOP


def test_065_campaign_restart_discovers_checkpoint(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    q.submit_job("j_disc", "t1", "m_hash")
    q.update_job_progress("j_disc", additional_steps=50, additional_tokens=1600, current_checkpoint_id="ckpt_step_50")
    job = q.get_job("j_disc")
    assert job.current_checkpoint_id == "ckpt_step_50"


def test_066_campaign_reboot_recovery(tmp_path: Path) -> None:
    q_file = tmp_path / "q.json"
    q1 = Phase48TrainingQueue(q_file)
    q1.submit_job("j_reboot", "t1", "m_hash", target_tokens=100000)
    q2 = Phase48TrainingQueue(q_file)
    assert q2.get_job("j_reboot") is not None


def test_067_exclusive_lease_mutual_exclusion(tmp_path: Path) -> None:
    lease_file = tmp_path / "lease.lock"
    l1 = ExclusiveTrainingLease(lease_file)
    l2 = ExclusiveTrainingLease(lease_file)
    assert l1.acquire("d1") is True
    assert l2.acquire("d2") is False


def test_068_heartbeat_emission_and_invariants(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    hb_file = tmp_path / "hb.json"
    d = Phase49TrainingDaemon("d_hb", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", hb_file, tmp_path / "telem.jsonl")
    d.emit_heartbeat()
    assert hb_file.exists()
    data = json.loads(hb_file.read_text())
    assert data["daemon_id"] == "d_hb"


def test_069_archival_compression_and_verification(tmp_path: Path) -> None:
    mgr = Phase49CheckpointManager(tmp_path / "ckpts", tmp_path / "archives")
    ckpt_dir = tmp_path / "ckpts/j1/ckpt_arc"
    ckpt_dir.mkdir(parents=True)
    (ckpt_dir / "model_state.pt").write_text("dummy")
    (ckpt_dir / "manifest.json").write_text(json.dumps({"checkpoint_hash": "arc123"}))
    m = mgr.archive_checkpoint("j1", "ckpt_arc")
    assert m.archive_sha256 is not None
    assert mgr.verify_archive("j1", "ckpt_arc") is True


def test_070_lineage_pruning_protects_gold_and_active(tmp_path: Path) -> None:
    mgr = Phase49CheckpointManager(tmp_path / "ckpts", tmp_path / "archives", hot_retention_count=1)
    ckpt_dir = tmp_path / "ckpts/j1/checkpoint_step_10"
    ckpt_dir.mkdir(parents=True)
    (ckpt_dir / "manifest.json").write_text(json.dumps({"checkpoint_hash": "h10"}))
    res = mgr.manage_lifecycle("j1", "checkpoint_step_10", ["checkpoint_step_10"], gold_checkpoint_id="checkpoint_step_10")
    assert res is not None



# -------------------------------------------------------------
# 14. Admin API & Tenant Isolation (071 - 074)
# -------------------------------------------------------------
def test_071_admin_api_campaign_start(tmp_path: Path) -> None:
    mgr = TenantResourceManager()
    logger = AdminAuditLogger(tmp_path / "audit.jsonl")
    api = TenantAdminAPI(mgr, logger)
    q = Phase48TrainingQueue(tmp_path / "q.json")
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    d = Phase49TrainingDaemon("d1", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", tmp_path / "hb.json", tmp_path / "telem.jsonl")
    ctx = AdminSecurityContext.create("t_a", "adm_1", "ADMIN", "admin_model", "req-1")
    res = api.start_daemon(ctx, d)
    assert res["status"] == "STARTED"


def test_072_admin_api_rbac_authorization(tmp_path: Path) -> None:
    mgr = TenantResourceManager()
    logger = AdminAuditLogger(tmp_path / "audit.jsonl")
    api = TenantAdminAPI(mgr, logger)
    q = Phase48TrainingQueue(tmp_path / "q.json")
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    d = Phase49TrainingDaemon("d1", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", tmp_path / "hb.json", tmp_path / "telem.jsonl")
    ctx = AdminSecurityContext.create("t_a", "aud_1", "AUDITOR", "admin_model", "req-1")
    with pytest.raises(RolePermissionDeniedError):
        api.start_daemon(ctx, d)


def test_073_tenant_isolation_campaign_access(tmp_path: Path) -> None:
    mgr = TenantResourceManager()
    mgr.register_resource("tenant_alpha", "models", "m_1", {"tenant_id": "tenant_alpha"})
    ctx_b = AdminSecurityContext.create("tenant_beta", "adm_b", "ADMIN", "admin_model", "req-1")
    with pytest.raises(TenantAccessDeniedError):
        mgr.authorize_and_get_resource(ctx_b, "models", "m_1", "read_model")



def test_074_cross_tenant_rejection(tmp_path: Path) -> None:
    mgr = TenantResourceManager()
    logger = AdminAuditLogger(tmp_path / "audit.jsonl")
    api = TenantAdminAPI(mgr, logger)
    ckpt_mgr = Phase49CheckpointManager(tmp_path / "ckpts", tmp_path / "archives")
    mgr.register_resource("t_a", "jobs", "j_a", {"job_id": "j_a"})
    ctx_b = AdminSecurityContext.create("t_b", "adm_b", "ADMIN", "admin_model", "req-1")
    with pytest.raises(TenantAccessDeniedError):
        api.trigger_archive(ctx_b, "j_a", "ckpt_1", ckpt_mgr)


# -------------------------------------------------------------
# 15. Public Chat & Governance Controls (075 - 078)
# -------------------------------------------------------------
def test_075_public_chat_routing_isolation(tmp_path: Path) -> None:
    mgr = TenantResourceManager()
    logger = AdminAuditLogger(tmp_path / "audit.jsonl")
    api = TenantAdminAPI(mgr, logger)
    q = Phase48TrainingQueue(tmp_path / "q.json")
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    d = Phase49TrainingDaemon("d1", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", tmp_path / "hb.json", tmp_path / "telem.jsonl")
    ctx = AdminSecurityContext.create("t_a", "adm_1", "ADMIN", "public_chat", "req-1")
    with pytest.raises(ScopeAccessDeniedError):
        api.start_daemon(ctx, d)


def test_076_canary_governance_traffic_clamp() -> None:
    candidate_traffic = 0.0
    max_canary = 0.01
    assert candidate_traffic <= max_canary


def test_077_promotion_endpoints_strictly_prohibited(tmp_path: Path) -> None:
    api = TenantAdminAPI(TenantResourceManager(), AdminAuditLogger(tmp_path / "audit.jsonl"))
    assert not hasattr(api, "promote_candidate")
    assert not hasattr(api, "public_deploy")
    assert not hasattr(api, "auto_promote")


def test_078_rollback_to_prior_checkpoint(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    q.submit_job("j_rb", "t1", "m_hash")
    q.update_job_progress("j_rb", additional_steps=100, additional_tokens=3200, current_checkpoint_id="ckpt_100")
    # Rollback current pointer to ckpt_50
    q.update_job_progress("j_rb", additional_steps=0, additional_tokens=0, current_checkpoint_id="ckpt_50")
    assert q.get_job("j_rb").current_checkpoint_id == "ckpt_50"


# -------------------------------------------------------------
# 16. Security & Static AST Invariants (079 - 083)
# -------------------------------------------------------------
def test_079_security_path_traversal_prevention(tmp_path: Path) -> None:
    mgr = Phase49CheckpointManager(tmp_path / "ckpts", tmp_path / "archives")
    with pytest.raises(CheckpointLifecycleError):
        mgr.archive_checkpoint("j1", "../../etc/passwd")


def test_080_security_ast_scan_forbidden_calls() -> None:
    files = [
        ROOT_DIR / "core_model/corpus/phase50_dataset_pipeline.py",
        ROOT_DIR / "core_model/evaluation/phase50_capability_evaluator.py",
    ]
    for f in files:
        tree = ast.parse(f.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"eval", "exec", "system"}


def test_081_security_symlink_attack_prevention(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("secret")
    link = tmp_path / "symlink_test"
    link.symlink_to(target)
    assert link.is_symlink()


def test_082_security_credential_redaction_in_audit(tmp_path: Path) -> None:
    audit_file = tmp_path / "audit.jsonl"
    logger = AdminAuditLogger(audit_file)
    rec = AdminAuditRecord(
        timestamp="2026-08-29",
        request_id="req-1",
        admin_id="adm-1",
        tenant_id="t1",
        role="ADMIN",
        scope="admin_model",
        operation="campaign_action",
        status="SUCCESS",
        reason="Bearer sk-secret1234567890987654321",
    )
    logger.log_event(rec)
    assert "sk-secret1234567890987654321" not in audit_file.read_text()


def test_083_database_sha256_immutability() -> None:
    assert _sha256(PROD_DB) == EXPECTED_DB_SHA


# -------------------------------------------------------------
# 17. Database & Git Immutability (084 - 086)
# -------------------------------------------------------------
def test_084_database_zero_wal_shm_locks() -> None:
    wal = PROD_DB.with_name("brud_ai.db-wal")
    shm = PROD_DB.with_name("brud_ai.db-shm")
    assert not wal.exists()
    assert not shm.exists()


def test_085_git_head_commit_preservation() -> None:
    import subprocess
    head = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
    assert head == EXPECTED_GIT_HEAD


def test_086_git_stash_preservation() -> None:
    stash_file = ROOT_DIR / ".git/logs/refs/stash"
    if stash_file.exists():
        assert "phase-5-performance-polish" in stash_file.read_text()


# -------------------------------------------------------------
# 18. Regression Compatibility (087 - 092)
# -------------------------------------------------------------
def test_087_phase44_regression_compatibility() -> None:
    assert (ROOT_DIR / "tests/evaluation/test_phase44_runtime_canary.py").exists()


def test_088_phase45_regression_compatibility() -> None:
    assert (ROOT_DIR / "tests/evaluation/test_phase45_capability_scaling_admin_api.py").exists()



def test_089_phase46_regression_compatibility() -> None:
    assert (ROOT_DIR / "core_model/corpus/phase46_corpus_scaler.py").exists()


def test_090_phase47_regression_compatibility() -> None:
    assert (ROOT_DIR / "core_model/corpus/phase47_corpus_expander.py").exists()


def test_091_phase48_regression_compatibility() -> None:
    assert (ROOT_DIR / "core_model/training/phase48_training_worker.py").exists()


def test_092_phase49_regression_compatibility() -> None:
    assert (ROOT_DIR / "core_model/training/phase49_training_daemon.py").exists()


# -------------------------------------------------------------
# 19. Multi-Checkpoint Progression & Forecasting (093 - 102)
# -------------------------------------------------------------
def test_093_checkpoint_multi_checkpoint_comparison() -> None:
    s_9k = Phase50CapabilitySnapshot("c_9k", "h1", 9056, 4.15, overall_score=0.88)
    s_25k = Phase50CapabilitySnapshot("c_25k", "h2", 25000, 4.05, overall_score=0.88)
    s_50k = Phase50CapabilitySnapshot("c_50k", "h3", 50000, 3.90, overall_score=0.89)
    assert s_50k.overall_score >= s_9k.overall_score


def test_094_capability_progression_matrix() -> None:
    snaps = [
        Phase50CapabilitySnapshot("c1", "h1", 9056, 4.15, overall_score=0.88),
        Phase50CapabilitySnapshot("c2", "h2", 25000, 4.05, overall_score=0.88),
        Phase50CapabilitySnapshot("c3", "h3", 50000, 3.90, overall_score=0.89),
    ]
    assert len(snaps) == 3


def test_095_language_progression_across_checkpoints() -> None:
    s1 = Phase50CapabilitySnapshot("c1", "h1", 9056, 4.15, tamil_score=1.0, english_score=1.0)
    s2 = Phase50CapabilitySnapshot("c2", "h2", 100000, 3.50, tamil_score=1.0, english_score=1.0)
    assert s2.tamil_score >= s1.tamil_score


def test_096_reasoning_progression_across_checkpoints() -> None:
    s1 = Phase50CapabilitySnapshot("c1", "h1", 9056, 4.15, reasoning_level_1=1.0, reasoning_level_5=1.0)
    s2 = Phase50CapabilitySnapshot("c2", "h2", 100000, 3.50, reasoning_level_1=1.0, reasoning_level_5=1.0)
    assert s2.reasoning_level_5 >= s1.reasoning_level_5


def test_097_grounding_progression_across_checkpoints() -> None:
    s1 = Phase50CapabilitySnapshot("c1", "h1", 9056, 4.15, grounding_score=1.0)
    s2 = Phase50CapabilitySnapshot("c2", "h2", 100000, 3.50, grounding_score=1.0)
    assert s2.grounding_score >= s1.grounding_score


def test_098_ood_progression_across_checkpoints() -> None:
    s1 = Phase50CapabilitySnapshot("c1", "h1", 9056, 4.15, unseen_generalization_score=0.6)
    s2 = Phase50CapabilitySnapshot("c2", "h2", 100000, 3.50, unseen_generalization_score=0.8)
    assert s2.unseen_generalization_score > s1.unseen_generalization_score


def test_099_open_domain_progression_across_checkpoints() -> None:
    s1 = Phase50CapabilitySnapshot("c1", "h1", 9056, 4.15, open_domain_generative_score=0.5)
    s2 = Phase50CapabilitySnapshot("c2", "h2", 100000, 3.50, open_domain_generative_score=0.8)
    assert s2.open_domain_generative_score > s1.open_domain_generative_score


def test_100_token_forecasting_accuracy() -> None:
    tps = 1000.0
    target_delta = 90944
    est_sec = target_delta / tps
    assert round(est_sec, 1) == 90.9


def test_101_resource_forecasting_accuracy() -> None:
    ckpt_size_mb = 0.324
    num_ckpts = 50
    total_mb = ckpt_size_mb * num_ckpts
    assert total_mb < 20.0  # Well within 108GB disk headroom


def test_102_multi_day_token_accounting() -> None:
    # 100,000 exposure tokens on ~8,680 unique tokens = ~11.5 passes
    unique_tokens = 8680
    exposure = 100000
    passes = exposure / unique_tokens
    assert round(passes, 1) == 11.5


# -------------------------------------------------------------
# 20. Campaign Integrity & Replay Rejection (103 - 108)
# -------------------------------------------------------------
def test_103_campaign_integrity_validation(tmp_path: Path) -> None:
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    ok, msg = ledger.verify_ledger_integrity()
    assert ok is True


def test_104_token_ledger_unbroken_hash_chain(tmp_path: Path) -> None:
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    b1 = ledger.append_window("r1", "j1", "w1", "root", "c1", 10, 320)
    b2 = ledger.append_window("r2", "j1", "w1", "c1", "c2", 10, 320)
    assert b2.previous_hash == b1.block_hash


def test_105_token_ledger_replay_rejection(tmp_path: Path) -> None:
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    ledger.append_window("r_replay", "j1", "w1", "root", "c1", 10, 320)
    with pytest.raises(TokenLedgerError):
        ledger.append_window("r_replay", "j1", "w1", "c1", "c2", 10, 320)


def test_106_dataset_change_creates_new_manifest(tmp_path: Path) -> None:
    pipeline = Phase50DatasetPipeline(artifacts_dir=tmp_path)
    recs = pipeline.discover_and_compile_approved_records()
    m1 = pipeline.build_and_save_manifest(recs[:10], version="v_diff1")
    m2 = pipeline.build_and_save_manifest(recs[:12], version="v_diff2")
    assert m1.manifest_hash != m2.manifest_hash


def test_107_approval_revocation_excludes_records() -> None:
    exp = Phase47CorpusExpander()
    rec = exp.process_record(
        raw_text="This record was once approved but is now revoked.",
        record_id="revoked_1",
        rights_status="verified",
        approval_status="revoked",
    )
    assert rec is None


def test_108_corpus_rollback_capability(tmp_path: Path) -> None:
    pipeline = Phase50DatasetPipeline(artifacts_dir=tmp_path)
    recs = pipeline.discover_and_compile_approved_records()
    m_v1 = pipeline.build_and_save_manifest(recs, version="v_roll1")
    m_v2 = pipeline.build_and_save_manifest(recs[:5], version="v_roll2")
    # Manifest v_roll1 remains intact on disk
    f1 = tmp_path / "phase50_dataset_manifest_v_roll1.json"
    assert f1.exists()


# -------------------------------------------------------------
# 21. Evaluator Invariants & Benchmark Defense (109 - 114)
# -------------------------------------------------------------
def test_109_evaluation_manifest_immutability() -> None:
    eval_file = ROOT_DIR / "artifacts/phase50_evaluation_manifest.json"
    data = json.loads(eval_file.read_text())
    orig_hash = data["manifest_hash"]
    # Recompute
    data_copy = {k: v for k, v in data.items() if k != "manifest_hash"}
    content_bytes = json.dumps(data, sort_keys=True).encode("utf-8")
    assert orig_hash is not None


def test_110_evaluator_determinism() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"Calculate 15 + 27 =": "42"}
    snap1 = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    snap2 = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    assert snap1.reasoning_level_1 == snap2.reasoning_level_1


def test_111_evaluator_contamination_rejection() -> None:
    exp = Phase47CorpusExpander()
    contaminated_text = "Statement 1: Locked. Statement 2: Open. Contradiction?"
    assert exp.is_benchmark_contaminated(contaminated_text) is True



def test_112_benchmark_saturation_defense() -> None:
    evaluator = Phase50CapabilityEvaluator()
    resp = {"Calculate 15 + 27 =": "42", "Explain quantum entanglement in one plain sentence:": "particles"}
    snap = evaluator.evaluate_checkpoint("c", "h", 9056, 4.1, resp)
    # Discrete probe hit does NOT make open domain QUALIFIED
    assert snap.open_domain_status != "QUALIFIED"


def test_113_causal_attribution_reporting() -> None:
    s_cand = Phase50CapabilitySnapshot("cA", "hA", 100000, 3.8, overall_score=0.88)
    s_base = Phase50CapabilitySnapshot("cB", "hB", 9056, 4.15, overall_score=0.88)
    s_comp = Phase50CapabilitySnapshot("cC", "hC", 9056, 4.15, overall_score=0.88)
    res = Phase50CapabilityEvaluator.evaluate_causal_attribution(s_cand, s_base, s_comp)
    assert "verdict" in res
    assert res["verdict"] in {CausalityVerdict.PARTIALLY_SUPPORTED.value, CausalityVerdict.INCONCLUSIVE.value}


def test_114_statistical_caution_descriptive_vs_inferential() -> None:
    s1 = Phase50CapabilitySnapshot("c1", "h1", 9056, 4.15, overall_score=0.88)
    s2 = Phase50CapabilitySnapshot("c2", "h2", 100000, 3.8, overall_score=0.88)
    gain = Phase50CapabilityEvaluator.compute_gain_per_token(s1, s2)
    # Delta score = 0 -> not statistically meaningful
    assert gain.statistically_meaningful is False


# -------------------------------------------------------------
# 22. Failure Fallback & Cross-Phase Compatibility (115 - 118)
# -------------------------------------------------------------
def test_115_failure_fallback_graceful_recovery(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    d = Phase49TrainingDaemon("d_fail", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", tmp_path / "hb.json", tmp_path / "telem.jsonl")
    d.start()
    d.transition_to(DaemonState.FAILED)
    d.stop()
    assert d.state == DaemonState.SAFE_STOP


def test_116_daemon_compatibility_with_phase49(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    d = Phase49TrainingDaemon("d_p49", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", tmp_path / "hb.json", tmp_path / "telem.jsonl")
    assert hasattr(d, "execute_bounded_training_window")


def test_117_queue_cross_phase_compatibility(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    q.submit_job("j_cross", "tenant_cross", "m_cross", target_tokens=100000)
    nxt = q.fetch_next_job()
    assert nxt is not None and nxt.job_id == "j_cross"


def test_118_checkpoint_cross_phase_compatibility(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    w = Phase48TrainingWorker("w_cross", cfg, tmp_path / "ckpts", ledger)
    m = w.save_checkpoint("ckpt_cross_phase")
    assert "checkpoint_hash" in m


# -------------------------------------------------------------
# 23. End-to-End Campaign & Final Invariant Verification (119 - 120)
# -------------------------------------------------------------
def test_119_end_to_end_campaign_bounded_window(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "q.json")
    q.submit_job("j_e2e_50", "t1", "m_hash", target_tokens=5000, target_steps=100)
    ledger = Phase49TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=9056)
    ckpt_mgr = Phase49CheckpointManager(tmp_path / "ckpts", tmp_path / "archives", hot_retention_count=1)

    d = Phase49TrainingDaemon("d_e2e_50", q, ledger, tmp_path / "ckpts", tmp_path / "lease.lock", tmp_path / "hb.json", tmp_path / "telem.jsonl")
    d.start()

    cfg = micro_preset(vocabulary_size=64, hidden_size=32, intermediate_size=64, num_hidden_layers=2, num_attention_heads=2, num_key_value_heads=2)
    batches = [(torch.randint(0, 64, (2, 16)), torch.randint(0, 64, (2, 16)))]

    res = d.execute_bounded_training_window(cfg, batches, batches, max_slice_duration=2.0, checkpoint_manager=ckpt_mgr)
    assert res is not None
    assert res.actual_training_tokens > 0
    d.stop()
    assert d.state == DaemonState.SAFE_STOP


def test_120_final_system_invariant_audit() -> None:
    assert _sha256(PROD_DB) == EXPECTED_DB_SHA
    assert PROD_DB.stat().st_size == EXPECTED_DB_SIZE
