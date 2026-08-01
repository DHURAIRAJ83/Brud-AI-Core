"""Phase 12 Step 12 deterministic safety scanner.

No antivirus engine exists in this codebase, so this module never
claims full malware detection -- every verdict is deliberately named
`clean_by_policy` (passed *our* deterministic checks, not "verified
safe by a real scanner") rather than a bare "clean". Checks:
executable/script/macro signatures (delegated to
`ExternalDatasetFileValidationService`'s classification, carried
forward here rather than re-implemented), embedded executable PDF
objects, suspicious archive contents (delegated to the archive-safety
service's own rejection list), malicious filename patterns, polyglot
mismatches, binary content inside a declared text file, HTML
`<script>` tags, CSV formula injection, Jupyter notebook code cells,
and pickle/joblib serialized-object signatures.

Deliberately never flags shell-command *text* appearing inside a
record's own content as unsafe -- a training example that merely
*describes* or *quotes* a shell command is inert data, not an
executable script file; only an actual script *file* (caught upstream
by file validation via extension/shebang) is ever blocked.
"""

from __future__ import annotations

import re
from typing import Any

from core_model.sample_import import BLOCKED_FILE_CLASSES

_HTML_SCRIPT_PATTERN = re.compile(rb"<\s*script[\s>]", re.IGNORECASE)
_CSV_FORMULA_PREFIXES = (b"=", b"+", b"-", b"@")
_PICKLE_SIGNATURES = (b"\x80\x02", b"\x80\x03", b"\x80\x04", b"\x80\x05")
_PDF_DANGEROUS_MARKERS = (b"/JavaScript", b"/JS", b"/Launch", b"/EmbeddedFile", b"/OpenAction")
_RTLO_CHARACTER = "‮"

_ARCHIVE_DANGEROUS_REJECTION_REASONS = frozenset(
    {"symlink", "hard_link", "device_file", "path_traversal", "absolute_path", "encrypted_entry"}
)


class ExternalDatasetSecurityScanService:
    def scan_file(
        self,
        content: bytes,
        *,
        original_filename: str,
        file_validation_result: dict[str, Any],
        archive_rejected_reasons: list[str] | None = None,
    ) -> dict[str, Any]:
        matched: list[str] = []

        if file_validation_result.get("status") == "blocked":
            blocked_class = file_validation_result.get("blocked_class")
            if blocked_class in BLOCKED_FILE_CLASSES:
                return self._result(
                    "blocked", [blocked_class],
                    f"file-level validation already classified this as '{blocked_class}'",
                )

        if self._has_filename_trick(original_filename):
            matched.append("malicious_filename_pattern")

        extension = file_validation_result.get("extension", "")
        if self._is_polyglot_mismatch(extension, content):
            matched.append("polyglot_mismatch")

        is_declared_text = extension in (".txt", ".md", ".markdown", ".csv", ".json", ".jsonl")
        if is_declared_text and self._looks_binary(content[:4096]):
            matched.append("binary_content_in_text_file")

        if _HTML_SCRIPT_PATTERN.search(content):
            matched.append("html_script_tag")

        if extension == ".csv" and self._has_csv_formula_injection(content):
            matched.append("csv_formula_injection")

        if extension in (".json", ".jsonl") and self._looks_like_notebook(content):
            matched.append("notebook_code_cell")

        if any(content.startswith(signature) for signature in _PICKLE_SIGNATURES):
            matched.append("pickle_or_joblib_signature")

        if extension == ".pdf" and any(marker in content for marker in _PDF_DANGEROUS_MARKERS):
            matched.append("pdf_embedded_executable_object")

        for reason in archive_rejected_reasons or []:
            if reason in _ARCHIVE_DANGEROUS_REJECTION_REASONS:
                matched.append("suspicious_archive_contents")
                break

        verdict = self._verdict_for(matched)
        reason = "; ".join(matched) if matched else "no deterministic risk signals matched"
        return self._result(verdict, matched, reason)

    @staticmethod
    def _result(verdict: str, matched: list[str], reason: str) -> dict[str, Any]:
        return {"verdict": verdict, "matched_signals": matched, "reason": reason}

    @staticmethod
    def _verdict_for(matched: list[str]) -> str:
        blocking = {"pickle_or_joblib_signature", "pdf_embedded_executable_object"}
        if any(signal in blocking for signal in matched):
            return "blocked"
        if matched:
            return "suspicious"
        return "clean_by_policy"

    @staticmethod
    def _has_filename_trick(filename: str) -> bool:
        if _RTLO_CHARACTER in filename:
            return True
        # A "double extension" trick (e.g. "invoice.pdf.exe") is
        # already caught by file validation's own extension check on
        # the *final* extension -- this only flags the case where an
        # earlier, blocked-class-looking extension is hidden mid-name.
        lowered = filename.lower()
        suspicious_middle_extensions = (".exe.", ".scr.", ".js.", ".vbs.")
        return any(marker in lowered for marker in suspicious_middle_extensions)

    @staticmethod
    def _looks_binary(sample: bytes) -> bool:
        if b"\x00" in sample:
            return True
        if not sample:
            return False
        non_printable = sum(1 for byte in sample if byte < 9 or (13 < byte < 32))
        return (non_printable / len(sample)) > 0.30

    @staticmethod
    def _is_polyglot_mismatch(extension: str, content: bytes) -> bool:
        head = content[:8]
        text_extensions = (".csv", ".txt", ".md", ".markdown", ".json", ".jsonl")
        binary_prefixes = (b"PK\x03\x04", b"%PDF-", b"MZ")
        if extension in text_extensions and head.startswith(binary_prefixes):
            return True
        if extension == ".pdf" and not head.startswith(b"%PDF-"):
            return True
        return False

    @staticmethod
    def _has_csv_formula_injection(content: bytes) -> bool:
        for line in content.split(b"\n")[:500]:
            for field in line.split(b","):
                stripped = field.strip(b' "\t')
                if stripped[:1] in _CSV_FORMULA_PREFIXES and len(stripped) > 1:
                    return True
        return False

    @staticmethod
    def _looks_like_notebook(content: bytes) -> bool:
        sample = content[:8192]
        return b'"cell_type"' in sample and b'"code"' in sample
