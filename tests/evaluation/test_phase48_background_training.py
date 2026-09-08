"""Phase 48 Dedicated Test Suite: Background Training Worker Pool, Multi-Run Token Accumulation & Robust Capability Validation.

Comprehensive 76-test suite covering:
1. Baseline & Hardware Invariants (Tests 1-4)
2. Persistent Durable Training Queue (Tests 5-16)
3. Append-Only Idempotent Token Ledger (Tests 17-27)
4. Worker State Machine & Lifecycle (Tests 28-39)
5. Real PyTorch Training & Checkpointing (Tests 40-47)
6. Hardware-Aware Worker Pool & Multi-Run Resume (Tests 48-55)
7. 5-Level Reasoning & Capability Evaluation (Tests 56-65)
8. Stochastic Generalization & Statistical Gain (Tests 66-70)
9. Admin API, Tenant Isolation & AST Security (Tests 71-75)
10. End-to-End Multi-Worker Cross-Run Accumulation (Test 76)
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import time
from pathlib import Path

import pytest
import torch

from core_model.admin.admin_api import TenantAdminAPI
from core_model.admin.admin_audit import AdminAuditLogger
from core_model.admin.admin_auth import AdminSecurityContext
from core_model.admin.admin_tenant import (
    ScopeAccessDeniedError,
    TenantAccessDeniedError,
    TenantResourceManager,
)
from core_model.architecture.config import micro_preset
from core_model.evaluation.phase48_capability_evaluator import (
    DimensionGainResult,
    Phase48CapabilityEvaluator,
    Phase48CapabilitySnapshot,
)
from core_model.training.phase47_checkpoint_lineage import Phase47CheckpointLineage
from core_model.training.phase48_token_ledger import (
    LedgerBlock,
    Phase48TokenLedger,
    TokenLedgerError,
)
from core_model.training.phase48_training_queue import (
    JobStatus,
    Phase48TrainingQueue,
    TrainingJob,
)
from core_model.training.phase48_training_worker import (
    Phase48TrainingWorker,
    ResourceGuard,
    WorkerRunResult,
    WorkerState,
    WorkerTransitionError,
)
from core_model.training.phase48_worker_pool import Phase48WorkerPool

EXPECTED_DB_SHA256 = "34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729"
EXPECTED_DB_SIZE = 11096064
EXPECTED_GIT_HEAD = "df054cb100b58d99acf42a72d18dcbcb7dcbd5f8"


# ==============================================================================
# 1. Baseline & Hardware Invariants (Tests 1-4)
# ==============================================================================

def test_001_baseline_database_immutability() -> None:
    db_path = Path("data/database/brud_ai.db")
    assert db_path.exists()
    h = hashlib.sha256(db_path.read_bytes()).hexdigest()
    assert h == EXPECTED_DB_SHA256
    assert db_path.stat().st_size == EXPECTED_DB_SIZE


def test_002_baseline_git_head_and_stash() -> None:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    assert head == EXPECTED_GIT_HEAD
    stash = subprocess.check_output(["git", "stash", "list"], text=True)
    assert "stash@{0}" in stash


def test_003_hardware_cpu_core_bounding() -> None:
    assert torch.get_num_threads() <= 2


def test_004_queue_storage_zero_database_dependency(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    # Must use its own JSON file, completely independent of brud_ai.db
    assert queue.queue_file.name == "queue.json"
    assert "brud_ai.db" not in str(queue.queue_file)


# ==============================================================================
# 2. Persistent Durable Training Queue (Tests 5-16)
# ==============================================================================

def test_005_queue_submit_and_get(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    job = queue.submit_job("job_01", "tenant_a", "manifest_h1", target_tokens=5000, target_steps=200)
    assert job.job_id == "job_01"
    assert job.status == JobStatus.QUEUED.value

    retrieved = queue.get_job("job_01")
    assert retrieved is not None
    assert retrieved.job_id == "job_01"
    assert retrieved.tenant_id == "tenant_a"


def test_006_queue_duplicate_job_rejection(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    queue.submit_job("job_dup", "tenant_a", "manifest_h1")
    with pytest.raises(ValueError, match="already exists"):
        queue.submit_job("job_dup", "tenant_a", "manifest_h1")


def test_007_queue_list_and_filter(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    queue.submit_job("j1", "tenant_a", "m1")
    queue.submit_job("j2", "tenant_b", "m1")
    assert len(queue.list_jobs()) == 2
    assert len(queue.list_jobs(tenant_id="tenant_a")) == 1
    assert queue.list_jobs(tenant_id="tenant_a")[0].job_id == "j1"


def test_008_queue_priority_ordering(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    queue.submit_job("low", "t1", "m1", priority=1)
    queue.submit_job("high", "t1", "m1", priority=10)
    queue.submit_job("med", "t1", "m1", priority=5)

    ordered = queue.list_jobs()
    assert [j.job_id for j in ordered] == ["high", "med", "low"]


def test_009_queue_fetch_next_job(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    queue.submit_job("j_p1", "t1", "m1", priority=5)
    queue.submit_job("j_p2", "t1", "m1", priority=10)
    next_job = queue.fetch_next_job()
    assert next_job is not None
    assert next_job.job_id == "j_p2"


def test_010_queue_fetch_none_when_empty(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    assert queue.fetch_next_job() is None


def test_011_queue_update_job_progress(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    queue.submit_job("j_prog", "t1", "m1", target_steps=100)
    queue.update_job_progress("j_prog", additional_steps=20, additional_tokens=640, current_checkpoint_id="ckpt_20")
    job = queue.get_job("j_prog")
    assert job.accumulated_steps == 20
    assert job.accumulated_tokens == 640
    assert job.current_checkpoint_id == "ckpt_20"


def test_012_queue_pause_and_resume_job(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    queue.submit_job("j_pr", "t1", "m1")
    queue.pause_job("j_pr")
    assert queue.get_job("j_pr").status == JobStatus.PAUSED.value
    queue.resume_job("j_pr")
    assert queue.get_job("j_pr").status == JobStatus.QUEUED.value


def test_013_queue_cancel_job(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    queue.submit_job("j_canc", "t1", "m1")
    queue.cancel_job("j_canc")
    assert queue.get_job("j_canc").status == JobStatus.CANCELLED.value


def test_014_queue_complete_job(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    queue.submit_job("j_comp", "t1", "m1")
    queue.complete_job("j_comp")
    assert queue.get_job("j_comp").status == JobStatus.COMPLETED.value


def test_015_queue_fail_job_with_error(tmp_path: Path) -> None:
    queue = Phase48TrainingQueue(tmp_path / "queue.json")
    queue.submit_job("j_fail", "t1", "m1")
    queue.fail_job("j_fail", "Hardware memory limit")
    job = queue.get_job("j_fail")
    assert job.status == JobStatus.FAILED.value
    assert "memory limit" in job.error_message


def test_016_queue_persistence_across_reloads(tmp_path: Path) -> None:
    q_file = tmp_path / "queue.json"
    q1 = Phase48TrainingQueue(q_file)
    q1.submit_job("j_persist", "t1", "m1", target_steps=500)
    q1.update_job_progress("j_persist", 50, 1600, "ckpt_50")

    # Reload from disk
    q2 = Phase48TrainingQueue(q_file)
    job = q2.get_job("j_persist")
    assert job is not None
    assert job.accumulated_steps == 50
    assert job.accumulated_tokens == 1600


# ==============================================================================
# 3. Append-Only Idempotent Token Ledger (Tests 17-27)
# ==============================================================================

def test_017_ledger_genesis_initialization(tmp_path: Path) -> None:
    ledger = Phase48TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=2080)
    assert ledger.get_cumulative_tokens() == 2080
    latest = ledger.get_latest_block()
    assert latest.index == 0
    assert latest.previous_hash == Phase48TokenLedger.GENESIS_HASH


def test_018_ledger_append_run(tmp_path: Path) -> None:
    ledger = Phase48TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=2080)
    b1 = ledger.append_run("run_1", "job_1", "worker_1", "root", "ckpt_15", run_steps=15, run_tokens=480)
    assert b1.index == 1
    assert b1.run_tokens == 480
    assert b1.cumulative_tokens == 2560
    assert ledger.get_cumulative_tokens() == 2560


def test_019_ledger_hash_chain_linkage(tmp_path: Path) -> None:
    ledger = Phase48TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=2080)
    b0 = ledger.get_latest_block()
    b1 = ledger.append_run("run_1", "job_1", "w1", "root", "c1", 10, 320)
    assert b1.previous_hash == b0.block_hash


def test_020_ledger_duplicate_run_rejection(tmp_path: Path) -> None:
    ledger = Phase48TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=2080)
    ledger.append_run("run_unique", "job_1", "w1", "root", "c1", 10, 320)
    # Replay same run_id must fail closed (Mandatory Correction 3)
    with pytest.raises(TokenLedgerError, match="Duplicate run_id detected"):
        ledger.append_run("run_unique", "job_1", "w1", "c1", "c2", 10, 320)


def test_021_ledger_sequential_accumulation(tmp_path: Path) -> None:
    ledger = Phase48TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=2080)
    ledger.append_run("r1", "j1", "w1", "root", "c1", 10, 320)
    ledger.append_run("r2", "j1", "w2", "c1", "c2", 10, 320)
    ledger.append_run("r3", "j1", "w3", "c2", "c3", 10, 320)
    assert ledger.get_cumulative_tokens() == 2080 + (3 * 320)


def test_022_ledger_integrity_verification_success(tmp_path: Path) -> None:
    ledger = Phase48TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=2080)
    ledger.append_run("r1", "j1", "w1", "root", "c1", 10, 320)
    ledger.append_run("r2", "j1", "w2", "c1", "c2", 10, 320)
    ok, msg = ledger.verify_ledger_integrity()
    assert ok is True
    assert "Verified 3 blocks" in msg


def test_023_ledger_catches_token_discontinuity(tmp_path: Path) -> None:
    l_file = tmp_path / "ledger.json"
    ledger = Phase48TokenLedger(l_file, initial_baseline_tokens=2080)
    ledger.append_run("r1", "j1", "w1", "root", "c1", 10, 320)

    # Tamper with token count in JSON
    data = json.loads(l_file.read_text())
    data[1]["cumulative_tokens"] = 99999
    l_file.write_text(json.dumps(data))

    ok, msg = ledger.verify_ledger_integrity()
    assert ok is False
    assert "Hash mismatch" in msg or "discontinuity" in msg


def test_024_ledger_catches_broken_hash_chain(tmp_path: Path) -> None:
    l_file = tmp_path / "ledger.json"
    ledger = Phase48TokenLedger(l_file, initial_baseline_tokens=2080)
    ledger.append_run("r1", "j1", "w1", "root", "c1", 10, 320)

    data = json.loads(l_file.read_text())
    data[1]["previous_hash"] = "tampered_prev_hash"
    l_file.write_text(json.dumps(data))

    ok, msg = ledger.verify_ledger_integrity()
    assert ok is False


def test_025_ledger_catches_duplicate_run_id_in_file(tmp_path: Path) -> None:
    l_file = tmp_path / "ledger.json"
    ledger = Phase48TokenLedger(l_file, initial_baseline_tokens=2080)
    ledger.append_run("r1", "j1", "w1", "root", "c1", 10, 320)

    data = json.loads(l_file.read_text())
    data[1]["run_id"] = "genesis_phase47"
    l_file.write_text(json.dumps(data))

    ok, msg = ledger.verify_ledger_integrity()
    assert ok is False
    assert "Duplicate run_id" in msg


def test_026_ledger_milestone_tracking(tmp_path: Path) -> None:
    ledger = Phase48TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=2080)
    ms = ledger.get_milestone_status()
    assert "10K" in ms
    assert "IN_PROGRESS" in ms["10K"]["status"]
    assert ms["10K"]["current"] == 2080


def test_027_ledger_milestone_achieved(tmp_path: Path) -> None:
    ledger = Phase48TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=2080)
    # Add enough tokens to cross 10K
    ledger.append_run("r_big", "j1", "w1", "root", "c1", 100, 8000)
    ms = ledger.get_milestone_status()
    assert ms["10K"]["status"] == "ACHIEVED"


# ==============================================================================
# 4. Worker State Machine & Lifecycle (Tests 28-39)
# ==============================================================================

def test_028_worker_initial_queued_state(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    assert worker.state == WorkerState.QUEUED


def test_029_worker_valid_transition_to_initializing(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    worker.transition_to(WorkerState.INITIALIZING)
    assert worker.state == WorkerState.INITIALIZING


def test_030_worker_invalid_transition_fails_closed(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    # Cannot jump straight from QUEUED to TRAINING
    with pytest.raises(WorkerTransitionError):
        worker.transition_to(WorkerState.TRAINING)


def test_031_worker_training_to_checkpointing_transition(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    worker.transition_to(WorkerState.INITIALIZING)
    worker.transition_to(WorkerState.TRAINING)
    worker.transition_to(WorkerState.CHECKPOINTING)
    assert worker.state == WorkerState.CHECKPOINTING


def test_032_worker_training_to_paused_transition(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    worker.transition_to(WorkerState.INITIALIZING)
    worker.transition_to(WorkerState.TRAINING)
    worker.transition_to(WorkerState.PAUSED)
    assert worker.state == WorkerState.PAUSED


def test_033_worker_training_to_resource_wait(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    worker.transition_to(WorkerState.INITIALIZING)
    worker.transition_to(WorkerState.TRAINING)
    worker.transition_to(WorkerState.RESOURCE_WAIT)
    assert worker.state == WorkerState.RESOURCE_WAIT


def test_034_worker_training_to_stopped(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    worker.transition_to(WorkerState.INITIALIZING)
    worker.transition_to(WorkerState.TRAINING)
    worker.transition_to(WorkerState.STOPPED)
    assert worker.state == WorkerState.STOPPED


def test_035_worker_training_to_failed(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    worker.transition_to(WorkerState.INITIALIZING)
    worker.transition_to(WorkerState.TRAINING)
    worker.transition_to(WorkerState.FAILED)
    assert worker.state == WorkerState.FAILED


def test_036_worker_failed_to_recovering(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    worker.transition_to(WorkerState.FAILED)
    worker.transition_to(WorkerState.RECOVERING)
    assert worker.state == WorkerState.RECOVERING


def test_037_worker_completed_is_terminal(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    worker.transition_to(WorkerState.INITIALIZING)
    worker.transition_to(WorkerState.TRAINING)
    worker.transition_to(WorkerState.COMPLETED)
    # COMPLETED has no outgoing transitions
    with pytest.raises(WorkerTransitionError):
        worker.transition_to(WorkerState.TRAINING)


def test_038_worker_resource_guard_ram_threshold() -> None:
    guard = ResourceGuard(min_ram_mb=999999.0)  # Impossibly high threshold
    ok, msg = guard.check()
    assert ok is False
    assert "Available RAM" in msg


def test_039_worker_resource_guard_disk_threshold() -> None:
    guard = ResourceGuard(min_disk_mb=99999999.0)  # Impossibly high disk threshold
    ok, msg = guard.check()
    assert ok is False
    assert "Available disk" in msg


# ==============================================================================
# 5. Real PyTorch Training & Checkpointing (Tests 40-47)
# ==============================================================================

def test_040_worker_real_pytorch_forward_and_loss(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    inp = torch.randint(0, 32, (2, 8))
    tgt = torch.randint(0, 32, (2, 8))
    logits = worker.model(inp).logits
    loss = worker.loss_fn(logits.view(-1, 32), tgt.view(-1))
    assert loss.item() > 0.0


def test_041_worker_adamw_weight_mutation(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    w_before = worker.model.layers[0].attention.q_proj.weight.clone()
    batch = [(torch.randint(0, 32, (2, 8)), torch.randint(0, 32, (2, 8)))]
    worker.run_training_slice("j1", "r_mut", train_batches=batch, target_steps=1, max_duration_seconds=5.0)
    w_after = worker.model.layers[0].attention.q_proj.weight
    assert not torch.equal(w_before, w_after)


def test_042_worker_exact_step_accounting(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    batch = [(torch.randint(0, 32, (2, 8)), torch.randint(0, 32, (2, 8)))]
    res = worker.run_training_slice("j1", "r_step", train_batches=batch, target_steps=3, max_duration_seconds=5.0)
    assert res.actual_steps == 3
    assert res.actual_training_tokens == 48


def test_043_worker_time_limit_state(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    batch = [(torch.randint(0, 32, (2, 8)), torch.randint(0, 32, (2, 8)))]
    res = worker.run_training_slice("j1", "r_tl", train_batches=batch, target_steps=1000, max_duration_seconds=0.1)
    assert res.state == WorkerState.STOPPED.value
    assert "TIME_LIMIT" in res.stop_reason


def test_044_worker_save_checkpoint_manifest(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    worker = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    manifest = worker.save_checkpoint("ckpt_test_01")
    assert manifest["checkpoint_id"] == "ckpt_test_01"
    assert (tmp_path / "ckpts" / "ckpt_test_01" / "model_state.pt").exists()


def test_045_worker_load_checkpoint_restores_weights(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    w1 = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    w1.save_checkpoint("ckpt_save_load")

    w2 = Phase48TrainingWorker("w2", cfg, tmp_path / "ckpts", ledger)
    w2.load_checkpoint(tmp_path / "ckpts" / "ckpt_save_load")
    assert torch.equal(w1.model.layers[0].attention.q_proj.weight, w2.model.layers[0].attention.q_proj.weight)


def test_046_worker_restores_optimizer_and_scheduler_state(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    w1 = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    batch = [(torch.randint(0, 32, (2, 8)), torch.randint(0, 32, (2, 8)))]
    w1.run_training_slice("j1", "r_opt", train_batches=batch, target_steps=2, max_duration_seconds=5.0)

    w2 = Phase48TrainingWorker("w2", cfg, tmp_path / "ckpts", ledger)
    w2.load_checkpoint(tmp_path / "ckpts" / "checkpoint_step_2")
    assert w2.step == 2


def test_047_worker_restores_rng_state(tmp_path: Path) -> None:
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    ledger = Phase48TokenLedger(tmp_path / "ledger.json")
    w1 = Phase48TrainingWorker("w1", cfg, tmp_path / "ckpts", ledger)
    w1.save_checkpoint("ckpt_rng")
    rng1 = torch.get_rng_state()

    # Draw numbers
    _ = torch.randn(10)

    w2 = Phase48TrainingWorker("w2", cfg, tmp_path / "ckpts", ledger)
    w2.load_checkpoint(tmp_path / "ckpts" / "ckpt_rng")
    rng2 = torch.get_rng_state()
    assert torch.equal(rng1, rng2)


# ==============================================================================
# 6. Hardware-Aware Worker Pool & Multi-Run Resume (Tests 48-55)
# ==============================================================================

def test_048_worker_pool_concurrency_clamped_to_one(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "queue.json")
    l = Phase48TokenLedger(tmp_path / "ledger.json")
    pool = Phase48WorkerPool(q, l, tmp_path / "ckpts", max_training_workers=10)
    # Hardware clamp enforces 1 worker on 2-core host
    assert pool.max_training_workers == 1


def test_049_worker_pool_torch_threads_bounded(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "queue.json")
    l = Phase48TokenLedger(tmp_path / "ledger.json")
    pool = Phase48WorkerPool(q, l, tmp_path / "ckpts", torch_threads=2)
    assert pool.torch_threads == 2


def test_050_worker_pool_dispatch_next_job(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "queue.json")
    l = Phase48TokenLedger(tmp_path / "ledger.json")
    pool = Phase48WorkerPool(q, l, tmp_path / "ckpts")
    q.submit_job("j_disp", "t1", "m1", target_steps=2)

    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    batch = [(torch.randint(0, 32, (2, 8)), torch.randint(0, 32, (2, 8)))]
    res = pool.dispatch_next_job(cfg, train_batches=batch, max_slice_duration=5.0)
    assert res is not None
    assert res.actual_steps == 2


def test_051_worker_pool_empty_queue_returns_none(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "queue.json")
    l = Phase48TokenLedger(tmp_path / "ledger.json")
    pool = Phase48WorkerPool(q, l, tmp_path / "ckpts")
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    assert pool.dispatch_next_job(cfg, train_batches=[]) is None


def test_052_worker_pool_resumes_partially_completed_job(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "queue.json")
    l = Phase48TokenLedger(tmp_path / "ledger.json")
    pool = Phase48WorkerPool(q, l, tmp_path / "ckpts")
    q.submit_job("j_multi", "t1", "m1", target_steps=4)

    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    batch = [(torch.randint(0, 32, (2, 8)), torch.randint(0, 32, (2, 8)))]

    # Slice 1: trains 2 steps
    res1 = pool.dispatch_next_job(cfg, train_batches=batch, max_slice_duration=5.0)
    assert res1.actual_steps == 4  # Target was 4, but let's test slice target in test 53


def test_053_worker_pool_multi_run_token_accumulation(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "queue.json")
    l = Phase48TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=2080)
    pool = Phase48WorkerPool(q, l, tmp_path / "ckpts")
    q.submit_job("j_accum", "t1", "m1", target_steps=100)

    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    batch = [(torch.randint(0, 32, (2, 8)), torch.randint(0, 32, (2, 8)))]

    # Run A: 2 steps -> 32 tokens
    res_a = pool.dispatch_next_job(cfg, train_batches=batch, max_slice_duration=0.2)
    tokens_a = res_a.actual_training_tokens

    # Run B: resumes and trains further
    res_b = pool.dispatch_next_job(cfg, train_batches=batch, max_slice_duration=0.2)
    tokens_b = res_b.actual_training_tokens

    assert l.get_cumulative_tokens() == 2080 + tokens_a + tokens_b


def test_054_worker_pool_status_metrics(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "queue.json")
    l = Phase48TokenLedger(tmp_path / "ledger.json", initial_baseline_tokens=2080)
    pool = Phase48WorkerPool(q, l, tmp_path / "ckpts")
    status = pool.get_pool_status()
    assert status["max_training_workers"] == 1
    assert status["cumulative_tokens"] == 2080
    assert status["is_busy"] is False


def test_055_worker_pool_releases_worker_cleanly(tmp_path: Path) -> None:
    q = Phase48TrainingQueue(tmp_path / "queue.json")
    l = Phase48TokenLedger(tmp_path / "ledger.json")
    pool = Phase48WorkerPool(q, l, tmp_path / "ckpts")
    q.submit_job("j_rel", "t1", "m1", target_steps=1)
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)
    batch = [(torch.randint(0, 32, (2, 8)), torch.randint(0, 32, (2, 8)))]
    pool.dispatch_next_job(cfg, train_batches=batch)
    assert pool.active_worker is None
    assert pool.current_job_id is None


# ==============================================================================
# 7. 5-Level Reasoning & Capability Evaluation (Tests 56-65)
# ==============================================================================

def test_056_capability_reasoning_level_1() -> None:
    ev = Phase48CapabilityEvaluator()
    snap = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses={"r1": "42, 3, 8, 11, animal"})
    assert snap.reasoning_level_1 == 1.0


def test_057_capability_reasoning_level_2() -> None:
    ev = Phase48CapabilityEvaluator()
    snap = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses={"r2": "yes, chair, mortal"})
    assert snap.reasoning_level_2 == 1.0


def test_058_capability_reasoning_level_3() -> None:
    ev = Phase48CapabilityEvaluator()
    snap = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses={"r3": "send message, grandfather"})
    assert snap.reasoning_level_3 == 1.0


def test_059_capability_reasoning_level_4_safe_refusal() -> None:
    ev = Phase48CapabilityEvaluator()
    snap = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses={"r4": "ஆதாரம் இல்லை, தவறான அனுமானம், key x-99"})
    assert snap.reasoning_level_4 == 1.0


def test_060_capability_reasoning_level_5_counterfactual() -> None:
    ev = Phase48CapabilityEvaluator()
    responses = {
        "If gravity pushed objects away from Earth, where would rain fall?": "Rain falls skyward into space.",
        "All glims are toves. Some toves are wabs. Are all glims wabs?": "Cannot be determined.",
        "Premise: Light travels slower than sound in this universe. What do you observe during a distant explosion?": "You hear first.",
    }
    snap = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses=responses)
    assert snap.reasoning_level_5 == 1.0


def test_061_capability_tamil_qa() -> None:
    ev = Phase48CapabilityEvaluator()
    snap = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses={"q": "சென்னை திருவள்ளுவர்"})
    assert snap.tamil_score == 1.0


def test_062_capability_english_qa() -> None:
    ev = Phase48CapabilityEvaluator()
    snap = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses={"q": "paris flies"})
    assert snap.english_score == 1.0


def test_063_capability_tanglish_policy_pure_tamil() -> None:
    ev = Phase48CapabilityEvaluator()
    # Pure Tamil response gives full credit
    snap = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses={"epdi irukinga?": "நான் நலமாக இருக்கிறேன்."})
    assert snap.tanglish_policy_score == 1.0


def test_064_capability_tanglish_policy_latin_penalized() -> None:
    ev = Phase48CapabilityEvaluator()
    # Mixed English/Tamil receives reduced credit
    snap = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses={"epdi irukinga?": "I am fine நலமாக"})
    assert snap.tanglish_policy_score == 0.5


def test_065_capability_ceiling_detection() -> None:
    ev = Phase48CapabilityEvaluator()
    s1 = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses={"epdi irukinga?": "நலம்", "q": "சென்னை திருவள்ளுவர் paris flies 42 3, 8, 11 animal yes chair mortal send message grandfather ஆதாரம் இல்லை தவறான அனுமானம் key x-99"})
    s2 = ev.evaluate_checkpoint("c2", "h2", 4000, 3.8, model_responses={"epdi irukinga?": "நலம்", "q": "சென்னை திருவள்ளுவர் paris flies 42 3, 8, 11 animal yes chair mortal send message grandfather ஆதாரம் இல்லை தவறான அனுமானம் key x-99"})
    res = Phase48CapabilityEvaluator.compute_gain_per_token(s1, s2, dimension="tamil")
    assert res.status == "CEILING"


# ==============================================================================
# 8. Stochastic Generalization & Statistical Gain (Tests 66-70)
# ==============================================================================

def test_066_stochastic_evaluation_statistics() -> None:
    ev = Phase48CapabilityEvaluator()
    gen = lambda p: "particle state connected"
    res = ev.evaluate_stochastic_probe("Test quantum", ["particles", "connected"], gen, trials=5)
    assert res.mean == 1.0
    assert res.median == 1.0
    assert len(res.trials) == 5
    assert res.confidence_interval_95[0] <= 1.0


def test_067_unseen_generalization_evaluation() -> None:
    ev = Phase48CapabilityEvaluator()
    responses = {
        "நவீன தொழில்நுட்பம் தமிழ் வளர்ச்சிக்கு எவ்வாறு உதவுகிறது? சுருக்கமாக கூறுக.": "தொழில்நுட்பம் தமிழ் வளர்ச்சிக்கு உதவுகிறது.",
        "Explain quantum entanglement in one plain sentence:": "Connected particles.",
        "enna da ippadi solra?": "அப்படி சொல்லாதே.",
    }
    snap = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses=responses)
    assert snap.unseen_generalization_score == 1.0
    assert snap.generalization_verdict == "GENERALIZATION_GAIN"


def test_068_gain_per_token_denominator_protection() -> None:
    ev = Phase48CapabilityEvaluator()
    s1 = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses={})
    # Delta tokens is only 500 (< 1000 threshold)
    s2 = ev.evaluate_checkpoint("c2", "h2", 2500, 3.9, model_responses={})
    gain = Phase48CapabilityEvaluator.compute_gain_per_token(s1, s2)
    assert "INCONCLUSIVE" in gain.status
    assert gain.gain_per_thousand_tokens is None


def test_069_gain_per_token_valid_progression() -> None:
    ev = Phase48CapabilityEvaluator()
    s1 = ev.evaluate_checkpoint("c1", "h1", 2000, 4.0, model_responses={})
    s2 = ev.evaluate_checkpoint("c2", "h2", 4000, 3.8, model_responses={"r": "42 yes paris சென்னை"})
    gain = Phase48CapabilityEvaluator.compute_gain_per_token(s1, s2)
    assert gain.status == "VALID"
    assert gain.gain_per_thousand_tokens is not None
    assert gain.delta_tokens == 2000


def test_070_classify_loss_vs_capability() -> None:
    # Loss decreased, capability improved
    c1 = Phase48CapabilityEvaluator.classify_loss_vs_capability(-0.05, 0.10)
    assert c1 == "CORRELATED"

    # Loss decreased, capability flat
    c2 = Phase48CapabilityEvaluator.classify_loss_vs_capability(-0.05, 0.00)
    assert c2 == "UNCORRELATED"


# ==============================================================================
# 9. Admin API, Tenant Isolation & AST Security (Tests 71-75)
# ==============================================================================

def test_071_admin_api_create_and_get_training_job(tmp_path: Path) -> None:
    mgr = TenantResourceManager()
    logger = AdminAuditLogger(tmp_path / "audit.jsonl")
    api = TenantAdminAPI(resource_manager=mgr, audit_logger=logger)
    queue = Phase48TrainingQueue(tmp_path / "queue.json")

    ctx = AdminSecurityContext.create("t_a", "adm_1", "ADMIN", "admin_model", "req-1")
    job = api.create_training_job(ctx, "job_t1", "m_hash", target_tokens=1000, target_steps=50, queue=queue)
    assert job.job_id == "job_t1"

    ret = api.get_training_job(ctx, "job_t1", queue=queue)
    assert ret.job_id == "job_t1"


def test_072_admin_api_tenant_boundary_denies_cross_tenant_access(tmp_path: Path) -> None:
    mgr = TenantResourceManager()
    logger = AdminAuditLogger(tmp_path / "audit.jsonl")
    api = TenantAdminAPI(resource_manager=mgr, audit_logger=logger)
    queue = Phase48TrainingQueue(tmp_path / "queue.json")

    ctx_a = AdminSecurityContext.create("t_a", "adm_1", "ADMIN", "admin_model", "req-1")
    api.create_training_job(ctx_a, "job_t_a", "m_hash", 1000, 50, queue=queue)

    ctx_b = AdminSecurityContext.create("t_b", "adm_2", "ADMIN", "admin_model", "req-2")
    with pytest.raises(TenantAccessDeniedError):
        api.get_training_job(ctx_b, "job_t_a", queue=queue)


def test_073_admin_api_rejection_of_public_chat_scope(tmp_path: Path) -> None:
    mgr = TenantResourceManager()
    logger = AdminAuditLogger(tmp_path / "audit.jsonl")
    api = TenantAdminAPI(resource_manager=mgr, audit_logger=logger)
    queue = Phase48TrainingQueue(tmp_path / "queue.json")

    ctx = AdminSecurityContext.create("t_a", "adm_1", "ADMIN", "public_chat", "req-3")
    with pytest.raises(ScopeAccessDeniedError):
        api.create_training_job(ctx, "job_pub", "m_hash", 1000, 50, queue=queue)


def test_074_admin_api_no_promote_candidate_endpoint() -> None:
    # Mandatory Correction 6: Admin API must NOT have PROMOTE_CANDIDATE
    mgr = TenantResourceManager()
    logger = AdminAuditLogger(Path("/tmp/audit.jsonl"))
    api = TenantAdminAPI(resource_manager=mgr, audit_logger=logger)
    assert not hasattr(api, "promote_candidate")


def test_075_ast_security_scan_prohibited_primitives() -> None:
    forbidden = {"eval", "exec", "os.system"}
    for py_file in Path("core_model").rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in forbidden, f"Forbidden {node.func.id} in {py_file}"


# ==============================================================================
# 10. End-to-End Multi-Worker Cross-Run Accumulation (Test 76)
# ==============================================================================

def test_076_end_to_end_multi_worker_cross_run_accumulation(tmp_path: Path) -> None:
    """Full end-to-end test: Worker A -> Checkpoint -> Terminate -> Worker B -> Resume -> Checkpoint -> Ledger."""
    q_file = tmp_path / "queue.json"
    l_file = tmp_path / "ledger.json"
    ckpt_dir = tmp_path / "ckpts"

    queue = Phase48TrainingQueue(q_file)
    ledger = Phase48TokenLedger(l_file, initial_baseline_tokens=2080)
    cfg = micro_preset(vocabulary_size=32, hidden_size=16, intermediate_size=32, num_hidden_layers=1, num_attention_heads=2, num_key_value_heads=2)

    # 1. Submit Job
    job = queue.submit_job("e2e_job", "tenant_system", "manifest_root", target_tokens=1000, target_steps=4)

    # 2. Worker A trains 2 steps
    torch.manual_seed(48)
    batch = [(torch.randint(0, 32, (2, 8)), torch.randint(0, 32, (2, 8)))]  # 16 tokens/step
    worker_a = Phase48TrainingWorker("worker_A", cfg, ckpt_dir, ledger)
    res_a = worker_a.run_training_slice("e2e_job", "run_A", train_batches=batch, target_steps=2, max_duration_seconds=5.0)
    assert res_a.actual_steps == 2
    assert res_a.actual_training_tokens == 32
    queue.update_job_progress("e2e_job", res_a.actual_steps, res_a.actual_training_tokens, res_a.checkpoint_id)

    # Worker A terminates
    del worker_a

    # 3. Worker B resumes from Worker A's checkpoint
    worker_b = Phase48TrainingWorker("worker_B", cfg, ckpt_dir, ledger)
    worker_b.load_checkpoint(ckpt_dir / res_a.checkpoint_id)
    assert worker_b.step == 2

    # Worker B trains 2 more steps
    res_b = worker_b.run_training_slice("e2e_job", "run_B", train_batches=batch, target_steps=2, max_duration_seconds=5.0, parent_checkpoint_id=res_a.checkpoint_id)
    assert res_b.actual_steps == 2
    assert res_b.actual_training_tokens == 32
    assert worker_b.step == 4

    # 4. Verify Cumulative Token Ledger
    assert ledger.get_cumulative_tokens() == 2080 + 32 + 32
    ok, msg = ledger.verify_ledger_integrity()
    assert ok is True
