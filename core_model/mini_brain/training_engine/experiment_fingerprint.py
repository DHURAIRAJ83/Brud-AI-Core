"""MB-22: Experiment Fingerprint -- pure. Reuses `core_model.release.
manifest.manifest_checksum()` directly -- the same real SHA-256-over-
canonical-JSON checksum function the Release Pipeline and MB-18/19/20/
21 all already use, never a second hashing implementation.
"""

from __future__ import annotations

from typing import Any

from core_model.release.manifest import manifest_checksum


def build_experiment_fingerprint(
    *, training_package_session_public_id: str, release_governance_session_public_id: str,
    execution_mode: str, resource_plan: dict[str, Any],
) -> dict[str, Any]:
    fingerprint_inputs = {
        "training_package_session_public_id": training_package_session_public_id,
        "release_governance_session_public_id": release_governance_session_public_id,
        "execution_mode": execution_mode,
        "cpu_thread_count": resource_plan.get("cpu_thread_count"),
        "gpu_required": resource_plan.get("gpu_required"),
    }
    fingerprint = manifest_checksum(fingerprint_inputs)
    return {
        "fingerprint_sha256": fingerprint, "fingerprint_inputs": fingerprint_inputs,
        "disclosure": (
            "the same source package/release public_ids and execution mode will always reproduce this "
            "identical fingerprint -- real training metrics themselves are never deterministic across "
            "real hardware runs, so only the job's own inputs are fingerprinted, never its outputs"
        ),
    }
