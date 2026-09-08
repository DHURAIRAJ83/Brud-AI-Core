"""Global per-client-IP rate limiting (Phase 6B-3).

Phase 6A found no rate-limiting middleware anywhere in the application.
This is a coarse, global safety net -- a fixed-window limiter applied to
every request by client IP -- reusing the same in-process
`check_rate_limit` helper Phase 5's public-chat and trusted-web work
already established (`public_chat_rate_limiter.py`) rather than adding a
new dependency. Route-specific limiters (public chat, trusted web, tool
execution) still apply on top of this and are unaffected.

`request.client.host` is only the real client IP when the process trusts
`X-Forwarded-For` from its proxy -- see `deploy/scripts/start-*.sh` and
`BRUD_TRUST_PROXY_HEADERS`/`BRUD_TRUSTED_PROXY_IPS`. Without that, every
request behind a reverse proxy shares one IP (the proxy's) and this
limiter degrades to a single shared budget for all proxied clients --
a safe fallback, but proxy trust should be configured in production.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.core.config import Settings
from backend.services.public_chat_rate_limiter import check_rate_limit

_EXEMPT_PATHS = {
    "/health",
    "/ready",
    "/status",
    "/api/health",
    "/api/ready",
    "/api/status",
    "/api/version",
}


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path in _EXEMPT_PATHS:
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        allowed = check_rate_limit(
            f"http:{client_host}",
            max_requests=self._settings.http_rate_limit_max_requests,
            window_seconds=self._settings.http_rate_limit_window_seconds,
        )
        if not allowed:
            return JSONResponse(status_code=429, content={"detail": "rate_limited"})
        return await call_next(request)
