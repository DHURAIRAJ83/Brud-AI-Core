"""MB-04: Brud Mini Brain CPU Runtime -- authenticated admin-only APIs.

Independent prefix (`/admin/mini-brain/runtime`), independent of
`inference_runtime.py` (the main InferenceRuntimeService's own
routes) -- this is Mini Brain's own runtime, never the shared one.
`generate` is the one route with real safety weight: it only ever
accepts a Response Plan-shaped payload, enforced by
`MiniBrainInMemoryModelLoader.generate_response` itself, not just
by this route's validation.
"""

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.models.mini_brain_runtime import GenerateRequest, LoadModelRequest, ModelRegisterRequest
from backend.services.mini_brain_runtime_manager_service import MiniBrainInMemoryModelLoader

router = APIRouter(
    prefix="/admin/mini-brain/runtime",
    tags=["admin-mini-brain-runtime"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainInMemoryModelLoader:
    return MiniBrainInMemoryModelLoader()


@router.post("/models")
async def register_model(payload: ModelRegisterRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).register_model(
        name=payload.name, path=payload.path, quantization=payload.quantization,
        context_length=payload.context_length,
    )


@router.get("/models")
async def list_models(settings: SettingsDependency):
    return service(settings).list_models()


@router.get("/models/{public_id}")
async def model_information(public_id: str, settings: SettingsDependency):
    return service(settings).model_information(public_id)


@router.post("/load")
async def load_model(payload: LoadModelRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).load_model(payload.model_public_id)


@router.post("/unload")
async def unload_model(settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).unload_model()


@router.post("/reload")
async def reload_model(settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).reload_model()


@router.post("/switch")
async def switch_model(payload: LoadModelRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).switch_model(payload.model_public_id)


@router.get("/status")
async def status(settings: SettingsDependency):
    return service(settings).status()


@router.get("/statistics")
async def statistics(settings: SettingsDependency):
    return service(settings).runtime_statistics()


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()


@router.get("/health")
async def health(settings: SettingsDependency):
    return service(settings).health()


@router.post("/generate")
async def generate(payload: GenerateRequest, settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).generate_response(
        payload.response_plan, max_tokens=payload.max_tokens, timeout_seconds=payload.timeout_seconds,
    )
