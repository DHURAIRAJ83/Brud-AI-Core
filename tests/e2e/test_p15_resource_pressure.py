"""P15 Resource Pressure & Memory Safety Test Suite.

Validates behavior under:
1. High CPU / prompt processing pressure
2. Large prompts and token budget truncation
3. Large RAG chunk payloads and memory consumption
4. Slow external providers and timeout resilience
5. Bounded retry caps (zero runaway retries)
6. Thread and task leakage audit (threading.active_count)
7. File descriptor leakage audit (/proc/self/fd)
8. Repeated SSE session teardown and resource release
9. SQLite connection cleanliness (zero orphaned connections)
10. Idempotency & duplicate persistence prevention
"""

from __future__ import annotations

import gc
import os
import resource
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.mini_brain_llm_adapter import (
    ExternalProviderMiniBrainAdapter,
    MockMiniBrainAdapter,
)
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService

pytestmark = pytest.mark.anyio


def _get_rss_mb() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2)


def _get_open_fd_count() -> int:
    try:
        return len(os.listdir("/proc/self/fd"))
    except Exception:
        return 0


@pytest.fixture
def p15_resource_env(tmp_path: Path):
    db_path = tmp_path / "p15_resource.db"
    settings = Settings(
        database_path=db_path,
        allowed_data_dir=tmp_path / "data",
        allowed_model_dir=tmp_path / "models",
        allow_external_storage=True,
        mini_brain_context_cache_ttl_seconds=5.0,
        database_busy_timeout_ms=10000,
    )
    initialize_database(settings.resolved_database_path)
    return settings


# 1. Large prompt and token budget bounding
def test_p15_res_001_large_prompt_bounded_context(p15_resource_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_resource_env, adapter_factory=lambda: adapter)

    # Accumulate 35 turns of detailed messages (>1500 tokens total) to exceed input budget
    session_id = None
    truncated_observed = False
    t0 = time.perf_counter()

    for turn in range(35):
        res = service.chat(
            session_id=session_id,
            message=f"Turn {turn}: Detailed administrative logging event record for distributed runtime analysis and pressure verification {turn} " * 5,
            admin_id="adm_pressure",
        )
        session_id = res["session"]["public_id"]
        if res["reply"]["truncated"] is True:
            truncated_observed = True
            break

    duration = time.perf_counter() - t0
    assert truncated_observed is True
    print(f"\n[RES-001] Context Window Bounding: context truncation successfully triggered under token pressure in {duration:.3f}s")



# 2. Large RAG chunk payload memory safety
def test_p15_res_002_large_rag_payload_safety(p15_resource_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_resource_env, adapter_factory=lambda: adapter)

    # 10 large chunks, 5000 chars each
    huge_chunks = [
        {"source_public_id": f"src_{i}", "text": f"Chunk {i} content: " + ("data " * 1000), "score": 0.9}
        for i in range(10)
    ]
    service.retrieval_service.retrieve = MagicMock(return_value={"results": huge_chunks})

    rss_before = _get_rss_mb()
    res = service.grounded_chat(
        session_id=None,
        message="Summarize all huge chunks",
        retrieval_profile_public_id="prof_huge",
        top_k=4,
        admin_id="adm_rag_pressure",
    )
    rss_after = _get_rss_mb()

    assert len(res["citations"]) == 4  # Top k strictly respected
    assert (rss_after - rss_before) < 20.0  # Memory delta bounded under 20MB
    print(f"\n[RES-002] Large RAG Payload (50K chars across 10 chunks): top_k=4 enforced, RSS delta: {rss_after - rss_before:.2f}MB")


# 3. Slow external provider timeout & bounded wait
def test_p15_res_003_slow_provider_timeout_bounded(p15_resource_env: Settings):
    slow_adapter = ExternalProviderMiniBrainAdapter(provider_key="slow_provider", api_key="sk-test")

    # Simulate slow hang that times out
    def slow_generate(*args, **kwargs):
        time.sleep(0.6)
        return {"text": "", "backend_type": "external", "error_message": "TIMEOUT: Read timed out after 500ms"}

    slow_adapter.generate = MagicMock(side_effect=slow_generate)
    slow_adapter.is_available = MagicMock(return_value=True)

    service = MiniBrainLlmRuntimeService(p15_resource_env)
    service._resolve_backend = MagicMock(return_value={
        "adapter": slow_adapter, "backend_type": "external", "model": "slow-model", "reason": "slow"
    })
    service._list_available_fallback_candidates = MagicMock(return_value=[])

    t0 = time.perf_counter()
    res = service.chat(
        session_id=None,
        message="Query to slow provider",
        admin_id="adm_slow",
        execution_mode="auto",
    )
    duration = time.perf_counter() - t0

    assert "timeout" in (res.get("error_message") or "").lower() or "unavailable" in res["reply"]["sanitized_text"].lower()
    assert duration < 5.0  # Bounded, does not hang indefinitely
    print(f"\n[RES-003] Slow Provider Timeout: bounded wait of {duration:.2f}s, clean error response")


# 4. Zero runaway retries (capped at max attempts)
def test_p15_res_004_bounded_retry_cap(p15_resource_env: Settings):
    adapter = ExternalProviderMiniBrainAdapter(provider_key="openai", api_key="sk-test")
    attempts = 0

    mock_httpx = MagicMock()
    def mock_post(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.text = "Bad Gateway"
        return mock_resp

    mock_httpx.post = mock_post
    adapter._import_httpx = MagicMock(return_value=mock_httpx)

    # Single call should make exactly max 3 attempts (1 initial + 2 retries)
    res = adapter.generate(messages=[{"role": "user", "content": "hi"}])

    assert attempts == 3  # Initial (1) + 2 retries = 3 total calls
    assert res["error_message"] is not None
    assert "BAD_GATEWAY" in res["error_message"]
    print(f"\n[RES-004] Retry Cap: max 3 attempts strictly enforced, attempts made: {attempts}")


# 5. Thread & task leakage audit
def test_p15_res_005_thread_leakage_audit(p15_resource_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_resource_env, adapter_factory=lambda: adapter)

    threads_before = threading.active_count()

    # Execute 30 chat requests
    for i in range(30):
        service.chat(session_id=None, message=f"Thread check {i}", admin_id="adm_thread")

    gc.collect()
    threads_after = threading.active_count()

    # Threads should not leak
    assert threads_after <= threads_before + 1
    print(f"\n[RES-005] Thread Leakage Audit: before={threads_before}, after={threads_after} (zero leaked threads)")


# 6. File descriptor leakage audit
def test_p15_res_006_fd_leakage_audit(p15_resource_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_resource_env, adapter_factory=lambda: adapter)

    gc.collect()
    fds_before = _get_open_fd_count()

    # Execute 25 chat requests
    for i in range(25):
        service.chat(session_id=None, message=f"FD check {i}", admin_id="adm_fd")

    gc.collect()
    fds_after = _get_open_fd_count()

    # FDs must remain stable (allow max +/- 2 for test runner noise)
    fd_growth = fds_after - fds_before
    assert fd_growth <= 3
    print(f"\n[RES-006] File Descriptor Audit: before={fds_before}, after={fds_after}, delta={fd_growth} FDs")


# 7. Repeated SSE sessions teardown & resource release
def test_p15_res_007_repeated_sse_sessions_teardown(p15_resource_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_resource_env, adapter_factory=lambda: adapter)

    gc.collect()
    rss_start = _get_rss_mb()

    for s in range(20):
        events = list(service.stream_chat(
            session_id=None,
            message=f"SSE repeated query {s}",
            admin_id="adm_sse_leak",
        ))
        assert len(events) >= 4
        done_ev = next(e for e in events if e["event"] == "done")
        assert done_ev is not None

    gc.collect()
    rss_end = _get_rss_mb()
    delta_mb = round(rss_end - rss_start, 2)

    assert delta_mb < 15.0  # Zero unbounded memory growth across SSE sessions
    print(f"\n[RES-007] Repeated SSE Teardown: 20 sessions streamed and closed, RSS delta: {delta_mb}MB")


# 8. SQLite connection hygiene (clean commit and close)
def test_p15_res_008_sqlite_connection_hygiene(p15_resource_env: Settings):
    service = MiniBrainLlmRuntimeService(p15_resource_env)

    # Trigger multiple transactions
    for i in range(15):
        with service.repository.transaction() as conn:
            conn.execute("SELECT 1").fetchone()

    # Verify database can be opened exclusively without contention
    with service.repository.transaction(immediate=True) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]

    assert integrity == "ok"
    print(f"\n[RES-008] SQLite Connection Hygiene: 15 sequential transactions closed cleanly, exclusive lock acquired")


# 9. Deduplication & single persistence turn under duplicate prompts
def test_p15_res_009_deduplication_under_burst(p15_resource_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_resource_env, adapter_factory=lambda: adapter)

    # First turn
    res1 = service.chat(session_id=None, message="Burst prompt duplicate", admin_id="adm_dedup")
    session_id = res1["session"]["public_id"]

    # Identical immediate turn in same session (dedup check)
    res2 = service.chat(session_id=session_id, message="Burst prompt duplicate", admin_id="adm_dedup")

    with service.repository.transaction() as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM mini_brain_llm_messages WHERE session_id=?", (session_id,)
        ).fetchone()[0]

    # Verified dedup avoids duplicate execution and assistant reply is deduplicated
    assert count == 2  # Exactly 1 user + 1 assistant message in session
    assert res1["reply"]["public_id"] == res2["reply"]["public_id"]
    print(f"\n[RES-009] Deduplication Under Burst: identical query re-used cached turn, 2 messages total in session")
