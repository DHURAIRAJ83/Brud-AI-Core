"""MB-24: Public Plugin Policy Check -- the Step 12 integration point
Public Chat Runtime (and, per Step 13, Admin Assistant) calls before
ever considering a plugin tool. Fully public (no admin auth, no CSRF,
matching Phase 18/MB-23's own public-route convention), rate-limited
with the same `check_rate_limit()` those routes already use. This
route never reveals a secret -- no execution token, no token hash, no
internal database id, no admin identity -- only four booleans.
`is_public_chat` is always forced `True` here; a caller cannot spoof
elevated, non-public-chat access through this route.
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.api.dependencies import SettingsDependency
from backend.core.exceptions import BrudError
from backend.services.mini_brain_plugin_governance_service import MiniBrainPluginGovernanceService
from backend.services.public_chat_rate_limiter import check_rate_limit

router = APIRouter(prefix="/public/plugin-policy", tags=["public-plugin-policy"])


class PluginPolicyRateLimited(BrudError):
    status_code = 429
    code = "PLUGIN_POLICY_RATE_LIMITED"

    def __init__(self) -> None:
        super().__init__("Too many requests. Please wait a moment and try again.")


def _client_key(request: Request) -> str:
    client = request.client
    return client.host if client else "unknown"


@router.get("/check")
async def check_plugin_policy(
    request: Request, settings: SettingsDependency,
    plugin_id: str = Query(min_length=1, max_length=100), scope_key: str = Query(min_length=1, max_length=100),
):
    allowed = check_rate_limit(
        _client_key(request), max_requests=settings.public_chat_rate_limit_max_requests,
        window_seconds=settings.public_chat_rate_limit_window_seconds,
    )
    if not allowed:
        raise PluginPolicyRateLimited()

    service = MiniBrainPluginGovernanceService(settings)
    return service.check_plugin_policy(plugin_id, scope_key=scope_key, is_public_chat=True)


__all__ = ["router"]
