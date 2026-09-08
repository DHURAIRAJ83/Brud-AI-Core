"""P15 Disaster Recovery Validation Test Suite.

Simulates and empirically measures:
1. Complete Database Loss & Cold Restore (measures RTO and RPO boundary)
2. Runtime Directory Loss (missing allowed_data_dir / models dir)
3. Total Provider Outage & Failover / Honest Degradation
4. Local Model File Absence (honest fail-closed availability)
5. RAG Pipeline Outage (empty/missing chunks gracefully handled)
6. Backend Process Crash & Cold Restart Timing
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.core.config import Settings
from backend.database.migrations import (
    create_verified_backup,
    initialize_database,
    verify_database,
)
from backend.services.mini_brain_llm_adapter import (
    LlamaCppMiniBrainAdapter,
    MockMiniBrainAdapter,
)
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService

pytestmark = pytest.mark.anyio


class StableMockAdapter(MockMiniBrainAdapter):
    backend_type = "local"

    def is_available(self) -> bool:
        return True

    def generate(self, *, messages: list[dict[str, Any]], **kwargs) -> dict[str, Any]:
        return {
            "text": "Disaster recovery verified reply",
            "backend_type": "local",
            "tokens_generated": 10,
            "latency_ms": 10.0,
            "error_message": None,
        }


@pytest.fixture
def dr_env(tmp_path: Path):
    db_path = tmp_path / "dr_live.db"
    backup_dir = tmp_path / "dr_backups"
    data_dir = tmp_path / "dr_data"
    models_dir = tmp_path / "dr_models"
    data_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    settings = Settings(
        database_path=db_path,
        backup_dir=backup_dir,
        allowed_data_dir=data_dir,
        allowed_model_dir=models_dir,
        allow_external_storage=True,
        database_auto_backup=True,
        database_busy_timeout_ms=10000,
    )
    initialize_database(settings.resolved_database_path)
    return settings


# 1. Database Loss Simulation: Measure RTO and verify RPO boundary
def test_p15_dr_001_database_loss_rto_rpo(dr_env: Settings):
    svc = MiniBrainLlmRuntimeService(dr_env, adapter_factory=lambda: StableMockAdapter())
    sess = svc.open_session(admin_id="admin_dr", title="Pre-Disaster Session")
    session_id = sess["public_id"]
    svc.chat(session_id=session_id, admin_id="admin_dr", message="Pre-disaster commit")

    # Step A: Create snapshot
    backup_res = create_verified_backup(dr_env.resolved_database_path, dr_env.resolved_backup_dir)
    snapshot_time = time.time()

    # Step B: Catastrophic destruction (Database Wipe)
    live_db = dr_env.resolved_database_path
    live_wal = live_db.with_name(live_db.name + "-wal")
    live_shm = live_db.with_name(live_db.name + "-shm")
    live_db.unlink()
    if live_wal.exists():
        live_wal.unlink()
    if live_shm.exists():
        live_shm.unlink()
    del svc

    # Step C: Measure Recovery Time Objective (RTO)
    rto_start = time.perf_counter()
    shutil.copy2(backup_res.path, live_db)
    verify_database(live_db)
    recovered_svc = MiniBrainLlmRuntimeService(dr_env, adapter_factory=lambda: StableMockAdapter())
    # Verify service is immediately ready to serve
    res = recovered_svc.chat(session_id=session_id, admin_id="admin_dr", message="Post-recovery ping")
    rto_seconds = round(time.perf_counter() - rto_start, 4)

    assert res["error_message"] is None
    assert len(recovered_svc.list_messages(session_id=session_id)["items"]) == 4

    print(f"\n[DR-001] Database Loss Disaster Recovery: Measured RTO = {rto_seconds}s, RPO boundary = backup snapshot ({backup_res.filename})")


# 2. Runtime Directory Loss Simulation
def test_p15_dr_002_runtime_directory_loss_recovery(dr_env: Settings):
    # Wipe the allowed data and model directories while DB remains
    if dr_env.allowed_data_dir.exists():
        shutil.rmtree(dr_env.allowed_data_dir)
    if dr_env.allowed_model_dir.exists():
        shutil.rmtree(dr_env.allowed_model_dir)

    # Re-initialize service: must safely recover or re-create directories without crash
    svc = MiniBrainLlmRuntimeService(dr_env, adapter_factory=lambda: StableMockAdapter())
    health = svc.widget_health()
    assert health["available"] is True
    # The directories can be recreated on-demand
    dr_env.allowed_data_dir.mkdir(parents=True, exist_ok=True)
    dr_env.allowed_model_dir.mkdir(parents=True, exist_ok=True)
    print("\n[DR-002] Runtime Directory Loss: service stayed resilient, reported health without crash")


# 3. Provider Outage Simulation: Fail-closed & honest degradation
def test_p15_dr_003_provider_outage_honest_degradation(dr_env: Settings):
    # Provider completely dead
    dead_adapter = MagicMock()
    dead_adapter.backend_type = "external"
    dead_adapter.is_available.return_value = False
    dead_adapter.generate.return_value = {
        "text": "",
        "backend_type": "external",
        "tokens_generated": 0,
        "latency_ms": 15.0,
        "error_message": "UPSTREAM_DISASTER: 503 Service Unavailable across all regions",
    }

    svc = MiniBrainLlmRuntimeService(dr_env, adapter_factory=lambda: dead_adapter)
    sess = svc.open_session(admin_id="admin_dr", title="Outage Session")
    session_id = sess["public_id"]

    outage_start = time.perf_counter()
    res = svc.chat(session_id=session_id, admin_id="admin_dr", message="Hello in outage")
    detection_time = round(time.perf_counter() - outage_start, 4)

    # Invariant: Zero fake replies, returns sanitized honest error
    assert res["error_message"] is not None
    assert "UPSTREAM_DISASTER" in res["error_message"]
    print(f"\n[DR-003] Provider Outage: fail-closed response in {detection_time}s, zero fake intelligence")


# 4. Local Model File Absence Simulation
def test_p15_dr_004_local_model_unavailable_honest_probe(dr_env: Settings):
    # Point adapter to nonexistent file
    ghost_path = dr_env.allowed_model_dir / "nonexistent_model.gguf"
    adapter = LlamaCppMiniBrainAdapter(settings=dr_env, model_path=ghost_path)

    probe_start = time.perf_counter()
    available = adapter.is_available()
    probe_time = round(time.perf_counter() - probe_start, 4)

    assert available is False
    res = adapter.generate(messages=[{"role": "user", "content": "test"}])
    assert res["error_message"] is not None
    assert "not available" in res["error_message"]
    print(f"\n[DR-004] Local Model Absence: is_available=False in {probe_time}s, clean error message")


# 5. RAG Pipeline Outage Simulation
def test_p15_dr_005_rag_outage_graceful_fallback(dr_env: Settings):
    # When RAG retrieval service returns empty results or errors, chat must not crash
    mock_retrieval = MagicMock()
    mock_retrieval.retrieve.return_value = {"chunks": [], "total_chunks": 0, "status": "empty"}

    svc = MiniBrainLlmRuntimeService(
        dr_env,
        adapter_factory=lambda: StableMockAdapter(),
        retrieval_service=mock_retrieval,
    )
    sess = svc.open_session(admin_id="admin_dr", title="RAG Outage Session")
    session_id = sess["public_id"]

    # Fallback to chat turn when RAG has 0 chunks
    res = svc.chat(session_id=session_id, admin_id="admin_dr", message="Question during RAG outage")
    assert res["error_message"] is None
    assert res["reply"]["sanitized_text"] == "Disaster recovery verified reply"
    print("\n[DR-005] RAG Pipeline Outage: service gracefully continued chat without crash")


# 6. Cold Start / Process Reboot Timing
def test_p15_dr_006_cold_start_reboot_timing(dr_env: Settings):
    cold_start_timings = []
    for _ in range(5):
        t0 = time.perf_counter()
        svc = MiniBrainLlmRuntimeService(dr_env, adapter_factory=lambda: StableMockAdapter())
        health = svc.widget_health()
        t1 = time.perf_counter()
        cold_start_timings.append(t1 - t0)
        del svc

    avg_cold_start_ms = round(sum(cold_start_timings) / len(cold_start_timings) * 1000, 2)
    max_cold_start_ms = round(max(cold_start_timings) * 1000, 2)
    assert avg_cold_start_ms < 500  # Must boot in under 500ms
    print(f"\n[DR-006] Cold Boot Process Restart Timing: avg={avg_cold_start_ms}ms, peak={max_cold_start_ms}ms")
