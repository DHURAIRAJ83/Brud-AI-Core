"""Phase 1 admin dashboard API."""

from fastapi import APIRouter, Depends

from backend import PROJECT_PHASE
from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.connection import database_connection

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


def _count(connection, query: str, params: tuple = ()) -> int:
    return connection.execute(query, params).fetchone()[0]


@router.get("/overview")
async def overview(settings: SettingsDependency) -> dict[str, str | int]:
    with database_connection(settings.resolved_database_path) as connection:
        dataset_records = _count(connection, "SELECT COUNT(*) FROM dataset_records")
        dataset_sources = _count(connection, "SELECT COUNT(*) FROM dataset_sources")
        ready_dataset_versions = _count(
            connection, "SELECT COUNT(*) FROM dataset_versions WHERE status = ?", ("ready",)
        )
        registered_tokenizer_versions = _count(
            connection, "SELECT COUNT(*) FROM tokenizer_versions"
        )
        registered_core_model_versions = _count(
            connection, "SELECT COUNT(*) FROM core_model_versions"
        )
        pretraining_jobs = _count(connection, "SELECT COUNT(*) FROM pretraining_jobs")
        completed_pretraining_jobs = _count(
            connection, "SELECT COUNT(*) FROM pretraining_jobs WHERE status = ?", ("completed",)
        )
    return {
        "project": "Brud AI",
        "phase": PROJECT_PHASE,
        "chatbot_status": "foundation_ready",
        "admin_dashboard_status": "foundation_ready",
        "core_model_status": "not_trained",
        "dataset_records": dataset_records,
        "dataset_sources": dataset_sources,
        "ready_dataset_versions": ready_dataset_versions,
        "training_jobs": pretraining_jobs,
        "completed_training_jobs": completed_pretraining_jobs,
        "registered_tokenizer_versions": registered_tokenizer_versions,
        "registered_models": registered_core_model_versions,
    }
