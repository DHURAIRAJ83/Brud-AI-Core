"""Phase 19 Step 32/33 -- remaining security/privacy/performance
coverage not already exercised by test_knowledge_gap_admin_api.py,
test_knowledge_gap_core_services.py, or
test_public_chat_knowledge_gap_integration.py."""

import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
from backend.main import create_app
from backend.services.knowledge_gap_capture_service import KnowledgeGapCaptureService
from backend.services.knowledge_gap_clustering_service import KnowledgeGapClusteringService
from backend.services.knowledge_gap_merge_service import KnowledgeGapMergeService
from tests.backend.test_dataset_api import authenticated_client
from tests.backend.test_knowledge_gap_admin_api import _seed_case

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    settings = Settings(
        database_path=tmp_path / "api.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


# -- privacy: no user-identifying column exists anywhere in the registry ----------------------


_KNOWLEDGE_GAP_TABLES = (
    "knowledge_gap_cases",
    "knowledge_gap_occurrences",
    "knowledge_gap_clusters",
    "knowledge_gap_cluster_members",
    "knowledge_gap_reviews",
    "knowledge_gap_research_notes",
    "knowledge_gap_resolution_events",
    "knowledge_gap_status_events",
    "knowledge_gap_deletion_requests",
    "knowledge_gap_daily_reports",
)

_FORBIDDEN_COLUMN_SUBSTRINGS = (
    "user_id",
    "session_id",
    "ip_address",
    "user_agent",
    "conversation_id",
)


def test_no_table_has_any_end_user_identifying_column(tmp_path: Path) -> None:
    """Structural cross-user-isolation guarantee: there is no column
    anywhere in the registry that could link two cases/occurrences back
    to the same end user, so there is nothing to leak across users by
    construction -- not merely hidden by an access-control check."""

    settings = Settings(
        database_path=tmp_path / "t.db",
        database_backup_dir=tmp_path / "b",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    connection = sqlite3.connect(settings.resolved_database_path)
    try:
        for table in _KNOWLEDGE_GAP_TABLES:
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            for column in columns:
                for forbidden in _FORBIDDEN_COLUMN_SUBSTRINGS:
                    assert forbidden not in column.lower(), (table, column)
    finally:
        connection.close()


# -- hostile input handling ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "'; DROP TABLE knowledge_gap_cases; --",
        "hello\x00world what is the latest version",
        "hello​world zero width space question",  # zero-width space
        "‮reversed bidi text question‬",
        "<script>alert(1)</script> what is the latest version",
    ],
)
async def test_hostile_message_content_never_crashes_capture(
    api_app: FastAPI, message: str
) -> None:
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        response = await client.post("/api/chat", json={"message": message})
        assert response.status_code in (200, 422)
    finally:
        await client.aclose()

    settings: Settings = api_app.state.settings
    repo = KnowledgeGapRepository(settings.resolved_database_path)
    # The table must still be fully queryable afterwards -- proves no
    # injection occurred and no crash left the database inconsistent.
    overview = repo.aggregate_overview()
    assert isinstance(overview["total_cases"], int)


def test_sql_like_note_text_is_stored_safely_never_executed(tmp_path: Path) -> None:
    from backend.services.knowledge_gap_research_service import KnowledgeGapResearchService

    settings = Settings(
        database_path=tmp_path / "t.db",
        database_backup_dir=tmp_path / "b",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    capture = KnowledgeGapCaptureService(settings)
    case = capture.capture(
        message="what is the latest python version",
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        confidence_band="unknown",
        fallbacks_attempted=("trusted_web_unavailable",),
        clarification_required=False,
        detected_language="en",
    )
    research = KnowledgeGapResearchService(settings)
    note = research.add_note(
        case["public_id"],
        note_type="investigation",
        note_text="'; DROP TABLE knowledge_gap_cases; --",
        source_reference=None,
        author_admin_id="admin-1",
    )
    assert note["public_id"]

    repo = KnowledgeGapRepository(settings.resolved_database_path)
    overview = repo.aggregate_overview()
    assert overview["total_cases"] == 1


# -- merge safety: arbitrary/nonexistent targets -------------------------------------------------


def test_propose_merge_rejects_nonexistent_case_id(tmp_path: Path) -> None:
    from backend.database.repositories.base import NotFoundError

    settings = Settings(
        database_path=tmp_path / "t.db",
        database_backup_dir=tmp_path / "b",
        allowed_data_dir=tmp_path,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    capture = KnowledgeGapCaptureService(settings)
    real_case = capture.capture(
        message="what is the latest python version",
        resolved_route="insufficient",
        safety_status="safe",
        evidence_status="none",
        confidence_band="unknown",
        fallbacks_attempted=("trusted_web_unavailable",),
        clarification_required=False,
        detected_language="en",
    )
    service = KnowledgeGapMergeService(settings)
    with pytest.raises(NotFoundError):
        service.propose_merge([real_case["public_id"], "does-not-exist"])


async def test_confirm_merge_api_rejects_arbitrary_nonexistent_target(api_app: FastAPI) -> None:
    settings: Settings = api_app.state.settings
    real_case = _seed_case(settings)

    client, headers = await authenticated_client(api_app)
    try:
        response = await client.post(
            "/api/admin/knowledge-gaps/clusters/confirm-merge",
            json={
                "case_public_ids": [real_case["public_id"], "does-not-exist"],
                "stale_check_fingerprint": "anything",
                "canonical_question": "x",
                "primary_language": "en",
            },
            headers=headers,
        )
        assert response.status_code in (404, 422)
    finally:
        await client.aclose()


# -- performance / resource bounds ---------------------------------------------------------------


def test_clustering_bucket_is_bounded_never_unbounded_pairwise_scan() -> None:
    from backend.services.knowledge_gap_clustering_service import MAX_CANDIDATES_PER_BUCKET

    assert MAX_CANDIDATES_PER_BUCKET > 0
    assert MAX_CANDIDATES_PER_BUCKET <= 500


def test_clustering_service_handles_a_bounded_batch_quickly() -> None:
    import time

    from backend.services.knowledge_gap_clustering_service import ClusterCandidate

    service = KnowledgeGapClusteringService()
    candidates = [
        ClusterCandidate(
            case_public_id=f"case-{i}",
            canonical_question=f"question number {i} about something",
            language="en",
            domain="general",
            intent="ask_fact",
            freshness="timeless",
        )
        for i in range(100)
    ]
    started = time.perf_counter()
    service.find_cluster_decisions(candidates)
    elapsed = time.perf_counter() - started
    assert elapsed < 5.0


async def test_admin_api_pagination_never_exceeds_100(api_app: FastAPI) -> None:
    client, headers = await authenticated_client(api_app)
    try:
        response = await client.get(
            "/api/admin/knowledge-gaps/cases", params={"limit": 100}, headers=headers
        )
        assert response.status_code == 200
        response = await client.get(
            "/api/admin/knowledge-gaps/cases", params={"limit": 101}, headers=headers
        )
        assert response.status_code == 422
    finally:
        await client.aclose()


def test_note_text_length_is_bounded() -> None:
    from backend.models.knowledge_gap import MAX_NOTE_LENGTH

    assert MAX_NOTE_LENGTH > 0
    assert MAX_NOTE_LENGTH <= 10000


async def test_single_capture_latency_is_bounded(api_app: FastAPI) -> None:
    import time

    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    try:
        started = time.perf_counter()
        response = await client.post(
            "/api/chat", json={"message": "what is the latest python version"}
        )
        elapsed = time.perf_counter() - started
        assert response.status_code == 200
        assert elapsed < 5.0
    finally:
        await client.aclose()
