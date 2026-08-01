from backend.services.dataset_sample_quality_service import ExternalDatasetQualityService


def _service() -> ExternalDatasetQualityService:
    return ExternalDatasetQualityService()


def test_normal_content_passes() -> None:
    result = _service().assess(
        raw_content="This is a normal, well-formed training example about cooking.",
        normalized_content="This is a normal, well-formed training example about cooking.",
    )
    assert result["state"] == "pass"
    assert result["issues"] == []


def test_empty_content_fails() -> None:
    result = _service().assess(raw_content="", normalized_content="   ")
    assert result["state"] == "fail"
    assert any(issue["issue_type"] == "empty_content" for issue in result["issues"])


def test_too_short_content_fails() -> None:
    result = _service().assess(raw_content="hi", normalized_content="hi")
    assert result["state"] == "fail"
    assert any(issue["issue_type"] == "too_short" for issue in result["issues"])


def test_encoding_corruption_needs_review() -> None:
    result = _service().assess(
        raw_content="corrupted � text", normalized_content="corrupted text here for review"
    )
    assert any(issue["issue_type"] == "encoding_corruption" for issue in result["issues"])
    assert result["state"] == "needs_review"


def test_missing_required_fields_fails() -> None:
    result = _service().assess(
        raw_content="some content", normalized_content="some content",
        structured_payload={"question": "what is this"}, required_fields=["question", "answer"],
    )
    assert result["state"] == "fail"
    assert any(issue["issue_type"] == "missing_required_fields" for issue in result["issues"])


def test_invalid_label_needs_review() -> None:
    result = _service().assess(
        raw_content="content", normalized_content="valid content here",
        structured_payload={"label": "unknown_category"}, allowed_labels=["positive", "negative"],
    )
    assert any(issue["issue_type"] == "invalid_labels" for issue in result["issues"])
    assert result["state"] == "needs_review"


def test_template_repetition_detected() -> None:
    text = "\n".join(["Buy now! Click here!" for _ in range(5)])
    result = _service().assess(raw_content=text, normalized_content=text)
    assert any(issue["issue_type"] == "template_repetition" for issue in result["issues"])


def test_low_information_content_detected() -> None:
    text = " ".join(["lorem"] * 20)
    result = _service().assess(raw_content=text, normalized_content=text)
    assert any(issue["issue_type"] == "low_information_content" for issue in result["issues"])


def test_broken_markup_detected() -> None:
    text = "<div><span>unbalanced" * 3
    result = _service().assess(raw_content=text, normalized_content=text)
    assert any(issue["issue_type"] == "broken_markup" for issue in result["issues"])


def test_balanced_markup_not_flagged() -> None:
    text = "<div><span>balanced content that is reasonably long</span></div>"
    result = _service().assess(raw_content=text, normalized_content=text)
    assert not any(issue["issue_type"] == "broken_markup" for issue in result["issues"])


def test_question_answer_mismatch_detected_when_answer_empty() -> None:
    result = _service().assess(
        raw_content="content", normalized_content="reasonable content length here",
        structured_payload={"question": "What is the capital of Tamil Nadu?", "answer": ""},
    )
    assert any(issue["issue_type"] == "question_answer_mismatch" for issue in result["issues"])


def test_unbalanced_conversation_turns_detected() -> None:
    result = _service().assess(
        raw_content="content", normalized_content="reasonable content length here",
        structured_payload={
            "turns": [{"role": "user", "text": "hi"}, {"role": "user", "text": "hello"}]
        },
    )
    assert any(
        issue["issue_type"] == "unbalanced_conversation_turns" for issue in result["issues"]
    )


def test_language_mismatch_detected() -> None:
    result = _service().assess(
        raw_content="content", normalized_content="reasonable content length here",
        expected_language="tamil", detected_language="english",
    )
    assert any(issue["issue_type"] == "language_mismatch" for issue in result["issues"])


def test_pass_with_warning_when_only_low_severity_issues() -> None:
    text = "\n".join(["repeat this line exactly" for _ in range(5)])
    result = _service().assess(raw_content=text, normalized_content=text)
    assert result["state"] in ("pass_with_warning", "needs_review")
