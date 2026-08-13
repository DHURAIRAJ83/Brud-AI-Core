"""MB-25: Public Plugin Execution -- the Step 8 public-chat entrypoint,
exposed as one rate-limited HTTP route. This route can never grant
itself elevated access: it only ever *consumes* an execution token
that MB-24's own admin-only routes already issued through a real,
admin-gated flow -- it never issues one itself. `execution_mode` is
always forced to `'public_chat'` here; a caller cannot request
`'admin_assistant'` or `'admin_manual'` mode through this route.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from backend.api.dependencies import SettingsDependency
from backend.core.exceptions import BrudError
from backend.models.mini_brain_plugin_runtime import PublicExecuteRequest
from backend.services.mini_brain_plugin_runtime_service import MiniBrainPluginRuntimeService
from backend.services.public_chat_rate_limiter import check_rate_limit

router = APIRouter(prefix="/public/plugin-runtime", tags=["public-plugin-runtime"])


class PluginRuntimeRateLimited(BrudError):
    status_code = 429
    code = "PLUGIN_RUNTIME_RATE_LIMITED"

    def __init__(self) -> None:
        super().__init__("Too many requests. Please wait a moment and try again.")


def _client_key(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


@router.post("/execute")
async def execute(request: Request, payload: PublicExecuteRequest, settings: SettingsDependency):
    allowed = check_rate_limit(
        _client_key(request), max_requests=settings.public_chat_rate_limit_max_requests,
        window_seconds=settings.public_chat_rate_limit_window_seconds,
    )
    if not allowed:
        raise PluginRuntimeRateLimited()

    service = MiniBrainPluginRuntimeService(settings)
    user_id_hash = service.governance.hash_identity(raw_identity=payload.raw_user_identity)
    return service.execute_for_public_chat(
        plugin_public_id=payload.plugin_public_id, scope_key=payload.scope_key, arguments=payload.arguments,
        requester_user_id_hash=user_id_hash, execution_token=payload.execution_token,
    )


__all__ = ["router"]
