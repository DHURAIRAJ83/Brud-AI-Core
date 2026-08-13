"""MB-18: Reproducibility Hasher -- pure. Reuses `core_model.release.
manifest.manifest_checksum()` directly -- the same real SHA-256-over-
canonical-JSON checksum function the Release Pipeline already uses,
never a second hashing implementation. Records the split seed
alongside the manifest checksum so a future run given the identical
inputs and seed can verify it reproduces the identical package.
"""

from __future__ import annotations

from typing import Any

from core_model.release.manifest import manifest_checksum, verify_manifest_checksum


def build_reproducibility_record(
    *, package_manifest: dict[str, Any], split_seed: int, source_dataset_public_ids: list[str],
    source_rag_memory_public_ids: list[str],
) -> dict[str, Any]:
    manifest_hash = manifest_checksum(package_manifest)
    inputs_hash = manifest_checksum({
        "source_dataset_public_ids": sorted(source_dataset_public_ids),
        "source_rag_memory_public_ids": sorted(source_rag_memory_public_ids),
        "split_seed": split_seed,
    })

    return {
        "manifest_checksum_sha256": manifest_hash, "input_set_checksum_sha256": inputs_hash,
        "split_seed": split_seed,
        "disclosure": (
            "the same source dataset/RAG-memory public_id sets and the same split_seed will always "
            "reproduce this identical input_set_checksum_sha256 -- verified by "
            "verify_manifest_checksum(), the same real function the Release Pipeline uses"
        ),
    }


def verify_reproducibility(*, manifest_json: str, expected_checksum: str) -> bool:
    return verify_manifest_checksum(manifest_json, expected_checksum)
