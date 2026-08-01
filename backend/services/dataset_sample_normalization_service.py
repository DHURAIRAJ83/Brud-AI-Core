"""Phase 12 Step 14 record normalization: turns a `ParsedRecord` into
the quarantine-only representation stored in
`external_dataset_sample_records`, preserving raw and normalized
content as two separate fields -- the original is never overwritten.

Reuses `core_model.corpus.unicode_normalization.normalize_unicode()`
(itself reusing Phase 16's `normalize_source_text` unchanged) for
NFC/newline/control-character normalization and Tamil-combining-mark
preservation verification -- never a second normalization
implementation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from backend.services.dataset_sample_parsing_service import ParsedRecord
from core_model.corpus.unicode_normalization import normalize_unicode

PARSER_VERSION = "phase12-parser-v1"
NORMALIZER_VERSION = "phase12-normalizer-v1"


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class NormalizedRecord:
    source_row_or_page: str | None
    raw_content: str
    normalized_content: str
    structured_payload: dict[str, Any]
    source_checksum: str
    record_checksum: str
    parser_version: str
    normalizer_version: str
    ocr_derived: bool
    unicode_integrity_status: str
    tamil_combining_marks_preserved: bool


class ExternalDatasetSampleNormalizationService:
    def normalize(
        self, record: ParsedRecord, *, source_checksum: str, ocr_derived: bool = False
    ) -> NormalizedRecord:
        result = normalize_unicode(record.raw_content)
        normalized_text = result["normalized_text"]
        return NormalizedRecord(
            source_row_or_page=record.source_row_or_page,
            raw_content=record.raw_content,
            normalized_content=normalized_text,
            structured_payload=record.structured_payload,
            source_checksum=source_checksum,
            record_checksum=_checksum(record.raw_content),
            parser_version=PARSER_VERSION,
            normalizer_version=NORMALIZER_VERSION,
            ocr_derived=ocr_derived,
            unicode_integrity_status=result["unicode_integrity_status"],
            tamil_combining_marks_preserved=result["tamil_combining_marks_preserved"],
        )
