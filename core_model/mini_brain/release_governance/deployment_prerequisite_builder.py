"""MB-20: Deployment Prerequisite Builder -- pure. A fixed, disclosed
checklist of conditions that would need to be true before a human
operator could deploy this release candidate -- documentation only.
This module never verifies any of these against a live system and
never triggers any deployment action itself.
"""

from __future__ import annotations

from typing import Any

PREREQUISITES = (
    {"name": "runtime_backend_configured", "description": "A CPU-safe runtime backend is configured and reachable."},
    {"name": "model_artifact_present_locally", "description": "The release candidate's model artifact exists on the target host's local disk."},
    {"name": "tokenizer_present_locally", "description": "The matching tokenizer version is present on the target host."},
    {"name": "reverse_proxy_configured", "description": "A reverse proxy / gateway is configured in front of the runtime."},
    {"name": "monitoring_configured", "description": "Request/error/latency monitoring is configured for the runtime endpoint."},
    {"name": "rollback_target_available", "description": "The previously active release remains available as a rollback target."},
    {"name": "operator_briefed", "description": "The on-call operator has reviewed this release's own operator instructions."},
)


def build_deployment_prerequisites(*, compatibility_matrix: dict[str, Any]) -> dict[str, Any]:
    items = [dict(item, verified=False) for item in PREREQUISITES]
    if compatibility_matrix.get("cpu_only_feasible") is False:
        items.append({
            "name": "gpu_resource_provisioned", "description": "This release is not CPU-only feasible per its own compatibility matrix -- a GPU-capable host must be provisioned.",
            "verified": False,
        })

    return {
        "items": items, "item_count": len(items),
        "all_verified": False,
        "disclosure": (
            "a fixed, disclosed checklist of conditions a human operator would need to confirm before "
            "deployment -- this module never verifies any item against a live system and never "
            "triggers deployment itself; every item is deliberately recorded as unverified"
        ),
    }
