"""Phase 12 Step 11 archive safety: only `zip`, `tar`, `tar.gz` are
ever opened, and every member is inspected before extraction -- never
`extractall()`. Rejects path traversal, absolute paths, symlinks, hard
links, device files, encrypted entries, duplicate paths, excessive
directory depth, and nested archives beyond a configured depth (this
implementation never auto-recurses into a nested archive; it is
flagged for separate, explicit handling instead). Enforces a maximum
member count, a maximum total expanded size, and a compression-ratio
threshold to catch archive bombs, plus a wall-clock extraction
timeout. All extracted content stays inside the caller-supplied
quarantine `derived/` directory.
"""

from __future__ import annotations

import posixpath
import shutil
import stat
import tarfile
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from core_model.sample_import import (
    ARCHIVE_COMPRESSION_RATIO_THRESHOLD,
    ARCHIVE_EXTRACTION_TIMEOUT_SECONDS,
    MAX_ARCHIVE_DIRECTORY_DEPTH,
    MAX_ARCHIVE_EXPANDED_BYTES,
    MAX_ARCHIVE_MEMBER_COUNT,
)

_ARCHIVE_EXTENSIONS_FOR_NESTED_DETECTION = (".zip", ".tar", ".tar.gz", ".tgz")


class ArchiveSafetyError(RuntimeError):
    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason


@dataclass
class ExtractedMember:
    member_path: str
    size_bytes: int
    destination: Path


@dataclass
class RejectedMember:
    member_path: str
    reason: str


@dataclass
class ArchiveExtractionResult:
    extracted: list[ExtractedMember] = field(default_factory=list)
    rejected: list[RejectedMember] = field(default_factory=list)
    expanded_bytes: int = 0
    member_count: int = 0
    aborted: bool = False
    abort_reason: str | None = None


def _is_path_safe(normalized: str) -> bool:
    return normalized != ".." and not normalized.startswith("../") and normalized != "/"


class ExternalDatasetArchiveSafetyService:
    def extract(
        self,
        archive_path: Path,
        destination_dir: Path,
        *,
        archive_format: str,
        max_member_count: int = MAX_ARCHIVE_MEMBER_COUNT,
        max_expanded_bytes: int = MAX_ARCHIVE_EXPANDED_BYTES,
        compression_ratio_threshold: float = ARCHIVE_COMPRESSION_RATIO_THRESHOLD,
        max_directory_depth: int = MAX_ARCHIVE_DIRECTORY_DEPTH,
        timeout_seconds: float = ARCHIVE_EXTRACTION_TIMEOUT_SECONDS,
    ) -> ArchiveExtractionResult:
        if archive_format not in ("zip", "tar", "tar.gz"):
            raise ArchiveSafetyError("unsupported_archive_format", archive_format)
        destination_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        deadline = time.monotonic() + timeout_seconds
        result = ArchiveExtractionResult()
        try:
            if archive_format == "zip":
                self._extract_zip(
                    archive_path, destination_dir, result, deadline,
                    max_member_count=max_member_count, max_expanded_bytes=max_expanded_bytes,
                    compression_ratio_threshold=compression_ratio_threshold,
                    max_directory_depth=max_directory_depth,
                )
            else:
                self._extract_tar(
                    archive_path, destination_dir, result, deadline,
                    archive_format=archive_format,
                    max_member_count=max_member_count, max_expanded_bytes=max_expanded_bytes,
                    compression_ratio_threshold=compression_ratio_threshold,
                    max_directory_depth=max_directory_depth,
                )
        except Exception:
            shutil.rmtree(destination_dir, ignore_errors=True)
            raise
        if result.aborted:
            shutil.rmtree(destination_dir, ignore_errors=True)
        return result

    def _extract_zip(
        self,
        archive_path: Path,
        destination_dir: Path,
        result: ArchiveExtractionResult,
        deadline: float,
        *,
        max_member_count: int,
        max_expanded_bytes: int,
        compression_ratio_threshold: float,
        max_directory_depth: int,
    ) -> None:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            result.member_count = len(infos)
            if len(infos) > max_member_count:
                result.aborted = True
                result.abort_reason = "member_count_exceeded"
                return
            seen_paths: set[str] = set()
            for info in infos:
                if time.monotonic() > deadline:
                    result.aborted = True
                    result.abort_reason = "extraction_timeout"
                    return
                if info.is_dir():
                    continue
                name = info.filename.replace("\\", "/")
                mode = (info.external_attr >> 16) & 0xFFFF
                reason = self._reject_reason(
                    name, seen_paths, max_directory_depth,
                    is_symlink=stat.S_ISLNK(mode) if mode else False,
                    is_hardlink=False,
                    is_device=False,
                    is_encrypted=bool(info.flag_bits & 0x1),
                )
                if reason:
                    result.rejected.append(RejectedMember(name, reason))
                    continue
                if (
                    info.compress_size > 0
                    and (info.file_size / info.compress_size) > compression_ratio_threshold
                ):
                    result.aborted = True
                    result.abort_reason = "compression_ratio_exceeded"
                    return
                result.expanded_bytes += info.file_size
                if result.expanded_bytes > max_expanded_bytes:
                    result.aborted = True
                    result.abort_reason = "expanded_bytes_exceeded"
                    return
                normalized = posixpath.normpath(name)
                seen_paths.add(normalized)
                target = destination_dir / normalized
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as source, target.open("wb") as handle:
                    shutil.copyfileobj(source, handle, length=65_536)
                target.chmod(0o600)
                result.extracted.append(ExtractedMember(normalized, info.file_size, target))

    def _extract_tar(
        self,
        archive_path: Path,
        destination_dir: Path,
        result: ArchiveExtractionResult,
        deadline: float,
        *,
        archive_format: str,
        max_member_count: int,
        max_expanded_bytes: int,
        compression_ratio_threshold: float,
        max_directory_depth: int,
    ) -> None:
        mode = "r:gz" if archive_format == "tar.gz" else "r:"
        with tarfile.open(archive_path, mode) as archive:
            members = archive.getmembers()
            result.member_count = len(members)
            if len(members) > max_member_count:
                result.aborted = True
                result.abort_reason = "member_count_exceeded"
                return
            compressed_size = archive_path.stat().st_size or 1
            seen_paths: set[str] = set()
            for member in members:
                if time.monotonic() > deadline:
                    result.aborted = True
                    result.abort_reason = "extraction_timeout"
                    return
                if member.isdir():
                    continue
                name = member.name.replace("\\", "/")
                reason = self._reject_reason(
                    name, seen_paths, max_directory_depth,
                    is_symlink=member.issym(),
                    is_hardlink=member.islnk(),
                    is_device=member.isdev(),
                    is_encrypted=False,
                )
                if reason:
                    result.rejected.append(RejectedMember(name, reason))
                    continue
                if not member.isfile():
                    result.rejected.append(RejectedMember(name, "path_traversal"))
                    continue
                result.expanded_bytes += member.size
                if result.expanded_bytes > max_expanded_bytes:
                    result.aborted = True
                    result.abort_reason = "expanded_bytes_exceeded"
                    return
                if (result.expanded_bytes / compressed_size) > compression_ratio_threshold:
                    result.aborted = True
                    result.abort_reason = "compression_ratio_exceeded"
                    return
                normalized = posixpath.normpath(name)
                seen_paths.add(normalized)
                target = destination_dir / normalized
                target.parent.mkdir(parents=True, exist_ok=True)
                source = archive.extractfile(member)
                if source is None:
                    result.rejected.append(RejectedMember(name, "path_traversal"))
                    continue
                with source, target.open("wb") as handle:
                    shutil.copyfileobj(source, handle, length=65_536)
                target.chmod(0o600)
                result.extracted.append(ExtractedMember(normalized, member.size, target))

    @staticmethod
    def _reject_reason(
        name: str,
        seen_paths: set[str],
        max_directory_depth: int,
        *,
        is_symlink: bool,
        is_hardlink: bool,
        is_device: bool,
        is_encrypted: bool,
    ) -> str | None:
        if not name or name.startswith("/") or (len(name) > 1 and name[1] == ":"):
            return "absolute_path"
        normalized = posixpath.normpath(name)
        if not _is_path_safe(normalized) or normalized.startswith(".."):
            return "path_traversal"
        if is_symlink:
            return "symlink"
        if is_hardlink:
            return "hard_link"
        if is_device:
            return "device_file"
        if is_encrypted:
            return "encrypted_entry"
        if normalized in seen_paths:
            return "duplicate_path"
        if normalized.count("/") > max_directory_depth:
            return "depth_exceeded"
        lowered = normalized.lower()
        if any(lowered.endswith(ext) for ext in _ARCHIVE_EXTENSIONS_FOR_NESTED_DETECTION):
            return "nested_archive_depth_exceeded"
        return None


def detect_archive_format(filename: str) -> str | None:
    lowered = filename.lower()
    if lowered.endswith(".tar.gz") or lowered.endswith(".tgz"):
        return "tar.gz"
    if lowered.endswith(".tar"):
        return "tar"
    if lowered.endswith(".zip"):
        return "zip"
    return None
