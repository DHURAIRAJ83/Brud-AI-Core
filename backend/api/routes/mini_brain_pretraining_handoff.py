"""Phase 2.7F: governed handoff of a real, verified MB-22 checkpoint into
the production `pretraining_checkpoints` table. Independent prefix
(`/admin/mini-brain/pretraining-handoff`), its own small router, calling
only `MiniBrainPretrainingHandoffService` -- never a direct write to
`pretraining_jobs`/`pretraining_checkpoints` from here, never a call to
`ModelReleaseService.activate()` or anything that releases/activates a
model. Registration is the only operation this router exposes.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.services.mini_brain_pretraining_handoff_service import MiniBrainPretrainingHandoffService

router = APIRouter(
    prefix="/admin/mini-brain/pretraining-handoff",
    tags=["admin-mini-brain-pretraining-handoff"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainPretrainingHandoffService:
    return MiniBrainPretrainingHandoffService(settings)


@router.post("/jobs/{job_id}/checkpoints/{checkpoint_id}/register")
async def register_checkpoint(
    job_id: str, checkpoint_id: str, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).register_checkpoint(job_id, checkpoint_id, admin.admin.public_id)
