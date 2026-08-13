"""Top-level API router."""

from fastapi import APIRouter

from backend.api.route_registry import ROUTE_PLUGINS, load_plugins
from backend.core.config import get_settings

api_router = APIRouter(prefix="/api")

# Phase 5D-C Commit 1: registration is now driven by the declarative
# ROUTE_PLUGINS registry (backend/api/route_registry.py) instead of a
# hand-written sequence of include_router() calls -- same routes, same
# prefixes/tags/dependencies/paths, same eager/deferred split introduced
# in Phase 5D-A/5D-B. No deployment-mode filtering yet (Commit 2).
_EAGER_PLUGINS = tuple(plugin for plugin in ROUTE_PLUGINS if plugin.enabled_by_default)
_DEFERRED_PLUGINS = tuple(plugin for plugin in ROUTE_PLUGINS if not plugin.enabled_by_default)

load_plugins(api_router, _EAGER_PLUGINS)

if get_settings().defer_admin_tool_routes is False:
    load_plugins(api_router, _DEFERRED_PLUGINS)


def register_deferred_admin_routes() -> None:
    """Explicit opt-in hook for a future admin-only startup path.

    When BRUD_DEFER_ADMIN_TOOL_ROUTES=true, Mini Brain / Production
    Readiness / RAG Sandbox / dataset & document admin routes are not
    registered above -- call this once, before serving traffic, to
    register them on demand instead.
    """

    load_plugins(api_router, _DEFERRED_PLUGINS)
