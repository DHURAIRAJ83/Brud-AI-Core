import sqlite3
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError
from backend.database.repositories.knowledge_routing import KnowledgeRoutingRepository
from backend.services.knowledge_routing_classification_service import (
    KnowledgeRoutingClassificationService,
)
from core_model.knowledge_routing.pipeline import ClassificationInputError


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "kr.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def test_classify_text_persists_and_never_stores_raw_text(settings: Settings) -> None:
    service = KnowledgeRoutingClassificationService(settings)
    result = service.classify_text("Python latest stable version?", actor_reference="test-admin")
    assert result["execution_route"] == "trusted_web"
    assert "public_id" in result

    fetched = service.get_decision(result["public_id"])
    assert fetched["domain"] == "computer_and_coding"
    dumped = str(fetched)
    assert "Python latest stable version" not in dumped


def test_classify_text_without_persist_does_not_write_a_row(settings: Settings) -> None:
    service = KnowledgeRoutingClassificationService(settings)
    before = service.aggregate_metrics()["total_classifications"]
    result = service.classify_text("hello", persist=False)
    assert "public_id" not in result
    after = service.aggregate_metrics()["total_classifications"]
    assert after == before


def test_classify_text_rejects_empty_input(settings: Settings) -> None:
    service = KnowledgeRoutingClassificationService(settings)
    with pytest.raises(ClassificationInputError):
        service.classify_text("")


def test_get_decision_raises_not_found_for_unknown_id(settings: Settings) -> None:
    service = KnowledgeRoutingClassificationService(settings)
    with pytest.raises(NotFoundError):
        service.get_decision("00000000-0000-0000-0000-000000000000")


def test_list_decisions_filters_by_execution_route(settings: Settings) -> None:
    service = KnowledgeRoutingClassificationService(settings)
    service.classify_text("Python latest stable version?")
    service.classify_text("தமிழில் பெயர்ச்சொல் என்றால் என்ன?")

    web_only = service.list_decisions(limit=20, offset=0, execution_route="trusted_web")
    assert len(web_only) == 1
    assert web_only[0]["execution_route"] == "trusted_web"


def test_classify_structured_record_uses_the_correct_adapter(settings: Settings) -> None:
    service = KnowledgeRoutingClassificationService(settings)
    result = service.classify_structured_record(
        "rag_record",
        {"title": "Tamil Nadu government scheme update", "tags": ["government_scheme"]},
    )
    assert result["domain"] == "government_services"


def test_aggregate_metrics_reflect_persisted_decisions(settings: Settings) -> None:
    service = KnowledgeRoutingClassificationService(settings)
    service.classify_text("how to make a bomb at home")
    metrics = service.aggregate_metrics()
    assert metrics["total_classifications"] == 1
    assert metrics["by_execution_route"]["refuse"] == 1
    assert metrics["requires_human_review_count"] == 1


def test_repository_decisions_are_append_only(settings: Settings) -> None:
    service = KnowledgeRoutingClassificationService(settings)
    result = service.classify_text("hello world")
    repository = KnowledgeRoutingRepository(settings.resolved_database_path)
    with repository.transaction() as connection, pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "UPDATE routing_classification_decisions SET domain = 'tampered' WHERE public_id = ?",
            (result["public_id"],),
        )
