from backend.services.dataset_sample_parsing_service import (
    ExternalDatasetSampleParsingService,
    ParsingError,
)


def _service() -> ExternalDatasetSampleParsingService:
    return ExternalDatasetSampleParsingService()


def test_parse_text_produces_single_record() -> None:
    result = _service().parse(b"hello\r\nworld\r\n", extension=".txt")
    assert len(result.records) == 1
    assert result.records[0].raw_content == "hello\nworld\n"


def test_parse_text_flags_control_characters() -> None:
    result = _service().parse(b"hello\x07world", extension=".txt")
    assert "control_characters_detected" in result.warnings


def test_parse_markdown_uses_same_path_as_text() -> None:
    result = _service().parse(b"# Heading\n\nbody", extension=".md")
    assert result.records[0].raw_content == "# Heading\n\nbody"


def test_parse_csv_produces_one_record_per_row() -> None:
    content = b"name,age\nAsha,30\nRavi,25\n"
    result = _service().parse(content, extension=".csv")
    assert len(result.records) == 2
    assert result.records[0].structured_payload == {"name": "Asha", "age": "30"}


def test_parse_csv_reports_malformed_rows_without_aborting() -> None:
    content = b"name,age\nAsha,30\nRavi\n"
    result = _service().parse(content, extension=".csv")
    assert len(result.records) == 1
    assert len(result.malformed) == 1
    assert result.malformed[0]["reason"] == "column_count_mismatch"


def test_parse_csv_detects_semicolon_delimiter() -> None:
    content = b"name;age\nAsha;30\n"
    result = _service().parse(content, extension=".csv")
    assert result.records[0].structured_payload == {"name": "Asha", "age": "30"}


def test_parse_json_array_produces_one_record_per_item() -> None:
    content = b'[{"a": 1}, {"a": 2}]'
    result = _service().parse(content, extension=".json")
    assert len(result.records) == 2
    assert result.records[0].structured_payload == {"a": 1}


def test_parse_json_single_object_produces_one_record() -> None:
    content = b'{"a": 1, "b": 2}'
    result = _service().parse(content, extension=".json")
    assert len(result.records) == 1
    assert result.records[0].structured_payload == {"a": 1, "b": 2}


def test_parse_json_malformed_document_reports_without_raising() -> None:
    result = _service().parse(b"{not valid json", extension=".json")
    assert result.records == []
    assert result.malformed[0]["location"] == "document"


def test_parse_json_rejects_excessive_nesting() -> None:
    nested = "1"
    for _ in range(30):
        nested = f"[{nested}]"
    result = _service().parse(nested.encode("utf-8"), extension=".json")
    assert result.records == []
    assert result.malformed[0]["reason"] == "max_nesting_depth_exceeded"


def test_parse_jsonl_produces_one_record_per_line() -> None:
    content = b'{"a": 1}\n{"a": 2}\n'
    result = _service().parse(content, extension=".jsonl")
    assert len(result.records) == 2
    assert result.records[1].source_row_or_page == "line:2"


def test_parse_jsonl_reports_malformed_lines_without_aborting() -> None:
    content = b'{"a": 1}\nnot json\n{"a": 3}\n'
    result = _service().parse(content, extension=".jsonl")
    assert len(result.records) == 2
    assert len(result.malformed) == 1
    assert result.malformed[0]["location"] == "line:2"


def test_parse_jsonl_skips_blank_lines() -> None:
    content = b'{"a": 1}\n\n{"a": 2}\n'
    result = _service().parse(content, extension=".jsonl")
    assert len(result.records) == 2


def test_parse_unsupported_extension_raises() -> None:
    try:
        _service().parse(b"data", extension=".xml")
        raise AssertionError("expected ParsingError")
    except ParsingError as exc:
        assert exc.reason == "unsupported_format"


def test_parse_pdf_extracts_embedded_text() -> None:
    fitz = __import__("fitz")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello from page one")
    pdf_bytes = doc.tobytes()
    doc.close()

    result = _service().parse(pdf_bytes, extension=".pdf")
    assert len(result.records) == 1
    assert "hello from page one" in result.records[0].raw_content
    assert result.records[0].source_row_or_page == "page:1"
    assert result.ocr_derived is False


def test_parse_pdf_rejects_encrypted_document() -> None:
    fitz = __import__("fitz")
    doc = fitz.open()
    doc.new_page()
    encrypted_bytes = doc.tobytes(
        encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw="owner", user_pw="user"
    )
    doc.close()

    try:
        _service().parse(encrypted_bytes, extension=".pdf")
        raise AssertionError("expected ParsingError")
    except ParsingError as exc:
        assert exc.reason == "encrypted_pdf_rejected"


def test_parse_pdf_uses_ocr_only_when_engine_supplied_and_page_is_empty() -> None:
    fitz = __import__("fitz")
    doc = fitz.open()
    doc.new_page()  # a page with no embedded text at all
    pdf_bytes = doc.tobytes()
    doc.close()

    result_without_ocr = _service().parse(pdf_bytes, extension=".pdf")
    assert result_without_ocr.records == []
    assert "no_embedded_text_on_page_1" in result_without_ocr.warnings

    def fake_ocr(page, *, language: str) -> str:
        return "ocr recovered text"

    result_with_ocr = ExternalDatasetSampleParsingService().parse_pdf(
        pdf_bytes, ocr_engine=fake_ocr
    )
    assert result_with_ocr.ocr_derived is True
    assert result_with_ocr.records[0].raw_content == "ocr recovered text"
