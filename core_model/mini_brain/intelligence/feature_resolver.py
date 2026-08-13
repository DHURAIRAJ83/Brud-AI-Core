"""Feature Resolver -- extracts dashboard/backend/API/repository/
module facts from already-matched Knowledge Core items. Pure
aggregation over the exact fields those items already carry
(category, related_services, related_apis, related_features, source)
-- never a guess about what a page or service does beyond what its
own knowledge item already states.
"""

from __future__ import annotations

from typing import Any


def resolve_features(items: list[dict[str, Any]]) -> dict[str, Any]:
    dashboard_pages = sorted({i["title"] for i in items if i.get("category") == "Page"})
    modules = sorted({i["title"] for i in items if i.get("category") == "Module"})
    features_and_components = sorted({
        i["title"] for i in items if i.get("category") in ("Feature", "Component")
    })
    backend_services = sorted({s for i in items for s in i.get("related_services", [])})
    apis = sorted({a for i in items for a in i.get("related_apis", [])})
    related_features = sorted({f for i in items for f in i.get("related_features", [])})

    repositories = sorted({
        i["source"] for i in items if "repositories/" in i.get("source", "")
    })
    database_areas = sorted({
        i["source"] for i in items
        if "schema.py" in i.get("source", "") or "migrations.py" in i.get("source", "")
    })

    return {
        "dashboard_pages": dashboard_pages,
        "modules": modules,
        "features": features_and_components + related_features,
        "backend_services": backend_services,
        "apis": apis,
        "repositories": repositories,
        "database_areas": database_areas,
    }
