"""Phase 1 admin dashboard API."""

from fastapi import APIRouter, Depends

from backend.api.auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.get("/overview")
async def overview() -> dict[str, str | int]:
    return {
        "project": "Brud AI",
        "phase": 1,
        "chatbot_status": "foundation_ready",
        "admin_dashboard_status": "foundation_ready",
        "core_model_status": "not_trained",
        "dataset_records": 0,
        "training_jobs": 0,
        "registered_models": 0,
    }
