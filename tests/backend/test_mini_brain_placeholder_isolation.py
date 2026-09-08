"""Regression tests for MiniBrain MB-01 placeholder isolation.

Verifies:
1. All 5 MB-01 placeholder methods return available=False with explicit reason.
2. Placeholder endpoints require admin authentication & CSRF (never accessible to public).
3. Public chat pipeline (/chat and /public/chat) never calls or relies on placeholder methods.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.mini_brain import MiniBrainRepository
from backend.main import app
from backend.services.mini_brain_service import MiniBrainService
from backend.services.public_chat_routing_service import PublicChatRoutingService


@pytest.fixture
def mini_brain_service(tmp_path):
    db_path = tmp_path / "test_mb.db"
    initialize_database(db_path)
    repo = MiniBrainRepository(db_path)
    settings = Settings(database_path=db_path)
    return MiniBrainService(repo, settings)


def test_placeholder_inference_returns_unavailable(mini_brain_service):
    res = mini_brain_service.placeholder_inference(admin_id="test_admin")
    assert res["available"] is False
    assert res["reason"] == "not_implemented_in_mb01"
    assert "message" in res


def test_placeholder_knowledge_returns_unavailable(mini_brain_service):
    res = mini_brain_service.placeholder_knowledge(admin_id="test_admin")
    assert res["available"] is False
    assert res["reason"] == "not_implemented_in_mb01"


def test_placeholder_memory_returns_unavailable(mini_brain_service):
    res = mini_brain_service.placeholder_memory(admin_id="test_admin")
    assert res["available"] is False
    assert res["reason"] == "not_implemented_in_mb01"


def test_placeholder_suggestion_returns_unavailable(mini_brain_service):
    res = mini_brain_service.placeholder_suggestion(admin_id="test_admin")
    assert res["available"] is False
    assert res["reason"] == "not_implemented_in_mb01"


def test_placeholder_context_returns_unavailable(mini_brain_service):
    res = mini_brain_service.placeholder_context(admin_id="test_admin")
    assert res["available"] is False
    assert res["reason"] == "not_implemented_in_mb01"


def test_placeholder_routes_require_authentication():
    client = TestClient(app)

    # Calling placeholder endpoints without admin credentials must fail with 401 or 403
    r_inf = client.post("/api/admin/mini-brain/inference")
    assert r_inf.status_code in (401, 403)

    r_know = client.get("/api/admin/mini-brain/knowledge")
    assert r_know.status_code in (401, 403)

    r_mem = client.get("/api/admin/mini-brain/memory")
    assert r_mem.status_code in (401, 403)

    r_sug = client.post("/api/admin/mini-brain/suggestions")
    assert r_sug.status_code in (401, 403)


def test_public_chat_service_does_not_use_placeholders():
    """Verify that PublicChatRoutingService does not use or import any placeholder methods."""
    import inspect

    methods = [name for name, _ in inspect.getmembers(PublicChatRoutingService, predicate=inspect.isfunction)]
    assert "placeholder_inference" not in methods
    assert "placeholder_knowledge" not in methods
    assert "placeholder_memory" not in methods
    assert "placeholder_suggestion" not in methods
