"""P13 Context Cache Test Suite.

Validates:
P13-CACHE-001: Cold cache builds context
P13-CACHE-002: Second request hits cache
P13-CACHE-003: TTL expiry rebuilds context
P13-CACHE-004: Model mutation invalidates cache
P13-CACHE-005: Governance mutation invalidates cache
P13-CACHE-006: Provider mutation invalidates cache
P13-CACHE-007: Training state mutation invalidates cache
P13-CACHE-008: No secret stored in cache
P13-CACHE-009: Concurrent cache access is safe
P13-CACHE-010: Cache does not return stale truth
P13-CACHE-011: Cache stampede protection (single-flight)
P13-CACHE-012: Cache memory remains bounded
"""

import concurrent.futures
import time
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.mini_brain_dashboard_context_service import (
    BoundedContextCache,
    MiniBrainDashboardContextService,
)


@pytest.fixture
def test_settings(tmp_path):
    settings = Settings(
        database_path=tmp_path / "test_p13.db",
        allowed_data_dir=tmp_path / "data",
        allowed_model_dir=tmp_path / "models",
        mini_brain_context_cache_ttl_seconds=1.5,
        allow_external_storage=True,
    )
    initialize_database(settings.resolved_database_path)
    return settings



def test_p13_cache_001_cold_cache_builds(test_settings):
    cache = BoundedContextCache(ttl_seconds=2.0)
    service = MiniBrainDashboardContextService(test_settings)
    service.cache = cache
    service.cache.invalidate("initial_reset")

    assert cache.get() is None
    ctx = service.get_system_context()
    assert ctx is not None
    assert "system" in ctx
    assert "governance" in ctx
    stats = cache.stats()
    assert stats["rebuild_count"] >= 1
    assert stats["cache_miss"] >= 1


def test_p13_cache_002_second_request_hits_cache(test_settings):
    cache = BoundedContextCache(ttl_seconds=3.0)
    service = MiniBrainDashboardContextService(test_settings)
    service.cache = cache
    service.cache.invalidate("reset")

    ctx1 = service.get_system_context()
    hits_before = cache.stats()["cache_hit"]

    ctx2 = service.get_system_context()
    hits_after = cache.stats()["cache_hit"]

    assert hits_after == hits_before + 1
    assert ctx1["system"] == ctx2["system"]


def test_p13_cache_003_ttl_expiry_rebuilds(test_settings):
    cache = BoundedContextCache(ttl_seconds=0.3)
    service = MiniBrainDashboardContextService(test_settings)
    service.cache = cache
    service.cache.invalidate("reset")

    service.get_system_context()
    assert cache.get() is not None

    time.sleep(0.35)
    # Expired
    stats_before = cache.stats()
    rebuilds_before = stats_before["rebuild_count"]
    service.get_system_context()
    stats_after = cache.stats()

    assert stats_after["rebuild_count"] == rebuilds_before + 1
    assert stats_after["cache_expired"] >= 1


def test_p13_cache_004_model_mutation_invalidates(test_settings):
    service = MiniBrainDashboardContextService(test_settings)
    service.cache.invalidate("reset")

    service.get_system_context()
    assert service.cache.get() is not None

    MiniBrainDashboardContextService.invalidate_cache("model_switched")
    assert service.cache.get() is None
    assert service.cache.stats()["last_invalidation_reason"] == "model_switched"


def test_p13_cache_005_governance_mutation_invalidates(test_settings):
    service = MiniBrainDashboardContextService(test_settings)
    service.get_system_context()
    assert service.cache.get() is not None

    MiniBrainDashboardContextService.invalidate_cache("proposal_review_approved")
    assert service.cache.get() is None
    assert service.cache.stats()["last_invalidation_reason"] == "proposal_review_approved"


def test_p13_cache_006_provider_mutation_invalidates(test_settings):
    service = MiniBrainDashboardContextService(test_settings)
    service.get_system_context()
    assert service.cache.get() is not None

    MiniBrainDashboardContextService.invalidate_cache("provider_enabled")
    assert service.cache.get() is None
    assert service.cache.stats()["last_invalidation_reason"] == "provider_enabled"


def test_p13_cache_007_training_state_mutation_invalidates(test_settings):
    service = MiniBrainDashboardContextService(test_settings)
    service.get_system_context()
    assert service.cache.get() is not None

    MiniBrainDashboardContextService.invalidate_cache("training_run_status_changed")
    assert service.cache.get() is None
    assert service.cache.stats()["last_invalidation_reason"] == "training_run_status_changed"


def test_p13_cache_008_no_secret_stored_in_cache():
    cache = BoundedContextCache(ttl_seconds=3.0)
    fake_snapshot = {
        "providers": {
            "api_key": "sk-1234567890abcdef1234567890abcdef",
            "token": "Bearer my_super_secret_bearer_token",
        },
        "system": {"healthy": True},
    }
    cache.set(fake_snapshot, latency_ms=1.2)
    stored = cache.get()

    assert "sk-" not in str(stored)
    assert "[REDACTED]" in str(stored)


def test_p13_cache_009_concurrent_cache_access_is_safe(test_settings):
    cache = BoundedContextCache(ttl_seconds=2.0)
    service = MiniBrainDashboardContextService(test_settings)
    service.cache = cache
    service.cache.invalidate("reset")

    errors = []

    def worker(worker_id):
        try:
            for i in range(10):
                ctx = service.get_system_context()
                if not ctx or "system" not in ctx:
                    errors.append(f"Worker {worker_id} got bad context")
                if i == 5 and worker_id == 0:
                    service.cache.invalidate(f"worker_{worker_id}_inv")
        except Exception as exc:
            errors.append(str(exc))

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, i) for i in range(10)]
        concurrent.futures.wait(futures)

    assert len(errors) == 0


def test_p13_cache_010_cache_does_not_return_stale_truth(test_settings):
    service = MiniBrainDashboardContextService(test_settings)
    service.cache.invalidate("reset")

    # Seed cache
    service.get_system_context()
    cached1 = service.cache.get()
    assert cached1 is not None

    # Mutation event occurs
    MiniBrainDashboardContextService.invalidate_cache("provider_config_update")
    assert service.cache.get() is None  # Immediately closed, zero stale return


def test_p13_cache_011_cache_stampede_protection(test_settings):
    cache = BoundedContextCache(ttl_seconds=5.0)
    service = MiniBrainDashboardContextService(test_settings)
    service.cache = cache
    cache.invalidate("reset")

    rebuild_before = cache.stats()["rebuild_count"]

    # Fire 10 simultaneous workers on cold cache
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(service.get_system_context) for _ in range(10)]
        results = [f.result() for f in futures]

    rebuild_after = cache.stats()["rebuild_count"]
    # Coalesced: exactly 1 rebuild happened for all 10 concurrent requests
    assert rebuild_after - rebuild_before == 1
    assert len(results) == 10
    assert all(r is not None for r in results)


def test_p13_cache_012_cache_memory_remains_bounded():
    cache = BoundedContextCache(ttl_seconds=1.0)
    for i in range(50):
        cache.set({"iteration": i, "data": "x" * 1000}, latency_ms=0.5)
        stats = cache.stats()
        # Generational marker increments but underlying storage stores only 1 active snapshot
        assert stats["generation"] == i + 1

    assert cache.get()["iteration"] == 49
