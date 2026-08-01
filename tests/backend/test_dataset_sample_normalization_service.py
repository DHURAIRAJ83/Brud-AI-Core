import hashlib

from backend.services.dataset_sample_normalization_service import (
    NORMALIZER_VERSION,
    PARSER_VERSION,
    ExternalDatasetSampleNormalizationService,
)
from backend.services.dataset_sample_parsing_service import ParsedRecord


def _service() -> ExternalDatasetSampleNormalizationService:
    return ExternalDatasetSampleNormalizationService()


def test_normalize_preserves_raw_content_separately_from_normalized() -> None:
    record = ParsedRecord(source_row_or_page="row:2", raw_content="Hello   world\r\n")
    normalized = _service().normalize(record, source_checksum="abc123")
    assert normalized.raw_content == "Hello   world\r\n"
    assert normalized.normalized_content != normalized.raw_content
    assert normalized.normalized_content == "Hello world"


def test_normalize_computes_record_checksum_from_raw_content() -> None:
    record = ParsedRecord(source_row_or_page=None, raw_content="hello")
    normalized = _service().normalize(record, source_checksum="src-checksum")
    assert normalized.record_checksum == hashlib.sha256(b"hello").hexdigest()
    assert normalized.source_checksum == "src-checksum"


def test_normalize_carries_parser_and_normalizer_versions() -> None:
    record = ParsedRecord(source_row_or_page=None, raw_content="hi")
    normalized = _service().normalize(record, source_checksum="x")
    assert normalized.parser_version == PARSER_VERSION
    assert normalized.normalizer_version == NORMALIZER_VERSION


def test_normalize_defaults_ocr_derived_to_false() -> None:
    record = ParsedRecord(source_row_or_page=None, raw_content="hi")
    normalized = _service().normalize(record, source_checksum="x")
    assert normalized.ocr_derived is False


def test_normalize_propagates_ocr_derived_flag() -> None:
    record = ParsedRecord(source_row_or_page="page:1", raw_content="ocr text")
    normalized = _service().normalize(record, source_checksum="x", ocr_derived=True)
    assert normalized.ocr_derived is True


def test_normalize_preserves_tamil_combining_marks() -> None:
    tamil_text = "தமிழ் மொழி"
    record = ParsedRecord(source_row_or_page=None, raw_content=tamil_text)
    normalized = _service().normalize(record, source_checksum="x")
    assert normalized.tamil_combining_marks_preserved is True
    assert "தமிழ்" in normalized.normalized_content


def test_normalize_reports_unicode_integrity_status() -> None:
    record = ParsedRecord(source_row_or_page=None, raw_content="clean text")
    normalized = _service().normalize(record, source_checksum="x")
    assert normalized.unicode_integrity_status == "valid"


def test_normalize_flags_replacement_characters() -> None:
    record = ParsedRecord(source_row_or_page=None, raw_content="corrupted � text")
    normalized = _service().normalize(record, source_checksum="x")
    assert normalized.unicode_integrity_status == "replacement_characters_detected"


def test_normalize_preserves_structured_payload() -> None:
    record = ParsedRecord(
        source_row_or_page="row:1", raw_content="a,b", structured_payload={"a": "1", "b": "2"}
    )
    normalized = _service().normalize(record, source_checksum="x")
    assert normalized.structured_payload == {"a": "1", "b": "2"}
