"""Security response headers middleware (Phase 6B-3).

Defense-in-depth for the direct-to-backend access path: the Phase 6A
audit found these headers already present at the reverse-proxy layer
(nginx.conf.example / Caddyfile.example) but nowhere in the app itself,
so a request that reaches uvicorn without going through the proxy (a
misconfigured firewall, worker mode, local debugging) got none of them.
The reverse-proxy templates now rely on this middleware instead of
setting the same headers a second time.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_STATIC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Permitted-Cross-Domain-Policies": "none",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for name, value in _STATIC_HEADERS.items():
            response.headers.setdefault(name, value)
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security", "max-age=63072000; includeSubDomains"
            )
        return response
