"""Phase 12 Step 9 isolated quarantine storage.

Every sample import gets its own directory under
`Settings.quarantine_dir` (default `data/quarantine/external-samples/`)
-- structurally separate from approved dataset storage, RAG indexes,
training data, model artifacts, and frontend static files (none of
those subsystems ever read from or reference this directory). Not the
same directory as the pre-existing, narrower `data/imports/quarantine/`
or `data/documents/quarantine/` "failed validation" buckets from the
existing import/document pipelines -- this is a distinct, richer
concept and must never write into those.

Layout per import:
    <quarantine_dir>/<sample_import_id>/original/   -- immutable, as downloaded
    <quarantine_dir>/<sample_import_id>/derived/     -- extraction/normalization output
    <quarantine_dir>/<sample_import_id>/reports/     -- rendered report snapshots
    <quarantine_dir>/<sample_import_id>/manifest.json

All directories are created `0o700` (owner rwx only); files are
`0o600`. Nothing here is ever registered on a static-file route --
`get_safe_text_preview` is the only read path meant to reach an API
response, and it is bounded and text-only.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend.core.config import Settings

_SAFE_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,255}$")
MAX_TEXT_PREVIEW_CHARS = 20_000


class QuarantineStorageError(RuntimeError):
    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason


def safe_filename(name: str) -> str:
    """Normalizes an arbitrary source filename into one that is safe to
    use as a single path component -- never a full path, never `..`,
    never a hidden dotfile, never empty."""

    candidate = Path(name).name.strip()
    candidate = re.sub(r"[^A-Za-z0-9._-]", "_", candidate) or "file"
    candidate = candidate.lstrip(".") or "file"
    return candidate[:200]


class ExternalDatasetQuarantineService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._root = settings.resolved_quarantine_dir

    def import_root(self, sample_import_public_id: str) -> Path:
        return self._root / sample_import_public_id

    def original_dir(self, sample_import_public_id: str) -> Path:
        return self.import_root(sample_import_public_id) / "original"

    def derived_dir(self, sample_import_public_id: str) -> Path:
        return self.import_root(sample_import_public_id) / "derived"

    def reports_dir(self, sample_import_public_id: str) -> Path:
        return self.import_root(sample_import_public_id) / "reports"

    def manifest_path(self, sample_import_public_id: str) -> Path:
        return self.import_root(sample_import_public_id) / "manifest.json"

    def ensure_layout(self, sample_import_public_id: str) -> Path:
        root = self.import_root(sample_import_public_id)
        for subdirectory in (
            self.original_dir(sample_import_public_id),
            self.derived_dir(sample_import_public_id),
            self.reports_dir(sample_import_public_id),
        ):
            subdirectory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not self.manifest_path(sample_import_public_id).exists():
            self.write_manifest(sample_import_public_id, {"files": []})
        return root

    def _safe_path(self, base: Path, relative_filename: str) -> Path:
        """Resolves `relative_filename` under `base` and refuses to
        return anything outside it -- the structural path-traversal
        guard every file read/write in this service goes through."""

        candidate = (base / safe_filename(relative_filename)).resolve()
        base_resolved = base.resolve()
        if candidate != base_resolved and base_resolved not in candidate.parents:
            raise QuarantineStorageError("path_traversal_rejected", relative_filename)
        return candidate

    def original_file_path(self, sample_import_public_id: str, filename: str) -> Path:
        return self._safe_path(self.original_dir(sample_import_public_id), filename)

    def derived_file_path(self, sample_import_public_id: str, filename: str) -> Path:
        return self._safe_path(self.derived_dir(sample_import_public_id), filename)

    def write_manifest(self, sample_import_public_id: str, manifest: dict[str, Any]) -> None:
        self.import_root(sample_import_public_id).mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self.manifest_path(sample_import_public_id)
        path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        path.chmod(0o600)

    def read_manifest(self, sample_import_public_id: str) -> dict[str, Any]:
        path = self.manifest_path(sample_import_public_id)
        if not path.exists():
            return {"files": []}
        return json.loads(path.read_text(encoding="utf-8"))

    def add_manifest_entry(self, sample_import_public_id: str, entry: dict[str, Any]) -> None:
        manifest = self.read_manifest(sample_import_public_id)
        manifest.setdefault("files", []).append(entry)
        self.write_manifest(sample_import_public_id, manifest)

    @staticmethod
    def _dir_bytes(directory: Path) -> int:
        if not directory.exists():
            return 0
        return sum(path.stat().st_size for path in directory.rglob("*") if path.is_file())

    def original_bytes_used(self, sample_import_public_id: str) -> int:
        """Downloaded-payload bytes only -- the figure the approved
        byte limit is actually a cap on, excluding manifest/derived/
        report bookkeeping overhead."""

        return self._dir_bytes(self.original_dir(sample_import_public_id))

    def bytes_used(self, sample_import_public_id: str) -> int:
        """Total on-disk footprint for this import (original + derived
        + reports + manifest) -- used for the Data Overview quarantine-
        storage aggregate, not for approval-quota enforcement."""

        return self._dir_bytes(self.import_root(sample_import_public_id))

    def remaining_quota_bytes(self, sample_import_public_id: str, approved_byte_limit: int) -> int:
        return max(0, approved_byte_limit - self.original_bytes_used(sample_import_public_id))

    def get_safe_text_preview(
        self, sample_import_public_id: str, filename: str, *, from_derived: bool = False
    ) -> str:
        """The only path meant to reach an API response for file
        content -- bounded, text-decoded-with-replacement, never a raw
        byte stream and never a public URL."""

        base = (
            self.derived_dir(sample_import_public_id)
            if from_derived
            else self.original_dir(sample_import_public_id)
        )
        path = self._safe_path(base, filename)
        if not path.exists() or not path.is_file():
            raise QuarantineStorageError("file_not_found", filename)
        with path.open("rb") as handle:
            raw = handle.read(MAX_TEXT_PREVIEW_CHARS * 4)
        return raw[:MAX_TEXT_PREVIEW_CHARS].decode("utf-8", errors="replace")

    def delete_payload(self, sample_import_public_id: str) -> None:
        """Removes only the payload directories (`original/`,
        `derived/`) -- `manifest.json` and `reports/` are left in
        place, since deletion must preserve lineage/checksums/reports
        (Step 26)."""

        import shutil

        for directory in (
            self.original_dir(sample_import_public_id),
            self.derived_dir(sample_import_public_id),
        ):
            if directory.exists():
                shutil.rmtree(directory)
