"""Deterministic, dependency-free text-extraction helpers.

Actual PDF parsing and OCR reuse Phase 5's optional ``fitz``/
``pytesseract`` imports directly in
``backend/services/corpus_processing_service.py`` -- exactly the same
optional-import pattern ``backend/services/document_service.py``
already uses, never a second OCR engine. This module holds only the
pure, dependency-free extraction paths (plain text, markdown, HTML
snapshot stripping, and dataset/document-record projection) plus
shared confidence-scoring and issue-summary helpers used by every
extraction method.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

_HTML_TAG_PATTERN = re.compile(r"<script.*?</script>|<style.*?</style>|<[^>]+>", re.DOTALL)
_HTML_ENTITY_MAP = {
    "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&nbsp;": " ",
}
_MARKDOWN_SYNTAX_PATTERN = re.compile(
    r"^#{1,6}\s+|\*\*|__|`{1,3}|^\s*[-*+]\s+|^\s*\d+\.\s+", re.MULTILINE
)


def content_checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def extract_plain_text(raw_bytes: bytes, *, encoding: str = "utf-8") -> dict[str, Any]:
    text = raw_bytes.decode(encoding, errors="replace")
    return {"text": text, "confidence": 1.0, "issues": []}


def extract_markdown_text(raw_bytes: bytes, *, encoding: str = "utf-8") -> dict[str, Any]:
    """Strips markdown syntax markers only -- headings become plain
    lines (heading structure is preserved separately by the
    segmentation stage reading the original text), never a full
    markdown-to-HTML render."""

    text = raw_bytes.decode(encoding, errors="replace")
    stripped = _MARKDOWN_SYNTAX_PATTERN.sub("", text)
    return {"text": stripped, "raw_text": text, "confidence": 1.0, "issues": []}


def extract_html_snapshot_text(raw_bytes: bytes, *, encoding: str = "utf-8") -> dict[str, Any]:
    html = raw_bytes.decode(encoding, errors="replace")
    stripped = _HTML_TAG_PATTERN.sub(" ", html)
    for entity, replacement in _HTML_ENTITY_MAP.items():
        stripped = stripped.replace(entity, replacement)
    collapsed = re.sub(r"[ \t]{2,}", " ", stripped)
    collapsed = re.sub(r"\n{3,}", "\n\n", collapsed)
    return {"text": collapsed.strip(), "confidence": 0.9, "issues": ["html_stripped"]}


def project_dataset_record(
    *, instruction: str | None, input_text: str | None, output_text: str | None
) -> dict[str, Any]:
    """Projects already-extracted text straight out of an existing
    ``dataset_records`` row -- never a second extraction pass over
    content Phase 3 already processed."""

    parts = [part for part in (instruction, input_text, output_text) if part]
    text = "\n\n".join(parts)
    return {"text": text, "confidence": 1.0, "issues": [] if text else ["empty_projection"]}


def project_document_pages(pages_cleaned_text: list[str]) -> dict[str, Any]:
    """Projects already-extracted, already-cleaned page text straight
    out of existing ``document_pages`` rows (Phase 5) -- never a second
    PDF/OCR extraction pass over content already extracted."""

    text = "\n\n".join(page for page in pages_cleaned_text if page)
    return {
        "text": text,
        "confidence": 1.0 if text else 0.0,
        "issues": [] if text else ["no_cleaned_page_text_available"],
    }


def build_issue_summary(issues: list[str]) -> list[dict[str, str]]:
    return [{"issue_code": issue} for issue in issues]
