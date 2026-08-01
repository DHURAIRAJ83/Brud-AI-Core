"""Phase 12 Step 10 file validation: never trusts a file extension
alone. Every file is classified by declared extension, detected MIME
type, and magic-byte signature (hand-rolled prefix comparisons, the
same house style as `document_service.py` -- no `python-magic`/
`filetype` dependency anywhere in this codebase). No file is ever
executed to determine its type.

Deliberately does not attempt full malware detection here -- that is
`ExternalDatasetSecurityScanService`'s honestly-scoped job (Step 12).
This module answers a narrower, structural question: "is this file's
declared/detected shape one of the classes we refuse to even scan
further?"
"""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path
from typing import Any

# Extension-based blocks take priority -- most of these classes (batch
# scripts, PowerShell, Java/Android archives, disk images, model-weight
# files) have no reliable magic-byte signature worth hand-rolling, so
# the extension is the only honest signal available; still layered
# with the magic-byte checks below for the classes that DO have one.
_EXTENSION_BLOCKED_CLASSES: dict[str, str] = {
    ".exe": "executable",
    ".dll": "shared_library",
    ".so": "shared_library",
    ".dylib": "shared_library",
    ".sh": "shell_script",
    ".bash": "shell_script",
    ".bat": "batch_script",
    ".cmd": "batch_script",
    ".ps1": "powershell_script",
    ".jar": "java_archive",
    ".apk": "android_package",
    ".iso": "disk_image",
    ".dmg": "disk_image",
    ".img": "disk_image",
    ".bin": "model_weight_file",
    ".pt": "model_weight_file",
    ".pth": "model_weight_file",
    ".safetensors": "model_weight_file",
    ".ckpt": "model_weight_file",
    ".h5": "model_weight_file",
    ".onnx": "model_weight_file",
    ".gguf": "model_weight_file",
}

# (signature prefix, detected MIME, blocked_class or None when the
# signature alone isn't enough to condemn it -- e.g. a plain ZIP is
# only blocked once its *extension* also says `.jar`/`.apk`).
_MAGIC_SIGNATURES: tuple[tuple[bytes, str, str | None], ...] = (
    (b"MZ", "application/x-msdownload", "executable"),
    (b"\x7fELF", "application/x-elf", "executable"),
    (b"\xca\xfe\xba\xbe", "application/x-mach-binary", "executable"),
    (b"\xfe\xed\xfa\xce", "application/x-mach-binary", "executable"),
    (b"\xfe\xed\xfa\xcf", "application/x-mach-binary", "executable"),
    (b"\xcf\xfa\xed\xfe", "application/x-mach-binary", "executable"),
    (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", "application/x-ole-storage", "macro_document"),
    (b"PK\x03\x04", "application/zip", None),
    (b"%PDF-", "application/pdf", None),
    (b"\x1f\x8b", "application/gzip", None),
)

_ARCHIVE_EXTENSIONS = {".zip": "zip", ".tar": "tar", ".tar.gz": "tar.gz", ".tgz": "tar.gz"}
_SUPPORTED_TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".json", ".jsonl"}


def _extension_of(filename: str) -> str:
    lowered = filename.lower()
    for double in (".tar.gz",):
        if lowered.endswith(double):
            return double
    return Path(lowered).suffix


def _looks_binary(sample: bytes) -> bool:
    if b"\x00" in sample:
        return True
    if not sample:
        return False
    non_printable = sum(1 for byte in sample if byte < 9 or (13 < byte < 32))
    return (non_printable / len(sample)) > 0.30


class ExternalDatasetFileValidationService:
    def validate_file(
        self,
        path: Path,
        *,
        original_filename: str,
        max_bytes: int | None = None,
        expected_checksum: str | None = None,
    ) -> dict[str, Any]:
        extension = _extension_of(original_filename)
        size_bytes = path.stat().st_size

        mode = path.stat().st_mode
        if stat.S_ISCHR(mode) or stat.S_ISBLK(mode) or stat.S_ISFIFO(mode) or stat.S_ISSOCK(mode):
            return self._result(
                status="blocked", blocked_class="device_file", extension=extension,
                size_bytes=size_bytes, reason="filesystem device/special file rejected",
            )

        with path.open("rb") as handle:
            head = handle.read(4096)
        checksum = _sha256_file(path)

        if max_bytes is not None and size_bytes > max_bytes:
            return self._result(
                status="oversized", extension=extension, size_bytes=size_bytes,
                checksum=checksum, reason=f"file exceeds the {max_bytes}-byte limit",
            )
        if expected_checksum is not None and checksum != expected_checksum:
            return self._result(
                status="corrupt", extension=extension, size_bytes=size_bytes,
                checksum=checksum,
                reason="checksum does not match the checksum recorded at download",
            )

        blocked_class = _EXTENSION_BLOCKED_CLASSES.get(extension)
        detected_mime = None
        detected_signature = None
        if blocked_class is None:
            for prefix, mime, sig_blocked_class in _MAGIC_SIGNATURES:
                if head.startswith(prefix):
                    detected_mime = mime
                    detected_signature = prefix.hex()
                    if sig_blocked_class:
                        blocked_class = sig_blocked_class
                    break
        if blocked_class is None and head.startswith(b"#!"):
            blocked_class = "shell_script"
            detected_signature = "shebang"

        if blocked_class:
            return self._result(
                status="blocked", blocked_class=blocked_class, extension=extension,
                size_bytes=size_bytes, checksum=checksum, detected_mime=detected_mime,
                detected_signature=detected_signature,
                reason=f"file classified as blocked class '{blocked_class}'",
            )

        if extension in _ARCHIVE_EXTENSIONS:
            return self._result(
                status="safe_for_scan", extension=extension, size_bytes=size_bytes,
                checksum=checksum, detected_mime=detected_mime or "application/octet-stream",
                is_archive=True, archive_format=_ARCHIVE_EXTENSIONS[extension],
            )

        if extension == ".pdf" or head.startswith(b"%PDF-"):
            return self._result(
                status="safe_for_scan", extension=extension, size_bytes=size_bytes,
                checksum=checksum, detected_mime="application/pdf",
            )

        if extension in _SUPPORTED_TEXT_EXTENSIONS and not _looks_binary(head):
            encoding, warnings = _detect_encoding(head)
            return self._result(
                status="safe_for_scan", extension=extension, size_bytes=size_bytes,
                checksum=checksum, detected_mime="text/plain", encoding=encoding,
                warnings=warnings,
            )

        if _looks_binary(head):
            return self._result(
                status="blocked", blocked_class="unknown_binary_blob", extension=extension,
                size_bytes=size_bytes, checksum=checksum,
                reason="unrecognized binary content -- not on the supported-format allowlist",
            )

        return self._result(
            status="unsupported", extension=extension, size_bytes=size_bytes, checksum=checksum,
            reason=f"'{extension or '(no extension)'}' is not a supported Phase 12 format",
        )

    @staticmethod
    def _result(
        *,
        status: str,
        extension: str,
        size_bytes: int,
        checksum: str | None = None,
        detected_mime: str | None = None,
        detected_signature: str | None = None,
        blocked_class: str | None = None,
        is_archive: bool = False,
        archive_format: str | None = None,
        encoding: str | None = None,
        reason: str = "",
        warnings: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "status": status,
            "extension": extension,
            "size_bytes": size_bytes,
            "checksum": checksum,
            "detected_mime": detected_mime,
            "detected_signature": detected_signature,
            "blocked_class": blocked_class,
            "is_archive": is_archive,
            "archive_format": archive_format,
            "encoding": encoding,
            "rejection_reason": reason,
            "warnings": warnings or [],
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65_536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _detect_encoding(sample: bytes) -> tuple[str, list[str]]:
    try:
        sample.decode("utf-8")
        return "utf-8", []
    except UnicodeDecodeError:
        return "utf-8-with-replacement", ["encoding_not_valid_utf8"]
