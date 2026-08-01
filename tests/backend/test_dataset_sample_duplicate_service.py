import hashlib

from backend.services.dataset_sample_duplicate_service import ExternalDatasetDuplicateService


def _service() -> ExternalDatasetDuplicateService:
    return ExternalDatasetDuplicateService()


def _record(public_id: str, content: str, **payload) -> dict:
    return {
        "public_id": public_id,
        "normalized_content": content,
        "record_checksum": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "structured_payload": payload,
    }


def test_group_exact_duplicates_finds_identical_checksums() -> None:
    records = [
        _record("r1", "hello world"),
        _record("r2", "hello world"),
        _record("r3", "different content"),
    ]
    groups = _service().group_exact_duplicates(records)
    assert groups == [["r1", "r2"]]


def test_group_exact_duplicates_returns_empty_when_all_unique() -> None:
    records = [_record("r1", "a"), _record("r2", "b")]
    assert _service().group_exact_duplicates(records) == []


def test_group_normalized_duplicates_ignores_whitespace_and_case() -> None:
    records = [
        _record("r1", "Hello   World"),
        _record("r2", "hello world"),
    ]
    groups = _service().group_normalized_duplicates(records)
    assert groups == [["r1", "r2"]]


def test_group_near_duplicates_finds_similar_text() -> None:
    records = [
        _record("r1", "the quick brown fox jumps over the lazy dog"),
        _record("r2", "the quick brown fox jumps over the lazy cat"),
        _record("r3", "completely unrelated sentence about something else entirely"),
    ]
    groups = _service().group_near_duplicates(records, threshold=0.5)
    assert any(set(group) == {"r1", "r2"} for group in groups)


def test_group_near_duplicates_does_not_group_dissimilar_records() -> None:
    records = [
        _record("r1", "a completely different topic about cooking rice"),
        _record("r2", "an entirely unrelated discussion of astronomy"),
    ]
    groups = _service().group_near_duplicates(records, threshold=0.9)
    assert groups == []


def test_is_duplicate_against_external_set() -> None:
    checksum = hashlib.sha256(b"content").hexdigest()
    assert (
        ExternalDatasetDuplicateService.is_duplicate_against_external_set(
            checksum, frozenset({checksum})
        )
        is True
    )
    assert (
        ExternalDatasetDuplicateService.is_duplicate_against_external_set(
            checksum, frozenset({"other"})
        )
        is False
    )


def test_find_conflicts_detects_disagreeing_labels() -> None:
    records = [
        _record("r1", "question one", question="q1", label="positive"),
        _record("r2", "question one restated", question="q1", label="negative"),
        _record("r3", "question two", question="q2", label="positive"),
    ]
    conflicts = _service().find_conflicts(records, key_field="question", value_field="label")
    assert len(conflicts) == 1
    assert conflicts[0]["key"] == "q1"
    assert set(conflicts[0]["record_public_ids"]) == {"r1", "r2"}
    assert conflicts[0]["conflicting_values"] == ["negative", "positive"]


def test_find_conflicts_returns_empty_when_values_agree() -> None:
    records = [
        _record("r1", "q", question="q1", label="positive"),
        _record("r2", "q", question="q1", label="positive"),
    ]
    assert _service().find_conflicts(records, key_field="question", value_field="label") == []


def test_find_conflicts_skips_records_missing_key_field() -> None:
    records = [_record("r1", "q", label="positive")]
    assert _service().find_conflicts(records, key_field="question", value_field="label") == []
