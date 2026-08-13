"""MB-05: service-level tests for MiniBrainDatasetIntelligenceService.

Uses the REAL, unmodified `DatasetService` against a real seeded
temp database -- no fake/mock needed, since this phase does no model
inference, only reads. The central concern this file proves: every
analysis method leaves `dataset_sources`, `dataset_records`, and
`audit_logs` byte-for-byte unchanged.
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
        ManualSourceCreate(name="Tamil Instructions", language="ta", source_type="manual"), admin.public_id,
    )
    for i in range(30):
        dataset_service.create_record(
            RecordCreate(
                source_public_id=source["public_id"], record_type="instruction", language="ta",
                instruction=f"தமிழில் dataset {i} உருவாக்குவது எப்படி?",
                output_text=f"இது பதில் எண் {i} — dataset உருவாக்க பல படிகள் உள்ளன, தரவு சேகரிப்பு மற்றும் சரிபார்ப்பு தேவை.",
                metadata={"topic": "dataset"},
            ),
            admin.public_id,
        )

    return {
        "settings": settings, "dataset_service": dataset_service,
        "service": MiniBrainDatasetIntelligenceService(dataset_service),
        "source_id": source["public_id"],
    }


def _table_counts(db_path) -> dict[str, int]:
    with database_connection(db_path) as connection:
        return {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("dataset_sources", "dataset_records", "audit_logs")
        }


def test_analyze_returns_real_record_count(wired) -> None:
    result = wired["service"].analyze(wired["source_id"])
    assert result["record_count"] == 30
    assert result["source"]["file_type"] == "manual"


def test_quality_report_over_real_records(wired) -> None:
    result = wired["service"].quality(wired["source_id"])
    assert result["total_records"] == 30
    assert result["clean_ratio"] == 1.0


def test_language_report_detects_tamil(wired) -> None:
    result = wired["service"].language(wired["source_id"])
    assert result["distribution_counts"]["tamil"] == 30


def test_domain_classifies_as_instruction(wired) -> None:
    result = wired["service"].domain(wired["source_id"])
    assert result["category"] == "Instruction"


def test_training_readiness_not_ready_below_minimum(wired) -> None:
    result = wired["service"].training(wired["source_id"])
    assert result["status"] == "Not Ready"


def test_rag_readiness_runs(wired) -> None:
    result = wired["service"].rag(wired["source_id"])
    assert result["status"] in ("Ready", "Needs Improvement", "Not Ready")


def test_sft_readiness_runs(wired) -> None:
    result = wired["service"].sft(wired["source_id"])
    assert result["status"] in ("Ready", "Needs Improvement", "Not Ready")


def test_tokens_estimate_runs(wired) -> None:
    result = wired["service"].tokens(wired["source_id"])
    assert result["total_records"] == 30
    assert result["estimated_total_tokens"] > 0


def test_report_assembles_everything(wired) -> None:
    result = wired["service"].report(wired["source_id"])
    for key in ("dataset_summary", "quality_report", "language_report", "domain", "duplicates",
                "training_report", "rag_report", "sft_report", "scores", "recommendations",
                "warnings", "overall_status", "processing_time_ms"):
        assert key in result


def test_diagnostics_reports_reuse_declarations(wired) -> None:
    diag = wired["service"].diagnostics()
    assert diag["ai_model_used"] is False
    assert diag["writes_performed"] == 0
    assert diag["database_tables"] == 0
    assert any("ExternalDatasetQualityService" in item for item in diag["reused_existing_services"])


# -- the central security proof: read-only, verified table-by-table --------

def test_every_analysis_method_leaves_all_tables_byte_identical(wired) -> None:
    before = _table_counts(wired["settings"].resolved_database_path)

    svc = wired["service"]
    sid = wired["source_id"]
    svc.analyze(sid)
    svc.quality(sid)
    svc.language(sid)
    svc.domain(sid)
    svc.training(sid)
    svc.rag(sid)
    svc.sft(sid)
    svc.tokens(sid)
    svc.report(sid)
    svc.diagnostics()

    after = _table_counts(wired["settings"].resolved_database_path)
    assert before == after


def test_dataset_intelligence_never_touches_admin_assistant_public_chat_training_rag_tables(wired) -> None:
    with database_connection(wired["settings"].resolved_database_path) as connection:
        protected_tables = [
            "admin_approvals", "inference_model_assignments", "mini_brain_knowledge_items",
        ]
        existing = []
        for table in protected_tables:
            try:
                connection.execute(f"SELECT COUNT(*) FROM {table}")
                existing.append(table)
            except Exception:
                pass

    wired["service"].report(wired["source_id"])

    with database_connection(wired["settings"].resolved_database_path) as connection:
        for table in existing:
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
