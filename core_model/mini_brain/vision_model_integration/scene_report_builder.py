"""MB-15: Scene Understanding report -- pure. Wraps the backend's own
`classify_scene()` output. Never maps a scene to a fixed vocabulary
(Indoor/Outdoor/Nature/Classroom/...) itself -- that would mean
inventing a category the model never actually said. The scene label is
always exactly what the provider returned, or `None` when unavailable.
"""

from __future__ import annotations

from typing import Any


def build_scene_report(*, provider_available: bool, scene: str | None, confidence: float | None) -> dict[str, Any]:
    if not provider_available or not scene:
        return {
            "provider_available": provider_available, "scene": None, "confidence": None,
            "disclosure": "no vision provider produced a real scene classification for this session",
        }
    return {"provider_available": True, "scene": scene, "confidence": confidence}
