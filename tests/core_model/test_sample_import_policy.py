import pytest

from core_model.sample_import import (
    ACTIVE_SAMPLE_IMPORT_STATUSES,
    AMBIGUOUS_PII_FINDING_STATUSES,
    APPROVAL_STATUSES,
    ARCHIVE_COMPRESSION_RATIO_THRESHOLD,
    ARCHIVE_ENTRY_REJECTION_REASONS,
    BLOCKED_FILE_CLASSES,
    BLOCKED_FILE_STATUSES,
    BLOCKING_CONTAMINATION_STATUSES,
    BLOCKING_POISONING_RESULTS,
    BLOCKING_SCAN_VERDICTS,
    CONFLICT_TYPES,
    CONTAMINATION_STATUSES,
    DELETION_REQUEST_STATUSES,
    DERIVED_REVISION_REVIEW_DECISIONS,
    DUPLICATE_CONFLICT_RESOLUTION_STATUSES,
    DUPLICATE_TYPES,
    FILE_STATUSES,
    MANIFEST_ONLY_MODALITIES,
    METADATA_ONLY_MODALITIES,
    MODALITIES,
    PII_CATEGORIES,
    PII_FINDING_STATUSES,
    POISONING_RESULTS,
    POISONING_SIGNAL_TYPES,
    PROHIBITED_SAMPLE_IMPORT_PURPOSES,
    QUALITY_ISSUE_TYPES,
    QUALITY_STATES,
    RECORD_STATUSES,
    REVIEW_DECISIONS,
    REVIEW_TARGET_TYPES,
    SAFETY_CATEGORIES,
    SAFETY_SEVERITIES,
    SAMPLE_IMPORT_PURPOSES,
    SAMPLE_IMPORT_STAGES,
    SAMPLE_IMPORT_STATUSES,
    SAMPLE_LANGUAGES,
    SCAN_VERDICTS,
    SELECTION_METHODS,
    SUPPORTED_ARCHIVE_FORMATS,
    SUPPORTED_TEXT_FORMATS,
    TERMINAL_SAMPLE_IMPORT_STATUSES,
    TRAINING_ASSESSMENT_STATUSES,
    is_terminal_sample_import_status,
    validate_sample_import_purpose,
)


def test_all_enums_are_nonempty_unique_str_tuples() -> None:
    for values in (
        MODALITIES, METADATA_ONLY_MODALITIES, MANIFEST_ONLY_MODALITIES, SUPPORTED_TEXT_FORMATS,
        SAMPLE_IMPORT_STATUSES, ACTIVE_SAMPLE_IMPORT_STATUSES, TERMINAL_SAMPLE_IMPORT_STATUSES,
        SAMPLE_IMPORT_STAGES, SAMPLE_IMPORT_PURPOSES, PROHIBITED_SAMPLE_IMPORT_PURPOSES,
        APPROVAL_STATUSES, SELECTION_METHODS, FILE_STATUSES, BLOCKED_FILE_STATUSES,
        BLOCKED_FILE_CLASSES, SUPPORTED_ARCHIVE_FORMATS, ARCHIVE_ENTRY_REJECTION_REASONS,
        SCAN_VERDICTS, BLOCKING_SCAN_VERDICTS, RECORD_STATUSES, SAMPLE_LANGUAGES,
        PII_CATEGORIES, PII_FINDING_STATUSES, AMBIGUOUS_PII_FINDING_STATUSES,
        SAFETY_CATEGORIES, SAFETY_SEVERITIES, QUALITY_STATES, QUALITY_ISSUE_TYPES,
        DUPLICATE_TYPES, CONFLICT_TYPES, DUPLICATE_CONFLICT_RESOLUTION_STATUSES,
        CONTAMINATION_STATUSES, BLOCKING_CONTAMINATION_STATUSES, POISONING_SIGNAL_TYPES,
        POISONING_RESULTS, BLOCKING_POISONING_RESULTS, REVIEW_TARGET_TYPES, REVIEW_DECISIONS,
        DERIVED_REVISION_REVIEW_DECISIONS, TRAINING_ASSESSMENT_STATUSES,
        DELETION_REQUEST_STATUSES,
    ):
        assert isinstance(values, tuple)
        assert len(values) > 0
        assert len(values) == len(set(values))
        assert all(isinstance(v, str) and v for v in values)


def test_active_and_terminal_statuses_partition_all_statuses_without_overlap() -> None:
    active = set(ACTIVE_SAMPLE_IMPORT_STATUSES)
    terminal = set(TERMINAL_SAMPLE_IMPORT_STATUSES)
    assert active & terminal == set()
    assert active | terminal == set(SAMPLE_IMPORT_STATUSES)


def test_subset_enums_are_true_subsets_of_their_parent_enum() -> None:
    assert set(ACTIVE_SAMPLE_IMPORT_STATUSES) <= set(SAMPLE_IMPORT_STATUSES)
    assert set(TERMINAL_SAMPLE_IMPORT_STATUSES) <= set(SAMPLE_IMPORT_STATUSES)
    assert set(BLOCKED_FILE_STATUSES) <= set(FILE_STATUSES)
    assert set(BLOCKING_SCAN_VERDICTS) <= set(SCAN_VERDICTS)
    assert set(AMBIGUOUS_PII_FINDING_STATUSES) <= set(PII_FINDING_STATUSES)
    assert set(BLOCKING_CONTAMINATION_STATUSES) <= set(CONTAMINATION_STATUSES)
    assert set(BLOCKING_POISONING_RESULTS) <= set(POISONING_RESULTS)
    assert set(DERIVED_REVISION_REVIEW_DECISIONS) <= set(REVIEW_DECISIONS)
    assert set(METADATA_ONLY_MODALITIES) <= set(MODALITIES)
    assert set(MANIFEST_ONLY_MODALITIES) <= set(MODALITIES)


def test_prohibited_purposes_never_overlap_permitted_purposes() -> None:
    assert set(SAMPLE_IMPORT_PURPOSES) & set(PROHIBITED_SAMPLE_IMPORT_PURPOSES) == set()


def test_prohibited_purposes_match_spec_exactly() -> None:
    assert set(PROHIBITED_SAMPLE_IMPORT_PURPOSES) == {"production_rag", "training", "model_release"}


def test_no_enum_anywhere_contains_a_training_approved_value() -> None:
    """Structural guarantee: no enum in this module contains a status
    that could be mistaken for training approval -- Phase 12 must
    never be able to *write* such a state because it does not exist."""

    all_values: set[str] = set()
    for values in (
        SAMPLE_IMPORT_STATUSES, TRAINING_ASSESSMENT_STATUSES, APPROVAL_STATUSES,
        REVIEW_DECISIONS, SCAN_VERDICTS,
    ):
        all_values |= set(values)
    assert "training_approved" not in all_values
    assert "approved" not in {v for v in all_values if "training" in v}


def test_training_assessment_statuses_never_include_approval() -> None:
    for status in TRAINING_ASSESSMENT_STATUSES:
        assert "approved" not in status


def test_validate_sample_import_purpose_accepts_permitted_purposes() -> None:
    for purpose in SAMPLE_IMPORT_PURPOSES:
        validate_sample_import_purpose(purpose)  # must not raise


@pytest.mark.parametrize("purpose", ["production_rag", "training", "model_release"])
def test_validate_sample_import_purpose_rejects_prohibited_purposes(purpose: str) -> None:
    with pytest.raises(ValueError):
        validate_sample_import_purpose(purpose)


def test_validate_sample_import_purpose_rejects_unknown_purpose() -> None:
    with pytest.raises(ValueError):
        validate_sample_import_purpose("not_a_real_purpose")


def test_is_terminal_sample_import_status() -> None:
    assert is_terminal_sample_import_status("validated") is True
    assert is_terminal_sample_import_status("rejected") is True
    assert is_terminal_sample_import_status("deleted") is True
    assert is_terminal_sample_import_status("draft") is False
    assert is_terminal_sample_import_status("needs_review") is False


def test_supported_text_formats_match_spec() -> None:
    assert set(SUPPORTED_TEXT_FORMATS) == {"txt", "markdown", "csv", "json", "jsonl", "pdf"}


def test_supported_archive_formats_are_the_explicit_safe_allowlist() -> None:
    assert set(SUPPORTED_ARCHIVE_FORMATS) == {"zip", "tar", "tar.gz"}


def test_archive_compression_ratio_threshold_is_bounded_positive_number() -> None:
    assert ARCHIVE_COMPRESSION_RATIO_THRESHOLD > 1.0


def test_sample_import_stages_do_not_duplicate_status_values() -> None:
    # Stage is a distinct dimension from status -- Step 4's "a single
    # boolean must not represent the lifecycle" implies stage and status
    # are two separate, non-redundant enums.
    assert set(SAMPLE_IMPORT_STAGES) & set(SAMPLE_IMPORT_STATUSES) == set()
