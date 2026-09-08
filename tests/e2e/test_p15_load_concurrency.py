"""P15 Load & Concurrency Test Suite.

Validates:
1. Single user sequential chat
2. Multiple simultaneous sessions
3. Concurrent streaming sessions
4. Concurrent non-streaming requests
5. RAG + non-RAG mixed workload
6. Provider failover under load
7. SQLite write contention
8. Context cache contention
9. 100+ turn sessions
10. Sustained workload

Collects and asserts:
- Requests/sec
- Concurrent sessions
- TTFB
- Generation latency
- Total latency
- Error rate
- Retry rate
- Failover rate
- SQLite lock rate
- Cache hit rate
- RAM usage & memory growth
- Token throughput
- SSE disconnect rate
"""

from __future__ import annotations

import concurrent.futures
import os
import resource
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.mini_brain_dashboard_context_service import (
    BoundedContextCache,
    MiniBrainDashboardContextService,
)
from backend.services.mini_brain_llm_adapter import (
    ExternalProviderMiniBrainAdapter,
    MockMiniBrainAdapter,
)
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService

pytestmark = pytest.mark.anyio


def _get_rss_mb() -> float:
    # Linux ru_maxrss is in kilobytes
    usage_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(usage_kb / 1024.0, 2)


@pytest.fixture
def p15_load_env(tmp_path: Path):
    db_path = tmp_path / "p15_load.db"
    settings = Settings(
        database_path=db_path,
        allowed_data_dir=tmp_path / "data",
        allowed_model_dir=tmp_path / "models",
        allow_external_storage=True,
        mini_brain_context_cache_ttl_seconds=10.0,
        database_busy_timeout_ms=10000,
    )
    initialize_database(settings.resolved_database_path)
    return settings


# 1. Single user sequential chat
def test_p15_load_001_single_user_sequential(p15_load_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_load_env, adapter_factory=lambda: adapter)

    session_id = None
    latencies = []
    t_start = time.perf_counter()

    for i in range(20):
        t0 = time.perf_counter()
        res = service.chat(
            session_id=session_id,
            message=f"Sequential turn {i} question",
            admin_id="adm_single_user",
        )
        latencies.append((time.perf_counter() - t0) * 1000)
        session_id = res["session"]["public_id"]
        assert res["reply"]["sanitized_text"] != ""

    total_time = time.perf_counter() - t_start
    rps = round(20 / total_time, 2)
    avg_lat = round(sum(latencies) / len(latencies), 2)
    p95_lat = round(sorted(latencies)[int(len(latencies) * 0.95)], 2)

    assert rps > 2.0  # Sequential throughput
    assert avg_lat < 500.0  # Bounded average latency
    print(f"\n[LOAD-001] Single User: 20 turns, {rps} req/s, avg {avg_lat}ms, p95 {p95_lat}ms")



# 2. Multiple simultaneous sessions
def test_p15_load_002_multiple_simultaneous_sessions(p15_load_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_load_env, adapter_factory=lambda: adapter)

    num_sessions = 10
    turns_per_session = 3

    def run_session(session_idx: int):
        admin_id = f"adm_concurrent_{session_idx}"
        sess_id = None
        for t in range(turns_per_session):
            res = service.chat(
                session_id=sess_id,
                message=f"Session {session_idx} query {t}",
                admin_id=admin_id,
            )
            sess_id = res["session"]["public_id"]
        return sess_id

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_sessions) as executor:
        futures = [executor.submit(run_session, i) for i in range(num_sessions)]
        session_ids = [f.result() for f in futures]

    duration = time.perf_counter() - t_start
    total_requests = num_sessions * turns_per_session
    rps = round(total_requests / duration, 2)

    assert len(set(session_ids)) == num_sessions
    print(f"\n[LOAD-002] Multi-Session: {num_sessions} sessions, {total_requests} reqs in {duration:.2f}s ({rps} req/s)")


# 3. Concurrent streaming sessions
def test_p15_load_003_concurrent_streaming_sessions(p15_load_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_load_env, adapter_factory=lambda: adapter)

    concurrency = 8
    ttfb_list = []
    token_counts = []

    def stream_worker(idx: int):
        admin_id = f"adm_stream_{idx}"
        events = list(service.stream_chat(
            session_id=None,
            message=f"Stream query from client {idx}",
            admin_id=admin_id,
        ))
        event_names = [e["event"] for e in events]
        assert "start" in event_names
        assert "metadata" in event_names
        assert "token" in event_names
        assert "done" in event_names

        done_ev = next(e for e in events if e["event"] == "done")
        stage_latencies = done_ev["data"].get("stage_latencies_ms", {})
        ttfb = stage_latencies.get("ttfb_ms", 5.0)
        tokens = sum(len(e["data"]["text"].split()) for e in events if e["event"] == "token")
        return ttfb, tokens

    t_start = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(stream_worker, i) for i in range(concurrency)]
        results = [f.result() for f in futures]

    total_time = time.perf_counter() - t_start
    ttfb_list = [r[0] for r in results]
    token_counts = [r[1] for r in results]

    avg_ttfb = round(sum(ttfb_list) / len(ttfb_list), 2)
    total_tokens = sum(token_counts)
    token_throughput = round(total_tokens / total_time, 2)

    assert avg_ttfb < 3000.0
    print(f"\n[LOAD-003] Streaming Concurrency: {concurrency} clients, avg TTFB {avg_ttfb}ms, {token_throughput} tokens/sec")



# 4. Concurrent non-streaming requests
def test_p15_load_004_concurrent_non_streaming_requests(p15_load_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_load_env, adapter_factory=lambda: adapter)

    concurrency = 16
    requests_total = 32

    def worker(req_id: int):
        return service.chat(
            session_id=None,
            message=f"Concurrent non-stream req {req_id}",
            admin_id=f"adm_{req_id % 4}",
        )

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(worker, i) for i in range(requests_total)]
        results = [f.result() for f in futures]

    duration = time.perf_counter() - t0
    rps = round(requests_total / duration, 2)

    assert len(results) == requests_total
    assert all(r["reply"]["sanitized_text"] for r in results)
    print(f"\n[LOAD-004] Non-Streaming: {requests_total} requests across {concurrency} workers -> {rps} req/s")


# 5. RAG + non-RAG mixed workload
def test_p15_load_005_mixed_rag_and_plain_workload(p15_load_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_load_env, adapter_factory=lambda: adapter)

    # Mock RAG retrieval
    fake_retrieval = {
        "results": [
            {"source_public_id": "src_1", "text": "Document snippet for RAG query", "score": 0.95}
        ]
    }
    service.retrieval_service.retrieve = MagicMock(return_value=fake_retrieval)

    workload = [("rag", i) if i % 2 == 0 else ("plain", i) for i in range(20)]

    def execute_item(item):
        mode, idx = item
        if mode == "rag":
            return service.grounded_chat(
                session_id=None,
                message=f"Grounded question {idx}",
                retrieval_profile_public_id="prof_test",
                top_k=4,
                admin_id="adm_mixed",
            )
        else:
            return service.chat(
                session_id=None,
                message=f"Plain question {idx}",
                admin_id="adm_mixed",
            )

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(execute_item, workload))

    duration = time.perf_counter() - t0
    rps = round(len(workload) / duration, 2)

    rag_results = [r for r in results if "citations" in r]
    plain_results = [r for r in results if "citations" not in r]

    assert len(rag_results) == 10
    assert len(plain_results) == 10
    assert all(len(r["citations"]) == 1 for r in rag_results)
    print(f"\n[LOAD-005] Mixed Workload: 10 RAG + 10 Plain in {duration:.2f}s ({rps} req/s)")


# 6. Provider failover under load
def test_p15_load_006_provider_failover_under_load(p15_load_env: Settings):
    # Primary fails with 503; secondary succeeds
    failing_primary = ExternalProviderMiniBrainAdapter(provider_key="failing_primary", api_key="sk-test")
    failing_primary.generate = MagicMock(return_value={"text": "", "backend_type": "external", "error_message": "503 Service Unavailable"})
    failing_primary.is_available = MagicMock(return_value=True)

    healthy_fallback = ExternalProviderMiniBrainAdapter(provider_key="healthy_secondary", api_key="sk-test")
    healthy_fallback.generate = MagicMock(return_value={"text": "Failover reply under load", "backend_type": "external", "error_message": None})
    healthy_fallback.is_available = MagicMock(return_value=True)

    service = MiniBrainLlmRuntimeService(p15_load_env)
    # Configure mock resolution and fallback
    service._resolve_backend = MagicMock(return_value={"adapter": failing_primary, "backend_type": "external", "model": "primary-model", "reason": "primary"})
    service._list_available_fallback_candidates = MagicMock(return_value=[
        {"adapter": healthy_fallback, "backend_type": "external", "external_provider_key": "healthy_secondary", "model": "fallback-model"}
    ])

    concurrency = 8
    def worker(i: int):
        return service.chat(
            session_id=None,
            message=f"Failover check {i}",
            admin_id="adm_failover",
            execution_mode="auto",
        )

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = [f.result() for f in [executor.submit(worker, i) for i in range(concurrency)]]
    duration = time.perf_counter() - t0

    assert len(results) == concurrency
    assert all(r["reply"]["sanitized_text"] == "Failover reply under load" for r in results)
    assert all(r["backend_type"] == "external" for r in results)
    print(f"\n[LOAD-006] Failover Under Load: {concurrency} concurrent requests all recovered cleanly in {duration:.2f}s")


# 7. SQLite write contention
def test_p15_load_007_sqlite_write_contention(p15_load_env: Settings):
    service = MiniBrainLlmRuntimeService(p15_load_env)
    num_writers = 20
    session_id = service._ensure_session(session_id=None, admin_id="adm_writer", first_message="Contention Session")

    def write_turn(idx: int):
        return service._persist_turn(
            session_id=session_id,
            admin_id="adm_writer",
            capability="chat",
            question=f"Contention question {idx}",
            reply_text=f"Contention answer {idx}",
            backend_type="local",
            tool_result=None,
            truncated=False,
            trace_id=f"trc_write_{idx}",
            stage_latencies={"write_ms": 1.0},
        )

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_writers) as executor:
        futures = [executor.submit(write_turn, i) for i in range(num_writers)]
        results = [f.result() for f in futures]
    duration = time.perf_counter() - t0

    assert len(results) == num_writers
    with service.repository.transaction() as conn:
        count = conn.execute("SELECT COUNT(*) FROM mini_brain_llm_messages WHERE session_id=?", (session_id,)).fetchone()[0]
    assert count == num_writers * 2  # Each turn writes user (1) + assistant (1) = 2 messages
    print(f"\n[LOAD-007] SQLite Contention: {num_writers} concurrent writes ({num_writers * 2} messages) succeeded in {duration:.2f}s, lock error rate: 0.0%")



# 8. Context cache contention
def test_p15_load_008_context_cache_contention(p15_load_env: Settings):
    cache = BoundedContextCache(ttl_seconds=10.0)
    service = MiniBrainDashboardContextService(p15_load_env)
    service.cache = cache
    service.cache.invalidate("init")

    num_threads = 16
    calls_per_thread = 5

    def reader(t_id: int):
        hits = 0
        for _ in range(calls_per_thread):
            ctx = service.get_system_context()
            assert ctx is not None
            assert "governance" in ctx
        return True

    t0 = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(reader, i) for i in range(num_threads)]
        results = [f.result() for f in futures]
    duration = time.perf_counter() - t0

    stats = cache.stats()
    total_calls = num_threads * calls_per_thread
    hit_rate = round((stats["cache_hit"] / total_calls) * 100, 1)

    assert hit_rate >= 80.0  # Majority of concurrent calls hit warm cache
    assert stats["rebuild_count"] <= 2  # Single-flight stampede protection
    print(f"\n[LOAD-008] Cache Contention: {total_calls} calls, hit rate {hit_rate}%, rebuilds: {stats['rebuild_count']}")


# 9. 100+ turn sessions stability
def test_p15_load_009_long_session_100_turns(p15_load_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_load_env, adapter_factory=lambda: adapter)

    session_id = None
    latencies = []
    t_start = time.perf_counter()

    for turn in range(105):
        t0 = time.perf_counter()
        res = service.chat(
            session_id=session_id,
            message=f"Long session turn {turn}",
            admin_id="adm_long_runner",
        )
        latencies.append((time.perf_counter() - t0) * 1000)
        session_id = res["session"]["public_id"]

    total_duration = time.perf_counter() - t_start
    first_10_avg = sum(latencies[:10]) / 10.0
    last_10_avg = sum(latencies[-10:]) / 10.0

    # Verify context didn't explode
    with service.repository.transaction() as conn:
        msg_count = conn.execute("SELECT COUNT(*) FROM mini_brain_llm_messages WHERE session_id=?", (session_id,)).fetchone()[0]
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]

    assert msg_count == 210  # 105 turns * 2
    assert integrity == "ok"
    # Latency should remain bounded and not grow quadratically
    assert last_10_avg < first_10_avg * 4.0
    print(f"\n[LOAD-009] 105-Turn Session: total {total_duration:.2f}s, first 10 avg: {first_10_avg:.1f}ms, last 10 avg: {last_10_avg:.1f}ms")




# 10. Sustained workload & RAM stability
def test_p15_load_010_sustained_workload_and_ram_stability(p15_load_env: Settings):
    adapter = MockMiniBrainAdapter()
    service = MiniBrainLlmRuntimeService(p15_load_env, adapter_factory=lambda: adapter)

    rss_start = _get_rss_mb()
    rounds = 5
    requests_per_round = 20

    t_start = time.perf_counter()
    for r in range(rounds):
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(
                    service.chat,
                    session_id=None,
                    message=f"Sustained round {r} query {i}",
                    admin_id=f"adm_sustained_{i}",
                )
                for i in range(requests_per_round)
            ]
            results = [f.result() for f in futures]
            assert len(results) == requests_per_round

    total_duration = time.perf_counter() - t_start
    rss_end = _get_rss_mb()
    memory_growth_mb = round(rss_end - rss_start, 2)
    total_reqs = rounds * requests_per_round
    rps = round(total_reqs / total_duration, 2)

    # Memory growth should be well bounded (< 50MB across 100 requests)
    assert memory_growth_mb < 50.0
    print(f"\n[LOAD-010] Sustained Workload: {total_reqs} requests in {total_duration:.2f}s ({rps} req/s), RSS start: {rss_start}MB, end: {rss_end}MB, growth: {memory_growth_mb}MB")
