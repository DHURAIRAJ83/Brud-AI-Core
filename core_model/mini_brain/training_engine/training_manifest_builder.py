"""MB-22: Training Manifest Builder -- pure. Assembles the manifest
describing what this job intends to run before any training starts --
the source packages, resource plan, and reproducibility fingerprint.
Never lists itself in its own artifact set, matching MB-18/19/20/21's
own manifest-builder precedent.
"""

from __future__ import annotations

from typing import Any


def build_training_manifest(
    *, job_public_id: str, topic: str, training_package_session_public_id: str,
    release_governance_session_public_id: str, execution_mode: str, resource_plan: dict[str, Any],
    fingerprint: dict[str, Any], created_at: str,
) -> dict[str, Any]:
    return {
        "job_public_id": job_public_id, "topic": topic,
        "training_package_session_public_id": training_package_session_public_id,
        "release_governance_session_public_id": release_governance_session_public_id,
        "execution_mode": execution_mode, "resource_plan": resource_plan, "fingerprint": fingerprint,
        "created_at": created_at, "model_weights_included": False, "training_executed": False,
        "disclosure": (
            "this manifest describes intent only -- it is built before training starts and never "
            "claims training has been executed or that any model weights are included"
        ),
    }
