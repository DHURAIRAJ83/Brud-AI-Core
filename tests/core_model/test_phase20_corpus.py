import json

from core_model.corpus.format_adapters import (
    ADAPTERS,
    ExtractionOptions,
    detect_magic_bytes,
    sanitize_csv_cell,
    validate_extension,
    validate_mime_type,
)
from core_model.corpus.readiness import (
    READINESS_DIMENSIONS,
    build_readiness_report,
    overall_readiness,
)
from core_model.corpus.tokenizer_analysis import (
    aggregate_metrics,
    analyze_token_ids,
    compute_script_token_ratios,
    round_trip_integrity_rate,
    script_token_bucket,
)

# --- format adapters -----------------------------------------------------


def test_txt_adapter_extracts_tamil_text():
    result = ADAPTERS["txt"].extract("தமிழ் உரை சோதனை.".encode(), ExtractionOptions())
    assert result.text == "தமிழ் உரை சோதனை."
    assert result.confidence == 1.0


def test_json_adapter_extracts_configured_text_field_from_record_list():
    payload = json.dumps([{"text": "தமிழ் ஒன்று"}, {"text": "தமிழ் இரண்டு"}]).encode()
    result = ADAPTERS["json"].extract(payload, ExtractionOptions(text_field="text"))
    assert "தமிழ் ஒன்று" in result.text
    assert "தமிழ் இரண்டு" in result.text
    assert result.issues == []


def test_json_adapter_falls_back_and_flags_when_configured_field_missing():
    payload = json.dumps({"items": [{"text": "தமிழ்"}]}).encode()
    result = ADAPTERS["json"].extract(payload, ExtractionOptions(text_field="text"))
    assert "தமிழ்" in result.text
    assert "configured_text_field_missing_used_fallback" in result.issues


def test_json_adapter_rejects_invalid_json():
    result = ADAPTERS["json"].extract(b"{not valid json", ExtractionOptions())
    assert result.confidence == 0.0
    assert "invalid_json" in result.issues


def test_json_adapter_bounded_recursion_never_raises_on_deeply_nested_input():
    nested: dict = {"text": "leaf"}
    for _ in range(50):
        nested = {"child": nested}
    payload = json.dumps(nested).encode()
    result = ADAPTERS["json"].extract(payload, ExtractionOptions())
    assert isinstance(result.text, str)


def test_jsonl_adapter_extracts_each_line():
    lines = [json.dumps({"text": t}) for t in ["தமிழ் ஒன்று", "தமிழ் இரண்டு"]]
    payload = "\n".join(lines).encode()
    result = ADAPTERS["jsonl"].extract(payload, ExtractionOptions(text_field="text"))
    assert "தமிழ் ஒன்று" in result.text
    assert "தமிழ் இரண்டு" in result.text


def test_jsonl_adapter_flags_invalid_line_without_dropping_whole_file():
    payload = (json.dumps({"text": "valid line"}) + "\nnot json\n").encode()
    result = ADAPTERS["jsonl"].extract(payload, ExtractionOptions(text_field="text"))
    assert "valid line" in result.text
    assert any("invalid_json_line" in issue for issue in result.issues)


def test_csv_adapter_extracts_selected_column():
    payload = "text,note\nதமிழ் வரி,fine\n".encode()
    result = ADAPTERS["csv"].extract(payload, ExtractionOptions(text_columns=("text",)))
    assert "தமிழ் வரி" in result.text
    assert "fine" not in result.text


def test_csv_adapter_neutralizes_formula_injection():
    payload = b"text\n=cmd|calc\n"
    result = ADAPTERS["csv"].extract(payload, ExtractionOptions(text_columns=("text",)))
    assert result.text.startswith("text: '=")


def test_sanitize_csv_cell_prefixes_formula_trigger_characters():
    assert sanitize_csv_cell("=1+1") == "'=1+1"
    assert sanitize_csv_cell("+SUM(A1)") == "'+SUM(A1)"
    assert sanitize_csv_cell("ordinary text") == "ordinary text"


def test_detect_magic_bytes_identifies_pdf_and_docx():
    assert detect_magic_bytes(b"%PDF-1.7 rest of file") == "pdf"
    assert detect_magic_bytes(b"PK\x03\x04 rest of zip") == "docx"
    assert detect_magic_bytes(b"plain text content") is None


def test_validate_extension_rejects_unsupported_format():
    assert validate_extension("json") is True
    assert validate_extension("exe") is False
    assert validate_extension("EXE") is False


def test_validate_mime_type_matches_declared_format_only():
    assert validate_mime_type("text/csv", format_name="csv") is True
    assert validate_mime_type("application/pdf", format_name="csv") is False


# --- readiness gate -----------------------------------------------------


def test_overall_readiness_any_fail_is_not_ready():
    results = dict.fromkeys(READINESS_DIMENSIONS, "pass")
    results["licence_compliance"] = "fail"
    assert overall_readiness(results) == "not_ready"


def test_overall_readiness_warning_never_silently_upgraded_to_pass():
    results = dict.fromkeys(READINESS_DIMENSIONS, "pass")
    results["balance_adequacy"] = "warning"
    assert overall_readiness(results) == "ready_with_warnings"


def test_overall_readiness_not_evaluated_is_ready_with_warnings_not_ready():
    results = dict.fromkeys(READINESS_DIMENSIONS, "pass")
    results["tokenizer_compatibility"] = "not_evaluated"
    assert overall_readiness(results) == "ready_with_warnings"


def test_overall_readiness_all_pass_is_ready():
    results = dict.fromkeys(READINESS_DIMENSIONS, "pass")
    assert overall_readiness(results) == "ready"


def test_build_readiness_report_counts_each_status():
    results = dict.fromkeys(READINESS_DIMENSIONS, "pass")
    results["licence_compliance"] = "fail"
    results["balance_adequacy"] = "warning"
    results["tokenizer_compatibility"] = "not_evaluated"
    report = build_readiness_report(results)
    assert report["overall_result"] == "not_ready"
    assert report["fail_count"] == 1
    assert report["warning_count"] == 1
    assert report["not_evaluated_count"] == 1
    assert report["pass_count"] == len(READINESS_DIMENSIONS) - 3


# --- tokenizer compatibility analysis -----------------------------------------------------


def test_analyze_token_ids_computes_unknown_rate_and_long_sequence_flag():
    metrics = analyze_token_ids(
        "தமிழ் உரை", [1, 2, 0, 3], unk_id=0, max_sequence_length=10
    )
    assert metrics["token_count"] == 4
    assert metrics["unknown_token_count"] == 1
    assert metrics["unknown_token_rate"] == 0.25
    assert metrics["is_long_sequence"] is False
    assert metrics["truncation_risk"] is False


def test_analyze_token_ids_flags_long_sequence_over_max_length():
    metrics = analyze_token_ids("text", [1, 2, 3], unk_id=99, max_sequence_length=2)
    assert metrics["is_long_sequence"] is True
    assert metrics["truncation_risk"] is True


def test_aggregate_metrics_handles_empty_input():
    aggregate = aggregate_metrics([])
    assert aggregate["total_tokens"] == 0
    assert aggregate["unknown_token_rate"] == 0.0


def test_aggregate_metrics_combines_multiple_rows():
    rows = [
        analyze_token_ids("a", [1, 0], unk_id=0, max_sequence_length=10),
        analyze_token_ids("bb", [1, 2, 3], unk_id=0, max_sequence_length=2),
    ]
    aggregate = aggregate_metrics(rows)
    assert aggregate["total_tokens"] == 5
    assert aggregate["long_sequence_rate"] == 0.5


def test_round_trip_integrity_rate_computes_exact_match_fraction():
    pairs = [("hello", "hello"), ("world", "wrold")]
    assert round_trip_integrity_rate(pairs) == 0.5
    assert round_trip_integrity_rate([]) == 0.0


def test_script_token_bucket_maps_known_and_unknown_categories():
    assert script_token_bucket("ta") == "tamil_token_ratio"
    assert script_token_bucket("tgl") == "tanglish_token_ratio"
    assert script_token_bucket("unknown") == "other_token_ratio"


def test_compute_script_token_ratios_sums_to_one():
    rows_by_language = {
        "ta": {"total_tokens": 60},
        "en": {"total_tokens": 40},
    }
    ratios = compute_script_token_ratios(rows_by_language)
    assert ratios["tamil_token_ratio"] == 0.6
    assert ratios["english_token_ratio"] == 0.4
    assert round(sum(ratios.values()), 6) == 1.0


def test_compute_script_token_ratios_empty_when_no_tokens():
    assert compute_script_token_ratios({}) == {}
