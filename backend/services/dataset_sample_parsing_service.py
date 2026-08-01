"""Phase 12 Step 13 safe, bounded parsing for the 6 supported text
formats (TXT, Markdown, CSV, JSON, JSONL, PDF). Every parser is
bounded (row/line/nesting/page limits from `core_model.sample_import`)
and reports malformed rows/lines instead of raising -- one bad record
must never abort parsing the rest of a sample. PDF extraction mirrors
(does not import, since it is a private method) the exact pattern
already mirrored twice in this codebase
(`corpus_processing_service.py` -> `dataset_verification_transport.py`
-> here): embedded-text-only, encrypted/password-protected PDFs
rejected outright, no JavaScript execution, no embedded-attachment
extraction. OCR is never attempted automatically -- a page with no
embedded text simply yields empty text plus a warning, unless a caller
explicitly supplies an `ocr_engine` callable (Step 13's "OCR only when
required").
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from typing import Any

from core_model.sample_import import (
    MAX_CSV_ROWS,
    MAX_JSON_NESTING_DEPTH,
    MAX_JSONL_LINES,
    MAX_OCR_PAGES,
    MAX_PDF_PAGES,
    MAX_TEXT_RECORD_CHARS,
)

try:
    import fitz
except ImportError:  # pragma: no cover - capability fallback
    fitz = None


class ParsingError(RuntimeError):
    def __init__(self, reason: str, message: str = "") -> None:
        super().__init__(message or reason)
        self.reason = reason


@dataclass
class ParsedRecord:
    source_row_or_page: str | None
    raw_content: str
    structured_payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    records: list[ParsedRecord] = field(default_factory=list)
    malformed: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ocr_derived: bool = False


def _bounded(text: str, warnings: list[str]) -> str:
    if len(text) > MAX_TEXT_RECORD_CHARS:
        warnings.append("record_truncated_to_char_limit")
        return text[:MAX_TEXT_RECORD_CHARS]
    return text


def _decode(content: bytes) -> tuple[str, list[str]]:
    warnings: list[str] = []
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("utf-8", errors="replace")
        warnings.append("encoding_not_valid_utf8")
    return text, warnings


def _normalize_line_endings(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


class ExternalDatasetSampleParsingService:
    def parse(self, content: bytes, *, extension: str) -> ParseResult:
        if extension in (".txt", ".md", ".markdown"):
            return self.parse_text(content)
        if extension == ".csv":
            return self.parse_csv(content)
        if extension == ".json":
            return self.parse_json(content)
        if extension == ".jsonl":
            return self.parse_jsonl(content)
        if extension == ".pdf":
            return self.parse_pdf(content)
        raise ParsingError("unsupported_format", extension)

    def parse_text(self, content: bytes) -> ParseResult:
        text, warnings = _decode(content)
        text = _normalize_line_endings(text)
        control_chars = sum(
            1 for char in text if ord(char) < 32 and char not in ("\n", "\t")
        )
        if control_chars:
            warnings.append("control_characters_detected")
        text = _bounded(text, warnings)
        return ParseResult(records=[ParsedRecord(None, text)], warnings=warnings)

    def parse_csv(self, content: bytes) -> ParseResult:
        text, warnings = _decode(content)
        text = _normalize_line_endings(text)
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
            delimiter = dialect.delimiter
        except csv.Error:
            delimiter = ","
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        rows = list(reader)
        if not rows:
            return ParseResult(warnings=warnings)
        header = rows[0]
        records: list[ParsedRecord] = []
        malformed: list[dict[str, Any]] = []
        for index, row in enumerate(rows[1:MAX_CSV_ROWS + 1], start=2):
            if len(row) != len(header):
                malformed.append(
                    {"location": f"row:{index}", "reason": "column_count_mismatch"}
                )
                continue
            payload = dict(zip(header, row, strict=True))
            raw = delimiter.join(row)
            records.append(ParsedRecord(f"row:{index}", _bounded(raw, warnings), payload))
        if len(rows) - 1 > MAX_CSV_ROWS:
            warnings.append("rows_truncated_to_limit")
        return ParseResult(records=records, malformed=malformed, warnings=warnings)

    def parse_json(self, content: bytes) -> ParseResult:
        text, warnings = _decode(content)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return ParseResult(
                malformed=[{"location": "document", "reason": f"invalid_json: {exc.msg}"}],
                warnings=warnings,
            )
        depth = _max_depth(data)
        if depth > MAX_JSON_NESTING_DEPTH:
            return ParseResult(
                malformed=[{"location": "document", "reason": "max_nesting_depth_exceeded"}],
                warnings=warnings,
            )
        items = data if isinstance(data, list) else [data]
        records = [
            ParsedRecord(
                f"item:{index}",
                _bounded(json.dumps(item, ensure_ascii=False), warnings),
                item if isinstance(item, dict) else {"value": item},
            )
            for index, item in enumerate(items)
        ]
        return ParseResult(records=records, warnings=warnings)

    def parse_jsonl(self, content: bytes) -> ParseResult:
        text, warnings = _decode(content)
        lines = _normalize_line_endings(text).split("\n")
        records: list[ParsedRecord] = []
        malformed: list[dict[str, Any]] = []
        seen_keys: set[str] = set()
        for index, line in enumerate(lines[:MAX_JSONL_LINES], start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                item = json.loads(stripped)
            except json.JSONDecodeError as exc:
                malformed.append(
                    {"location": f"line:{index}", "reason": f"invalid_json: {exc.msg}"}
                )
                continue
            payload = item if isinstance(item, dict) else {"value": item}
            if isinstance(item, dict):
                key_signature = ",".join(sorted(item.keys()))
                if key_signature in seen_keys:
                    warnings.append(f"duplicate_key_signature_at_line_{index}")
                seen_keys.add(key_signature)
            records.append(
                ParsedRecord(f"line:{index}", _bounded(stripped, warnings), payload)
            )
        if len(lines) > MAX_JSONL_LINES:
            warnings.append("lines_truncated_to_limit")
        return ParseResult(records=records, malformed=malformed, warnings=warnings)

    def parse_pdf(
        self, content: bytes, *, ocr_engine: Any = None, ocr_language: str = "eng"
    ) -> ParseResult:
        if fitz is None:
            raise ParsingError("pdf_extraction_unavailable")
        warnings: list[str] = []
        records: list[ParsedRecord] = []
        ocr_derived = False
        with fitz.open(stream=content, filetype="pdf") as pdf:
            if pdf.needs_pass or pdf.is_encrypted:
                raise ParsingError("encrypted_pdf_rejected")
            page_count = len(pdf)
            if page_count > MAX_PDF_PAGES:
                warnings.append("pdf_truncated_to_page_limit")
            for page_number, page in enumerate(pdf, start=1):
                if page_number > MAX_PDF_PAGES:
                    break
                text = page.get_text("text")
                if not text.strip():
                    if ocr_engine is not None and page_number <= MAX_OCR_PAGES:
                        text = ocr_engine(page, language=ocr_language) or ""
                        if text.strip():
                            ocr_derived = True
                    if not text.strip():
                        warnings.append(f"no_embedded_text_on_page_{page_number}")
                        continue
                records.append(
                    ParsedRecord(f"page:{page_number}", _bounded(text, warnings))
                )
        return ParseResult(records=records, warnings=warnings, ocr_derived=ocr_derived)


def _max_depth(value: Any, current: int = 0) -> int:
    if current > MAX_JSON_NESTING_DEPTH + 1:
        return current
    if isinstance(value, dict):
        if not value:
            return current + 1
        return max(_max_depth(v, current + 1) for v in value.values())
    if isinstance(value, list):
        if not value:
            return current + 1
        return max(_max_depth(v, current + 1) for v in value)
    return current
