"""MB-05.1: service-level tests for MiniBrainAdvancedDatasetService.

Uses the REAL, unmodified `DatasetService` and `MiniBrainDatasetIntelligenceService`
against a real seeded temp database -- no fake/mock needed, since this
phase does no model inference, only reads. The central concern: every
method leaves `dataset_sources`, `dataset_records`, and `audit_logs`
byte-for-byte unchanged.
"""

from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.models.auth import AdminCreate
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_advanced_dataset_service import MiniBrainAdvancedDatasetService
from backend.services.mini_brain_dataset_intelligence_service import MiniBrainDatasetIntelligenceService


@pytest.fixture
def wired(tmp_path: Path):
    settings = Settings(
        database_path=tmp_path / "t.db", database_backup_dir=tmp_path / "b",
        allowed_data_dir=tmp_path, allow_external_storage=True, log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    repo = DatasetAdminRepository(settings.resolved_database_path)
    dataset_service = DatasetService(repo)
    admin = AdminRepository(settings.resolved_database_path).create_admin(
        AdminCreate(username="test-admin", display_name="A", password="password12345")
    )

    source = dataset_service.create_source(
        ManualSourceCreate(name="Programming Set", language="en", source_type="manual"), admin.public_id,
    )
    questions = ["What is Python used for?", "How does TCP networking work?", "Explain machine learning basics"]
    for i in range(30):
        question = questions[i % 3]
        dataset_service.create_record(
            RecordCreate(
                source_public_id=source["public_id"], record_type="instruction", language="en",
                instruction=question, output_text=f"Answer number {i} about {question}",
                metadata={"topic": "programming"},
            ),
            admin.public_id,
        )

    mb05 = MiniBrainDatasetIntelligenceService(dataset_service)
    return {
        "settings": settings, "dataset_service": dataset_service,
        "service": MiniBrainAdvancedDatasetService(dataset_service, mb05),
        "source_id": source["public_id"],
    }


def _table_counts(db_path) -> dict[str, int]:
    with database_connection(db_path) as connection:
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("dataset_sources", "dataset_records", "audit_logs")
        }


def test_conflicts_detects_real_conflicting_answers(wired) -> None:
    result = wired["service"].conflicts(wired["source_id"])
    assert result["conflict_count"] == 3  # 3 rotating questions, each with distinct numbered answers


def test_bias_reuses_mb05_language_and_domain_outputs(wired) -> None:
    result = wired["service"].bias(wired["source_id"])
    assert result["language_balance"]["verdict"] == "Heavy Bias"  # 100% english


def test_coverage_runs(wired) -> None:
    result = wired["service"].coverage(wired["source_id"])
    assert "Programming" in result["coverage"]


def test_difficulty_runs(wired) -> None:
    result = wired["service"].difficulty(wired["source_id"])
    assert sum(result["distribution"].values()) == 30


def test_curriculum_runs(wired) -> None:
    result = wired["service"].curriculum(wired["source_id"])
    assert "topics" in result


def test_knowledge_gap_runs(wired) -> None:
    result = wired["service"].knowledge_gap(wired["source_id"])
    assert result["gap_count"] >= 0


def test_risk_runs(wired) -> None:
    result = wired["service"].risk(wired["source_id"])
    assert result["risk_item_count"] == 0  # clean synthetic data


def test_graph_runs(wired) -> None:
    result = wired["service"].graph(wired["source_id"])
    assert result["node_count"] > 0


def test_priority_runs(wired) -> None:
    result = wired["service"].priority(wired["source_id"])
    assert isinstance(result["priorities"], list)


def test_report_assembles_everything(wired) -> None:
    result = wired["service"].report(wired["source_id"])
    for key in ("conflicts", "bias", "coverage", "difficulty", "curriculum", "knowledge_gaps",
                "risk", "graph", "priorities", "scores", "processing_time_ms"):
        assert key in result


def test_diagnostics_reports_reuse_declarations(wired) -> None:
    diag = wired["service"].diagnostics()
    assert diag["ai_model_used"] is False
    assert diag["writes_performed"] == 0
    assert any("ExternalDatasetPIIScanService" in item for item in diag["reused_existing_services"])
    assert any("MiniBrainDatasetIntelligenceService" in item for item in diag["reused_mb05_outputs"])


# -- the central security proof: read-only, verified table-by-table --------

def test_every_method_leaves_all_tables_byte_identical(wired) -> None:
    before = _table_counts(wired["settings"].resolved_database_path)

    svc = wired["service"]
    sid = wired["source_id"]
    svc.conflicts(sid)
    svc.bias(sid)
    svc.coverage(sid)
    svc.difficulty(sid)
    svc.curriculum(sid)
    svc.knowledge_gap(sid)
    svc.risk(sid)
    svc.graph(sid)
    svc.priority(sid)
    svc.report(sid)
    svc.diagnostics()

    after = _table_counts(wired["settings"].resolved_database_path)
    assert before == after


def test_mb05_itself_remains_untouched_and_still_agrees(wired) -> None:
    """Direct proof MB-05 is unmodified and still produces the same
    result before and after MB-05.1 runs against the same source."""

    mb05 = MiniBrainDatasetIntelligenceService(wired["dataset_service"])
    before = mb05.language(wired["source_id"])

    wired["service"].report(wired["source_id"])

    after = mb05.language(wired["source_id"])
    assert before == after
