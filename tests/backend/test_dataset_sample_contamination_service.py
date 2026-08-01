from backend.services.dataset_sample_contamination_service import (
    ExternalDatasetContaminationService,
)
from core_model.corpus.exact_deduplication import tamil_safe_normalized_checksum


def _service() -> ExternalDatasetContaminationService:
    return ExternalDatasetContaminationService()


def test_unknown_when_no_comparison_sets_supplied() -> None:
    result = _service().check("some text")
    assert result["status"] == "unknown"
    assert result["blocks_training"] is False


def test_clear_when_no_checksum_matches() -> None:
    result = _service().check("some unrelated text", test_checksums=frozenset({"a" * 64}))
    assert result["status"] == "clear"


def test_confirmed_overlap_when_checksum_matches_test_set() -> None:
    text = "this exact segment appears in the test set"
    checksum = tamil_safe_normalized_checksum(text)
    result = _service().check(text, test_checksums=frozenset({checksum}))
    assert result["status"] == "confirmed_overlap"
    assert "test_leakage" in result["issues"]
    assert result["blocks_training"] is True


def test_training_duplicate_does_not_block_training() -> None:
    text = "this segment is a training-split duplicate only"
    checksum = tamil_safe_normalized_checksum(text)
    result = _service().check(text, training_checksums=frozenset({checksum}))
    assert result["status"] == "confirmed_overlap"
    assert "training_duplicate" in result["issues"]
    assert result["blocks_training"] is False


def test_evaluation_fixture_overlap_blocks_training() -> None:
    text = "this segment overlaps an evaluation fixture"
    checksum = tamil_safe_normalized_checksum(text)
    result = _service().check(text, evaluation_fixture_checksums=frozenset({checksum}))
    assert result["blocks_training"] is True
