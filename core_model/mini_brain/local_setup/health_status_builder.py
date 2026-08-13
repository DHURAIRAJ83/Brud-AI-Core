"""MB-29: Health Status Builder -- pure. Mirrors MB-27's own
`provider_health_summary.py` shape (a single `health` verdict plus the
inputs that produced it) for the Hardware tab's health badge.
"""

from __future__ import annotations

from typing import Any


def build(*, hardware: dict[str, Any], local_model_configured: bool, local_model_available: bool) -> dict[str, Any]:
    if local_model_available:
        health = "healthy"
    elif local_model_configured:
        health = "degraded"
    elif hardware.get("total_ram_gb", 0) <= 0:
        health = "unknown"
    else:
        health = "unconfigured"

    return {
        "health": health,
        "ram_tier": hardware.get("recommended_ram_tier"),
        "disk_free_gb": hardware.get("disk_free_gb"),
        "local_model_configured": local_model_configured,
        "local_model_available": local_model_available,
    }
