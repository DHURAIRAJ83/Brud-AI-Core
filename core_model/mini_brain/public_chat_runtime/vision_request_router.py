"""MB-23: Vision Request Router -- pure. Derives a `used_vision` flag
from the query's own classified category and the response's already-
computed source types -- MB-23 never runs vision inference itself; the
real vision provider is only ever reached through the existing chat
orchestration path.
"""

from __future__ import annotations

from typing import Any


def derive_vision_usage(*, query_category: str, source_types: list[str]) -> dict[str, Any]:
    used_vision = query_category == "vision" or "vision" in source_types
    return {
        "used_vision": used_vision,
        "disclosure": "derived from the query's own coarse category and the response's already-computed source types -- no vision inference is performed by this module",
    }
