"""MB-20: Reproducibility Hasher -- pure. Reuses `core_model.release.
manifest.manifest_checksum()`/`verify_manifest_checksum()` directly --
the same real SHA-256-over-canonical-JSON checksum functions the
Release Pipeline, MB-18, and MB-19 all already use, never a second
hashing implementation.
"""

from __future__ import annotations

from typing import Any

from core_model.release.manifest import manifest_checksum, verify_manifest_checksum


def build_reproducibility_record(
    *, release_manifest: dict[str, Any], source_dataset_public_ids: list[str],
    source_rag_session_public_ids: list[str], source_training_package_public_id: str | None,
    source_evaluation_session_public_id: str | None,
) -> dict[str, Any]:
    manifest_hash = manifest_checksum(release_manifest)
    inputs_hash = manifest_checksum({
        "source_dataset_public_ids": sorted(source_dataset_public_ids),
        "source_rag_session_public_ids": sorted(source_rag_session_public_ids),
        "source_training_package_public_id": source_training_package_public_id,
        "source_evaluation_session_public_id": source_evaluation_session_public_id,
    })

    return {
        "manifest_checksum_sha256": manifest_hash, "input_set_checksum_sha256": inputs_hash,
        "disclosure": (
            "the same source dataset/RAG-session/training-package/evaluation-session public_ids will "
            "always reproduce this identical input_set_checksum_sha256 -- verified by "
            "verify_manifest_checksum(), the same real function the Release Pipeline uses"
        ),
    }


def verify_reproducibility(*, manifest_json: str, expected_checksum: str) -> bool:
    return verify_manifest_checksum(manifest_json, expected_checksum)
