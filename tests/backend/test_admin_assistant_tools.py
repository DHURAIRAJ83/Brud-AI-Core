from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.rag import RagRepository
from backend.models.data_sources import DataSourceCreate
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.rag import KnowledgeSpaceCreate
from backend.services.admin_assistant_tools import (
    READ_ONLY_TOOLS,
    ReadOnlyToolError,
    get_tool,
    run_tool,
    tools_for_mode,
)
from backend.services.data_source_service import SourceRegistryService
from backend.services.rag_ingestion_service import RagIngestionService

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "tools.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def test_registry_has_all_six_modes_covered() -> None:
    modes = {tool.mode for tool in READ_ONLY_TOOLS}
    assert modes == {"guide", "data", "governance", "rag", "model", "system"}


def test_tools_for_mode_filters_correctly() -> None:
    for mode in ("guide", "data", "governance", "rag", "model", "system"):
        for tool in tools_for_mode(mode):
            assert tool.mode == mode


def test_run_tool_rejects_unknown_tool(settings: Settings) -> None:
    with pytest.raises(ReadOnlyToolError):
        run_tool("does_not_exist", settings)


def test_run_tool_rejects_missing_required_param(settings: Settings) -> None:
    with pytest.raises(ReadOnlyToolError):
        run_tool("get_page_help", settings, {})
    with pytest.raises(ReadOnlyToolError):
        run_tool("get_source_status", settings, {})


def test_dashboard_overview(settings: Settings) -> None:
    result = run_tool("get_dashboard_overview", settings)
    assert "summary" in result
    assert "guidance" in result


def test_page_help_known_and_unknown_page(settings: Settings) -> None:
    result = run_tool("get_page_help", settings, {"page_id": "datasets"})
    assert result["available"] is True
    assert result["nav_key"] == "Datasets"
    assert "tabs" in result

    missing = run_tool("get_page_help", settings, {"page_id": "not_a_real_page"})
    assert missing["available"] is False

    by_nav_key = run_tool("get_page_help", settings, {"nav_key": "Chat Testing"})
    assert by_nav_key["available"] is True
    assert by_nav_key["implemented"] is False


def test_pending_admin_proposals_empty(settings: Settings) -> None:
    result = run_tool("get_pending_admin_proposals", settings)
    assert result["available"] is True
    assert result["items"] == []


def test_governance_review_queue_empty(settings: Settings) -> None:
    result = run_tool("get_governance_review_queue", settings)
    assert result["items"] == []
    assert result["total"] == 0


def test_governance_entity_status_with_no_activity(settings: Settings) -> None:
    result = run_tool(
        "get_governance_entity_status",
        settings,
        {"entity_type": "dataset_record", "entity_public_id": "does-not-exist"},
    )
    assert result["available"] is True
    assert all(
        target["decision"] == "not_requested" for target in result["targets"].values()
    )


def test_governed_build_status_not_found(settings: Settings) -> None:
    result = run_tool("get_governed_build_status", settings, {"public_id": "does-not-exist"})
    assert result["available"] is False


def test_list_governed_builds_empty(settings: Settings) -> None:
    result = run_tool("list_governed_builds", settings)
    assert result["items"] == []


def test_lineage_trace_with_no_edges(settings: Settings) -> None:
    result = run_tool(
        "get_lineage_trace",
        settings,
        {"entity_type": "dataset_record", "entity_id": "rec-1"},
    )
    assert result["available"] is True


def test_source_status_real_source(settings: Settings) -> None:
    repository = DataSourceRepository(settings.resolved_database_path)
    service = SourceRegistryService(repository, settings)
    created = service.create(
        DataSourceCreate(
            source_code="SRC-TOOL-TEST-0001",
            title="Tool Registry Test Source",
            source_type="human_created",
        ),
        ADMIN_ID,
    )
    result = run_tool("get_source_status", settings, {"public_id": created["public_id"]})
    assert result["available"] is True
    assert result["source_code"] == "SRC-TOOL-TEST-0001"

    missing = run_tool("get_source_status", settings, {"public_id": "does-not-exist"})
    assert missing["available"] is False


def test_list_rag_knowledge_spaces(settings: Settings) -> None:
    repository = RagRepository(settings.resolved_database_path)
    service = RagIngestionService(repository, settings)
    service.create_space(
        KnowledgeSpaceCreate(name="Tool Registry Space", slug="tool-registry-space"),
        ADMIN_ID,
    )
    result = run_tool("list_rag_knowledge_spaces", settings)
    assert any(space["slug"] == "tool-registry-space" for space in result["items"])


def test_model_evaluation_run_not_found(settings: Settings) -> None:
    result = run_tool("get_model_evaluation_run", settings, {"public_id": "does-not-exist"})
    assert result["available"] is False


def test_model_release_candidate_not_found(settings: Settings) -> None:
    result = run_tool("get_model_release_candidate", settings, {"public_id": "does-not-exist"})
    assert result["available"] is False


def test_pretraining_readiness_evaluations_empty(settings: Settings) -> None:
    result = run_tool("list_pretraining_readiness_evaluations", settings)
    assert "items" in result


def test_recent_audit_events(settings: Settings) -> None:
    AuditLogRepository(settings.resolved_database_path).append(
        AuditEventCreate(
            event_type="test_event",
            actor_type="test",
            actor_reference=ADMIN_ID,
            action="test_action",
            resource_type="test_resource",
            resource_public_id="res-1",
            outcome=AuditOutcome.SUCCESS,
            metadata={},
        )
    )
    result = run_tool("get_recent_audit_events", settings, {"limit": 5})
    assert result["available"] is True
    assert any(event["event_type"] == "test_event" for event in result["items"])


def test_every_registered_tool_is_reachable_via_get_tool() -> None:
    for tool in READ_ONLY_TOOLS:
        assert get_tool(tool.name) is tool
