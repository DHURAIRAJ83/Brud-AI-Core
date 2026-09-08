"""Phase 49 Checkpoint Lifecycle Manager and Cold Storage Archiving.

Implements HOT/WARM/COLD/GOLD checkpoint tiering, dependency-aware retention,
cryptographically verified cold storage archiving, and disk budget governance.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class CheckpointTier(str, Enum):
    HOT = "HOT"      # Available for immediate resumption (latest 2)
    WARM = "WARM"    # Retained on disk for active lineage
    COLD = "COLD"    # Archived in tar.gz cold storage
    GOLD = "GOLD"    # Best validation checkpoint (never pruned)


class DiskState(str, Enum):
    NORMAL = "NORMAL"
    ARCHIVE_REQUIRED = "ARCHIVE_REQUIRED"
    RESOURCE_WAIT = "RESOURCE_WAIT"
    SAFE_STOP = "SAFE_STOP"


class CheckpointLifecycleError(Exception):
    """Raised when an archive verification fails or safe pruning is violated."""
    pass


@dataclass
class ArchiveManifest:
    checkpoint_id: str
    job_id: str
    archive_file: str
    archive_sha256: str
    file_count: int
    component_hashes: dict[str, str]
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArchiveManifest:
        return cls(**data)


class Phase49CheckpointManager:
    """Manages multi-tier checkpoint lifecycle, cold archiving, and dependency-aware retention."""

    def __init__(
        self,
        checkpoint_root: Path | str,
        archive_root: Path | str,
        min_free_disk_mb: float = 1000.0,
        archive_trigger_mb: float = 3000.0,
        critical_disk_mb: float = 500.0,
        hot_retention_count: int = 2,
    ) -> None:
        self.checkpoint_root = Path(checkpoint_root)
        self.checkpoint_root.mkdir(parents=True, exist_ok=True)
        self.archive_root = Path(archive_root)
        self.archive_root.mkdir(parents=True, exist_ok=True)

        self.min_free_disk_mb = min_free_disk_mb
        self.archive_trigger_mb = archive_trigger_mb
        self.critical_disk_mb = critical_disk_mb
        self.hot_retention_count = max(1, hot_retention_count)

    def get_free_disk_mb(self) -> float:
        stat = os.statvfs(str(self.checkpoint_root))
        return (stat.f_bavail * stat.f_frsize) / (1024.0 * 1024.0)

    def assess_disk_budget(self) -> DiskState:
        free_mb = self.get_free_disk_mb()
        if free_mb < self.critical_disk_mb:
            return DiskState.SAFE_STOP
        if free_mb < self.min_free_disk_mb:
            return DiskState.RESOURCE_WAIT
        if free_mb < self.archive_trigger_mb:
            return DiskState.ARCHIVE_REQUIRED
        return DiskState.NORMAL

    @staticmethod
    def sha256_file(filepath: Path) -> str:
        h = hashlib.sha256()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def archive_checkpoint(self, job_id: str, checkpoint_id: str) -> ArchiveManifest:
        """Archives a checkpoint folder to a verified deterministic tar.gz file."""
        ckpt_dir = self.checkpoint_root / job_id / checkpoint_id
        if not ckpt_dir.exists():
            raise CheckpointLifecycleError(f"Checkpoint directory {ckpt_dir} does not exist")

        archive_job_dir = self.archive_root / job_id
        archive_job_dir.mkdir(parents=True, exist_ok=True)
        archive_tar = archive_job_dir / f"{checkpoint_id}.tar.gz"

        component_hashes = {}
        files_to_archive = sorted([f for f in ckpt_dir.iterdir() if f.is_file()])
        for f in files_to_archive:
            component_hashes[f.name] = self.sha256_file(f)

        # Create tar.gz archive
        with tarfile.open(archive_tar, "w:gz") as tar:
            for f in files_to_archive:
                tar.add(f, arcname=f.name)

        archive_sha = self.sha256_file(archive_tar)
        manifest = ArchiveManifest(
            checkpoint_id=checkpoint_id,
            job_id=job_id,
            archive_file=str(archive_tar),
            archive_sha256=archive_sha,
            file_count=len(files_to_archive),
            component_hashes=component_hashes,
        )

        manifest_file = archive_job_dir / f"{checkpoint_id}_archive_manifest.json"
        manifest_file.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
        return manifest

    def verify_archive(self, job_id: str, checkpoint_id: str) -> bool:
        """Verifies the integrity of a COLD archive without extracting all files to disk."""
        archive_job_dir = self.archive_root / job_id
        archive_tar = archive_job_dir / f"{checkpoint_id}.tar.gz"
        manifest_file = archive_job_dir / f"{checkpoint_id}_archive_manifest.json"

        if not archive_tar.exists() or not manifest_file.exists():
            return False

        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            manifest = ArchiveManifest.from_dict(manifest_data)
            current_sha = self.sha256_file(archive_tar)
            if current_sha != manifest.archive_sha256:
                return False

            # Verify tar header integrity
            with tarfile.open(archive_tar, "r:gz") as tar:
                members = tar.getmembers()
                if len(members) != manifest.file_count:
                    return False
            return True
        except Exception:
            return False

    def manage_lifecycle(
        self,
        job_id: str,
        current_checkpoint_id: str,
        active_lineage: list[str],
        gold_checkpoint_id: str | None = None,
        reproduction_required: list[str] | None = None,
    ) -> dict[str, Any]:
        """Dependency-aware checkpoint lifecycle management obeying Mandatory Correction 4."""
        job_ckpt_dir = self.checkpoint_root / job_id
        if not job_ckpt_dir.exists():
            return {"status": "NO_CHECKPOINTS"}

        reproduction_set = set(reproduction_required or [])
        protected_set = set(active_lineage) | {current_checkpoint_id} | reproduction_set
        if gold_checkpoint_id:
            protected_set.add(gold_checkpoint_id)

        all_ckpts = sorted(
            [d.name for d in job_ckpt_dir.iterdir() if d.is_dir() and d.name.startswith("checkpoint_")],
            reverse=True,
        )

        archived = []
        pruned = []

        for ckpt_id in all_ckpts:
            # Checkpoint tier decision
            if ckpt_id == gold_checkpoint_id:
                tier = CheckpointTier.GOLD
            elif ckpt_id in active_lineage[-self.hot_retention_count:]:
                tier = CheckpointTier.HOT
            elif ckpt_id in protected_set:
                tier = CheckpointTier.WARM
            else:
                tier = CheckpointTier.COLD

            if tier == CheckpointTier.COLD:
                # Mandatory Correction 4: Archive and verify before local directory deletion
                self.archive_checkpoint(job_id, ckpt_id)
                if self.verify_archive(job_id, ckpt_id):
                    shutil.rmtree(job_ckpt_dir / ckpt_id)
                    pruned.append(ckpt_id)
                    archived.append(ckpt_id)
                else:
                    raise CheckpointLifecycleError(
                        f"Archive verification failed for {ckpt_id}; fail-closed without pruning original"
                    )

        return {
            "status": "SUCCESS",
            "job_id": job_id,
            "protected_checkpoints": list(protected_set),
            "archived": archived,
            "pruned": pruned,
            "free_disk_mb": round(self.get_free_disk_mb(), 2),
            "disk_state": self.assess_disk_budget().value,
        }
