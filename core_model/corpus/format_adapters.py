"""Phase 20 multi-format source adapters.

Every supported source format has its own dedicated, pure-function
adapter rather than one large conditional -- ``inspect()`` sniffs
structure/validity without any side effect, ``extract()`` produces
plain text plus confidence/issues, exactly mirroring Phase 19's
``text_extraction.py`` shape. PDF and DOCX extraction need optional
third-party libraries (``fitz``, ``python-docx``) and therefore live
as adapter classes in ``backend/services/corpus_ingestion_service.py``
instead, following the same optional-import convention Phase 5/19
already established -- this module stays dependency-free.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from core_model.corpus.text_extraction import (
    content_checksum,
    extract_html_snapshot_text,
    extract_markdown_text,
    extract_plain_text,
)

SUPPORTED_FORMATS = ("pdf", "epub", "txt", "json", "jsonl", "csv", "docx", "html", "markdown")

_MAGIC_SIGNATURES: dict[bytes, str] = {
    b"%PDF-": "pdf",
    b"PK\x03\x04": "epub",  # EPUB/DOCX zip container
}

# Leading characters that a spreadsheet application would interpret as
# the start of a formula -- neutralized on every ingested CSV cell so a
# malicious cell can never execute when the corpus is later opened in
# a spreadsheet tool.
_CSV_FORMULA_TRIGGER_CHARACTERS = ("=", "+", "-", "@", "\t", "\r")


@dataclass
class SourceInspection:
    format: str
    declared_extension: str
    detected_by_magic_bytes: str | None
    size_bytes: int
    record_count: int | None = None
    encoding: str = "utf-8"
    is_encrypted: bool = False
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExtractionOptions:
    encoding: str = "utf-8"
    text_field: str | None = None
    text_columns: tuple[str, ...] | None = None


@dataclass
class ExtractionResult:
    text: str
    confidence: float
    issues: list[str] = field(default_factory=list)


class CorpusSourceAdapter(Protocol):
    """Every format-specific adapter implements exactly this shape --
    never a branch inside one large conditional extraction function."""

    def inspect(self, raw_bytes: bytes, *, declared_extension: str) -> SourceInspection: ...

    def extract(self, raw_bytes: bytes, options: ExtractionOptions) -> ExtractionResult: ...


def detect_magic_bytes(raw_bytes: bytes) -> str | None:
    for signature, format_name in _MAGIC_SIGNATURES.items():
        if raw_bytes.startswith(signature):
            return format_name
    return None


def validate_extension(
    declared_extension: str, *, allowed: tuple[str, ...] = SUPPORTED_FORMATS
) -> bool:
    return declared_extension.lower().lstrip(".") in allowed


def validate_mime_type(mime_type: str, *, format_name: str) -> bool:
    expected = {
        "pdf": {"application/pdf"},
        "txt": {"text/plain"},
        "json": {"application/json", "text/json"},
        "jsonl": {"application/x-ndjson", "application/json", "text/plain"},
        "csv": {"text/csv", "application/csv", "text/plain"},
        "docx": {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
        },
        "html": {"text/html"},
        "markdown": {"text/markdown", "text/plain"},
    }
    return mime_type.lower() in expected.get(format_name, set())


def sanitize_csv_cell(value: str) -> str:
    """Neutralizes CSV formula injection -- a cell beginning with a
    formula-trigger character is prefixed with a single quote so a
    spreadsheet application renders it as literal text, never as a
    formula to execute."""

    if value and value[0] in _CSV_FORMULA_TRIGGER_CHARACTERS:
        return f"'{value}"
    return value


class TxtAdapter:
    """Thin wrapper over Phase 19's ``text_extraction.extract_plain_text``
    -- never a second plain-text decoder."""

    def inspect(self, raw_bytes: bytes, *, declared_extension: str) -> SourceInspection:
        warnings = []
        try:
            raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            warnings.append("not_valid_utf8_will_use_replacement_characters")
        return SourceInspection(
            format="txt",
            declared_extension=declared_extension,
            detected_by_magic_bytes=None,
            size_bytes=len(raw_bytes),
            warnings=warnings,
        )

    def extract(self, raw_bytes: bytes, options: ExtractionOptions) -> ExtractionResult:
        result = extract_plain_text(raw_bytes, encoding=options.encoding)
        return ExtractionResult(
            text=result["text"], confidence=result["confidence"], issues=result["issues"]
        )


class MarkdownAdapter:
    def inspect(self, raw_bytes: bytes, *, declared_extension: str) -> SourceInspection:
        return SourceInspection(
            format="markdown",
            declared_extension=declared_extension,
            detected_by_magic_bytes=None,
            size_bytes=len(raw_bytes),
        )

    def extract(self, raw_bytes: bytes, options: ExtractionOptions) -> ExtractionResult:
        result = extract_markdown_text(raw_bytes, encoding=options.encoding)
        return ExtractionResult(
            text=result["text"], confidence=result["confidence"], issues=result["issues"]
        )


class HtmlAdapter:
    def inspect(self, raw_bytes: bytes, *, declared_extension: str) -> SourceInspection:
        return SourceInspection(
            format="html",
            declared_extension=declared_extension,
            detected_by_magic_bytes=None,
            size_bytes=len(raw_bytes),
        )

    def extract(self, raw_bytes: bytes, options: ExtractionOptions) -> ExtractionResult:
        result = extract_html_snapshot_text(raw_bytes, encoding=options.encoding)
        return ExtractionResult(
            text=result["text"], confidence=result["confidence"], issues=result["issues"]
        )


def _find_text_recursively(value: Any, *, max_depth: int = 6, _depth: int = 0) -> list[str]:
    """Bounded fallback used only when no explicit ``text_field`` is
    configured -- collects every string leaf value, depth-limited so a
    deeply nested or adversarial JSON document cannot cause unbounded
    recursion."""

    if _depth > max_depth:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        found = []
        for item in value:
            found.extend(_find_text_recursively(item, max_depth=max_depth, _depth=_depth + 1))
        return found
    if isinstance(value, dict):
        found = []
        for item in value.values():
            found.extend(_find_text_recursively(item, max_depth=max_depth, _depth=_depth + 1))
        return found
    return []


class JsonAdapter:
    def inspect(self, raw_bytes: bytes, *, declared_extension: str) -> SourceInspection:
        warnings = []
        record_count = None
        try:
            parsed = json.loads(raw_bytes.decode("utf-8"))
            record_count = len(parsed) if isinstance(parsed, list) else 1
        except (UnicodeDecodeError, json.JSONDecodeError):
            warnings.append("invalid_json")
        return SourceInspection(
            format="json",
            declared_extension=declared_extension,
            detected_by_magic_bytes=None,
            size_bytes=len(raw_bytes),
            record_count=record_count,
            warnings=warnings,
        )

    def extract(self, raw_bytes: bytes, options: ExtractionOptions) -> ExtractionResult:
        try:
            parsed = json.loads(raw_bytes.decode(options.encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return ExtractionResult(text="", confidence=0.0, issues=["invalid_json"])

        records = parsed if isinstance(parsed, list) else [parsed]
        issues: list[str] = []
        parts: list[str] = []
        for record in records:
            if options.text_field and isinstance(record, dict) and options.text_field in record:
                value = record[options.text_field]
                if isinstance(value, str):
                    parts.append(value)
            else:
                if options.text_field:
                    issues.append("configured_text_field_missing_used_fallback")
                parts.extend(_find_text_recursively(record))
        text = "\n\n".join(part for part in parts if part.strip())
        return ExtractionResult(
            text=text,
            confidence=1.0 if parts else 0.0,
            issues=issues or ([] if text else ["empty_projection"]),
        )


class JsonlAdapter:
    def inspect(self, raw_bytes: bytes, *, declared_extension: str) -> SourceInspection:
        warnings = []
        record_count = 0
        try:
            text = raw_bytes.decode("utf-8")
            for line in text.splitlines():
                if not line.strip():
                    continue
                json.loads(line)
                record_count += 1
        except (UnicodeDecodeError, json.JSONDecodeError):
            warnings.append("invalid_jsonl_line")
        return SourceInspection(
            format="jsonl",
            declared_extension=declared_extension,
            detected_by_magic_bytes=None,
            size_bytes=len(raw_bytes),
            record_count=record_count,
            warnings=warnings,
        )

    def extract(self, raw_bytes: bytes, options: ExtractionOptions) -> ExtractionResult:
        issues: list[str] = []
        parts: list[str] = []
        try:
            text = raw_bytes.decode(options.encoding)
        except UnicodeDecodeError:
            return ExtractionResult(text="", confidence=0.0, issues=["invalid_encoding"])

        for line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                issues.append(f"invalid_json_line_{line_number}")
                continue
            if options.text_field and isinstance(record, dict) and options.text_field in record:
                value = record[options.text_field]
                if isinstance(value, str):
                    parts.append(value)
            else:
                parts.extend(_find_text_recursively(record))
        text_out = "\n\n".join(part for part in parts if part.strip())
        return ExtractionResult(
            text=text_out,
            confidence=1.0 if parts else 0.0,
            issues=issues or ([] if text_out else ["empty_projection"]),
        )


class CsvAdapter:
    def inspect(self, raw_bytes: bytes, *, declared_extension: str) -> SourceInspection:
        warnings = []
        record_count = None
        try:
            text = raw_bytes.decode("utf-8")
            record_count = sum(1 for _ in csv.reader(io.StringIO(text))) - 1
            if record_count < 0:
                record_count = 0
        except UnicodeDecodeError:
            warnings.append("invalid_encoding")
        return SourceInspection(
            format="csv",
            declared_extension=declared_extension,
            detected_by_magic_bytes=None,
            size_bytes=len(raw_bytes),
            record_count=record_count,
            warnings=warnings,
        )

    def extract(self, raw_bytes: bytes, options: ExtractionOptions) -> ExtractionResult:
        try:
            text = raw_bytes.decode(options.encoding)
        except UnicodeDecodeError:
            return ExtractionResult(text="", confidence=0.0, issues=["invalid_encoding"])

        reader = csv.DictReader(io.StringIO(text))
        parts: list[str] = []
        columns = options.text_columns
        for row in reader:
            selected = {key: row[key] for key in columns if key in row} if columns else dict(row)
            sanitized = {key: sanitize_csv_cell(value or "") for key, value in selected.items()}
            line = "\n".join(f"{key}: {value}" for key, value in sanitized.items() if value)
            if line.strip():
                parts.append(line)
        text_out = "\n\n".join(parts)
        return ExtractionResult(
            text=text_out,
            confidence=1.0 if parts else 0.0,
            issues=[] if text_out else ["empty_projection"],
        )


class EpubAdapter:
    """Pure zipfile HTML extraction adapter for .epub book archives."""

    def inspect(self, raw_bytes: bytes) -> SourceInspection:
        valid = raw_bytes.startswith(b"PK\x03\x04")
        return SourceInspection(
            format="epub",
            declared_extension="epub",
            detected_by_magic_bytes="epub" if valid else None,
            size_bytes=len(raw_bytes),
            warnings=[] if valid else ["not_zip_archive"],
        )

    def extract(self, raw_bytes: bytes, options: ExtractionOptions) -> ExtractionResult:
        import zipfile
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as z:
                html_files = [f for f in z.namelist() if f.endswith((".html", ".xhtml", ".htm"))]
                parts = []
                for hf in sorted(html_files):
                    with z.open(hf) as handle:
                        text_part = extract_html_snapshot_text(handle.read()).get("text", "")
                        if text_part.strip():
                            parts.append(text_part.strip())
                extracted_text = "\n\n".join(parts)
                return ExtractionResult(
                    text=extracted_text,
                    confidence=1.0 if parts else 0.0,
                    issues=[] if parts else ["no_html_content_in_epub"]
                )
        except Exception as exc:
            return ExtractionResult(text="", confidence=0.0, issues=[f"epub_zip_error: {exc}"])


ADAPTERS: dict[str, CorpusSourceAdapter] = {
    "txt": TxtAdapter(),
    "markdown": MarkdownAdapter(),
    "html": HtmlAdapter(),
    "json": JsonAdapter(),
    "jsonl": JsonlAdapter(),
    "csv": CsvAdapter(),
    "epub": EpubAdapter(),
}


def adapter_for_format(format_name: str) -> CorpusSourceAdapter:
    if format_name not in ADAPTERS:
        raise ValueError(f"no pure adapter registered for format: {format_name}")
    return ADAPTERS[format_name]


__all__ = [
    "SUPPORTED_FORMATS",
    "SourceInspection",
    "ExtractionOptions",
    "ExtractionResult",
    "CorpusSourceAdapter",
    "detect_magic_bytes",
    "validate_extension",
    "validate_mime_type",
    "sanitize_csv_cell",
    "content_checksum",
    "ADAPTERS",
    "adapter_for_format",
]
