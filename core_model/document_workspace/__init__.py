"""Phase 4 (Data Studio) PDF Research Workspace pure-function package.

Enhances the existing Phase 5 (`005_phase5_document_processing`) PDF
pipeline (``backend/services/document_service.py``) with a governed
human-review layer -- it never re-implements embedded extraction, OCR
invocation, or segmentation, all of which already exist and continue
to work unchanged. Every enum here is the single source of truth
shared by the schema (``backend/database/schema.py``'s Phase 4 block)
and the backend services.
"""

from __future__ import annotations

# Human review outcome, layered on top of the existing (unchanged)
# `document_pages.extraction_status` (pending/extracting/success/warning/
# failed/skipped), which continues to mean extraction outcome only.
REVIEW_STATUSES = ("pending", "needs_correction", "corrected", "approved", "rejected", "excluded")

REVIEW_ACTIONS = (
    "approve",
    "reject",
    "exclude",
    "request_correction",
    "request_ocr_rerun",
    "request_extraction_rerun",
    "restore_previous_revision",
    "reopen",
)

# Matches the existing `document_pages.extraction_method` CHECK values,
# plus 'failed' for a recorded extraction attempt that raised.
EXTRACTION_METHODS = ("embedded", "ocr", "hybrid", "manual", "failed")

REPEATED_ELEMENT_TYPES = ("header", "footer", "page_number", "unknown")

REPEATED_ELEMENT_STATUSES = ("suggested", "accepted", "rejected", "applied")

CORRECTION_CATEGORIES = (
    "unicode_normalization",
    "whitespace",
    "line_break",
    "broken_word",
    "header_removed",
    "footer_removed",
    "page_number_removed",
    "ocr_character_correction",
    "manual_rewrite",
    "other",
)

SUGGESTION_TYPES = (
    "broken_tamil_word",
    "repeated_whitespace",
    "replacement_glyph",
    "suspicious_latin_in_tamil",
    "duplicated_line",
    "repeated_header",
    "likely_page_number",
    "unbalanced_punctuation",
)
