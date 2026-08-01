from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.admin_assistant_context import (
    AdminAssistantContextRepository,
)
from backend.database.repositories.base import NotFoundError

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def repository(tmp_path: Path) -> AdminAssistantContextRepository:
    database_path = tmp_path / "context.db"
    initialize_database(database_path)
    return AdminAssistantContextRepository(database_path)


def test_create_and_get_context_snapshot(repository: AdminAssistantContextRepository) -> None:
    snapshot = repository.create_context_snapshot(
        {
            "page_id": "datasets",
            "tab_id": "Records",
            "sanitized_context": {"filter": "pending_review", "api_key": "secret-value"},
            "registry_version": "v1",
            "created_by_admin_public_id": ADMIN_ID,
        }
    )
    assert snapshot["page_id"] == "datasets"
    assert snapshot["sanitized_context"]["api_key"] == "[REDACTED]"

    fetched = repository.get_context_snapshot(snapshot["public_id"])
    assert fetched == snapshot

    with pytest.raises(NotFoundError):
        repository.get_context_snapshot("does-not-exist")


def test_list_context_snapshots(repository: AdminAssistantContextRepository) -> None:
    for i in range(3):
        repository.create_context_snapshot(
            {
                "page_id": f"page-{i}",
                "registry_version": "v1",
                "created_by_admin_public_id": ADMIN_ID,
            }
        )
    items = repository.list_context_snapshots(limit=10)
    assert len(items) == 3


def test_tool_invocation_lifecycle(repository: AdminAssistantContextRepository) -> None:
    invocation = repository.create_tool_invocation(
        {
            "tool_name": "get_dashboard_overview",
            "mode": "guide",
            "input_summary": {},
            "performed_by_admin_public_id": ADMIN_ID,
        }
    )
    assert invocation["status"] == "succeeded"
    assert invocation["completed_at"] is None

    completed = repository.complete_tool_invocation(
        invocation["public_id"],
        status="succeeded",
        result_summary={"count": 5, "password": "hunter2"},
    )
    assert completed["completed_at"] is not None
    assert completed["result_summary"]["password"] == "[REDACTED]"
    assert completed["result_summary"]["count"] == 5

    with pytest.raises(NotFoundError):
        repository.complete_tool_invocation(
            "does-not-exist", status="failed", result_summary={}
        )


def test_list_tool_invocations(repository: AdminAssistantContextRepository) -> None:
    for i in range(2):
        repository.create_tool_invocation(
            {
                "tool_name": f"tool-{i}",
                "mode": "data",
                "performed_by_admin_public_id": ADMIN_ID,
            }
        )
    items = repository.list_tool_invocations(limit=10)
    assert len(items) == 2


def test_feedback_create_and_list(repository: AdminAssistantContextRepository) -> None:
    feedback = repository.create_feedback(
        {
            "rating": "helpful",
            "registry_version": "v1",
            "submitted_by_admin_public_id": ADMIN_ID,
            "page_id": "datasets",
            "comment": "Clear guidance",
        }
    )
    assert feedback["rating"] == "helpful"
    fetched = repository.get_feedback(feedback["public_id"])
    assert fetched == feedback

    items = repository.list_feedback(limit=10)
    assert len(items) == 1

    with pytest.raises(NotFoundError):
        repository.get_feedback("does-not-exist")
