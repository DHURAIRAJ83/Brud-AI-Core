"""MB-31G: Mini Brain Health -- a single read-only, admin-only
diagnostics endpoint composed entirely from RuntimeManagerService and
MiniBrainLlmRuntimeService. No model loading, no network calls; see
`backend/services/mini_brain_health_service.py` for the composition.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_health import MiniBrainHealthSnapshot
from backend.services.mini_brain_health_service import MiniBrainHealthService

router = APIRouter(
    prefix="/admin/mini-brain",
    tags=["admin-mini-brain-health"],
    dependencies=[Depends(require_admin)],
)


# Named "runtime-health", not "health" -- `/admin/mini-brain/health`
# already exists (backend/api/routes/mini_brain.py, the MB-01-era
# placeholder module's own generic module-enabled/disabled check).
# Colliding with it would shadow one endpoint depending on router
# registration order; this stays additive and collision-free instead.
@router.get("/runtime-health", response_model=MiniBrainHealthSnapshot)
async def runtime_health(settings: SettingsDependency):
    return MiniBrainHealthService(settings).snapshot()


__all__ = ["router"]
