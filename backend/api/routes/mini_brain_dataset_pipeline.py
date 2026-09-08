"""Phase 2.7G: real-time, read-only training-readiness reporting for a
(Dataset Version, Core Model Version) pair. Independent prefix
(`/admin/mini-brain/dataset-pipeline`), one GET route -- this router
never mutates anything; it only runs the real
`MiniBrainDatasetPipelineService.check_readiness()` gate and reports its
real result. No activation control, no release control, no "start
training" action lives here.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.auth import require_admin
from backend.api.dependencies import SettingsDependency
from backend.services.mini_brain_dataset_pipeline_service import MiniBrainDatasetPipelineService

router = APIRouter(
    prefix="/admin/mini-brain/dataset-pipeline",
    tags=["admin-mini-brain-dataset-pipeline"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainDatasetPipelineService:
    return MiniBrainDatasetPipelineService(settings)


@router.get("/readiness")
async def check_readiness(
    settings: SettingsDependency,
    dataset_version_public_id: str = Query(...),
    core_model_version_public_id: str = Query(...),
):
    return service(settings).check_readiness(
        dataset_version_public_id=dataset_version_public_id,
        core_model_version_public_id=core_model_version_public_id,
    )


@router.get("/readiness/contract")
async def readiness_contract(
    settings: SettingsDependency,
    dataset_version_public_id: str = Query(...),
    core_model_version_public_id: str = Query(...),
):
    """Phase 2.7H: the structured READY/NOT_READY/BLOCKED Training
    Dataset Readiness contract (mission Part 2/11) -- still read-only,
    still no mutation, no activation, no release control."""

    return service(settings).readiness_contract(
        dataset_version_public_id=dataset_version_public_id,
        core_model_version_public_id=core_model_version_public_id,
    )
