"""Top-level API router."""

from fastapi import APIRouter

from backend.api.route_registry import ROUTE_PLUGINS, load_plugins
from backend.core.config import get_settings

api_router = APIRouter(prefix="/api")
settings = get_settings()
mode = settings.deployment_mode

# Phase 5D-C Commit 1: registration is driven by the declarative
# ROUTE_PLUGINS registry (backend/api/route_registry.py) instead of a
# hand-written sequence of include_router() calls -- same routes, same
# prefixes/tags/dependencies/paths, same eager/deferred split introduced
# in Phase 5D-A/5D-B.
#
# Phase 5D-C Commit 2: deployment_mode now decides which subset of
# ROUTE_PLUGINS actually loads. "dev" (the default) and "admin" preserve
# the exact prior behavior -- including defer_admin_tool_routes, kept
# working for backward compatibility. "public" and "worker" are new,
# narrower startup paths that never import the admin-only route modules
# at all.
_EAGER_PLUGINS = tuple(plugin for plugin in ROUTE_PLUGINS if plugin.enabled_by_default)
_DEFERRED_PLUGINS = tuple(plugin for plugin in ROUTE_PLUGINS if not plugin.enabled_by_default)

if mode in ("dev", "admin"):
    load_plugins(api_router, mode=mode, plugins=_EAGER_PLUGINS)
    if settings.defer_admin_tool_routes:
        pass
    else:
        load_plugins(api_router, mode=mode, plugins=_DEFERRED_PLUGINS)
elif mode == "public":
    load_plugins(api_router, mode="public", plugins=_EAGER_PLUGINS)
elif mode == "worker":
    load_plugins(api_router, mode="worker", plugins=_EAGER_PLUGINS)
else:
    raise RuntimeError(f"Unsupported deployment mode: {mode}")


def register_deferred_admin_routes() -> None:
    """Explicit opt-in hook for a future admin-only startup path.

    When BRUD_DEFER_ADMIN_TOOL_ROUTES=true, Mini Brain / Production
    Readiness / RAG Sandbox / dataset & document admin routes are not
    registered above -- call this once, before serving traffic, to
    register them on demand instead.
    """

    load_plugins(api_router, mode=mode, plugins=_DEFERRED_PLUGINS)
