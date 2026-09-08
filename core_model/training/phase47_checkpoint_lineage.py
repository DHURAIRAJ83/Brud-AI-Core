"""Phase 47 Checkpoint Lineage & Cryptographic Integrity Engine.

Guarantees immutable parent-child ancestry, multi-file checksum manifests,
and strict non-destructive checkpoint persistence across training epochs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


class CheckpointLineageError(RuntimeError):
    """Raised when checkpoint manifest, parent hash, or state is invalid/corrupted."""

    pass


@dataclass
class LineageNode:
    checkpoint_id: str
    step: int
    cumulative_tokens: int
    parent_checkpoint_hash: str
    checkpoint_hash: str
    val_loss: float | None
    dataset_manifest_hash: str
    tokenizer_hash: str
    timestamp: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Phase47CheckpointLineage:
    """Manages cryptographic checkpoint binding and immutable DAG ancestry."""

    EXPECTED_FILES = [
        "model_state.pt",
        "optimizer_state.pt",
        "scheduler_state.pt",
        "rng_state.pt",
        "trainer_state.json",
        "config.json",
        "references.json",
    ]

    @staticmethod
    def compute_file_sha256(path: Path) -> str:
        """Computes SHA-256 for a given artifact file."""
        hasher = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def create_checkpoint_manifest(
        cls,
        checkpoint_dir: Path,
        checkpoint_id: str,
        step: int,
        cumulative_tokens: int,
        parent_checkpoint_hash: str,
        val_loss: float | None = None,
        dataset_manifest_hash: str = "",
        tokenizer_hash: str = "sovereign_sp_32k",
    ) -> dict[str, Any]:
        """Creates manifest.json binding all state files and parent lineage hash."""
        file_hashes: dict[str, str] = {}
        for fname in cls.EXPECTED_FILES:
            fpath = checkpoint_dir / fname
            if not fpath.is_file():
                raise CheckpointLineageError(f"Missing required checkpoint file: {fname}")
            file_hashes[fname] = cls.compute_file_sha256(fpath)

        # Compute root checkpoint hash
        hasher = hashlib.sha256()
        hasher.update(parent_checkpoint_hash.encode("utf-8"))
        hasher.update(str(step).encode("utf-8"))
        hasher.update(str(cumulative_tokens).encode("utf-8"))
        for fname in sorted(file_hashes.keys()):
            hasher.update(f"{fname}:{file_hashes[fname]}".encode("utf-8"))
        checkpoint_hash = hasher.hexdigest()

        manifest = {
            "checkpoint_id": checkpoint_id,
            "step": step,
            "cumulative_tokens": cumulative_tokens,
            "parent_checkpoint_hash": parent_checkpoint_hash,
            "checkpoint_hash": checkpoint_hash,
            "val_loss": val_loss,
            "dataset_manifest_hash": dataset_manifest_hash,
            "tokenizer_hash": tokenizer_hash,
            "files": file_hashes,
        }

        manifest_path = checkpoint_dir / "manifest.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2)

        return manifest

    @classmethod
    def verify_checkpoint_integrity(cls, checkpoint_dir: Path) -> dict[str, Any]:
        """Validates all file checksums against manifest.json and re-derives checkpoint hash."""
        manifest_path = checkpoint_dir / "manifest.json"
        if not manifest_path.is_file():
            raise CheckpointLineageError(f"Missing manifest.json in {checkpoint_dir}")

        try:
            with manifest_path.open("r", encoding="utf-8") as handle:
                manifest = json.load(handle)
        except json.JSONDecodeError as exc:
            raise CheckpointLineageError(f"Corrupted manifest.json in {checkpoint_dir}") from exc

        file_hashes = manifest.get("files", {})
        for fname in cls.EXPECTED_FILES:
            fpath = checkpoint_dir / fname
            if not fpath.is_file():
                raise CheckpointLineageError(f"Missing required checkpoint file: {fname}")
            expected_hash = file_hashes.get(fname)
            actual_hash = cls.compute_file_sha256(fpath)
            if actual_hash != expected_hash:
                raise CheckpointLineageError(
                    f"Integrity violation in {fname}: expected {expected_hash}, got {actual_hash}"
                )

        # Re-derive checkpoint hash
        hasher = hashlib.sha256()
        hasher.update(str(manifest.get("parent_checkpoint_hash", "")).encode("utf-8"))
        hasher.update(str(manifest.get("step", 0)).encode("utf-8"))
        hasher.update(str(manifest.get("cumulative_tokens", 0)).encode("utf-8"))
        for fname in sorted(file_hashes.keys()):
            hasher.update(f"{fname}:{file_hashes[fname]}".encode("utf-8"))
        recomputed_hash = hasher.hexdigest()

        if recomputed_hash != manifest.get("checkpoint_hash"):
            raise CheckpointLineageError(
                f"Checkpoint root hash mismatch: {manifest.get('checkpoint_hash')} vs {recomputed_hash}"
            )

        return manifest

    @classmethod
    def verify_lineage_chain(
        cls,
        checkpoints: list[Path],
        expected_root_parent: str = "phase46_checkpoint_step_130_root",
    ) -> list[dict[str, Any]]:
        """Verifies unbroken parent-to-child lineage chain across a sequence of checkpoints."""
        verified_nodes: list[dict[str, Any]] = []
        expected_parent = expected_root_parent

        for ckpt_dir in checkpoints:
            manifest = cls.verify_checkpoint_integrity(ckpt_dir)
            actual_parent = manifest.get("parent_checkpoint_hash")
            if actual_parent != expected_parent:
                raise CheckpointLineageError(
                    f"Broken lineage at {ckpt_dir.name}: expected parent {expected_parent}, got {actual_parent}"
                )
            verified_nodes.append(manifest)
            expected_parent = manifest["checkpoint_hash"]

        return verified_nodes
