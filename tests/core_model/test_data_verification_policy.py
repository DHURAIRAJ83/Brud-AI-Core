import pytest

from core_model.data_verification import (
    ACTIVE_VERIFICATION_CASE_STATUSES,
    ADMIN_ONLY_PERMISSION_STATUSES,
    AUTHORITY_PRECEDENCE,
    AUTOMATED_PERMISSION_STATUSES,
    BLOCKING_CONFLICT_SEVERITIES,
    CASE_SECTION_STATUSES,
    COMMERCIAL_USE_INTENDED_CATEGORIES,
    CONFLICT_RESOLUTION_STATUSES,
    CONFLICT_SEVERITIES,
    CONFLICT_TYPES,
    EVIDENCE_AUTHORITY_LEVELS,
    EVIDENCE_CONTENT_TYPES,
    EVIDENCE_LINK_ENTITY_TYPES,
    EVIDENCE_LINK_ROLES,
    EVIDENCE_RETRIEVAL_STATUSES,
    EVIDENCE_TYPE_DEFAULT_AUTHORITY,
    EVIDENCE_TYPES,
    FINALIZABLE_FROM_CASE_STATUSES,
    IDENTITY_SIGNAL_TYPES,
    IDENTITY_STATUSES,
    LICENCE_STATUSES,
    PERMISSION_STATUSES,
    PERMISSION_TYPES,
    REPORT_FIELD_PROVENANCE,
    REVERIFICATION_STATUSES,
    STRONG_IDENTITY_STATUSES,
    SYSTEM_TRIGGERED_PERMISSION_STATUSES,
    TERMINAL_VERIFICATION_CASE_STATUSES,
    UPSTREAM_RELATIONSHIP_TYPES,
    UPSTREAM_VERIFICATION_STATUSES,
    VERIFICATION_CASE_STATUSES,
    VERIFICATION_EVENT_TYPES,
    WITHDRAWAL_IMPACT_STATUSES,
    WITHDRAWAL_NOTICE_TYPES,
    authority_rank,
    default_authority_for_evidence_type,
    higher_or_equal_authority,
    is_admin_only_permission_status,
    normalize_spdx_identifier,
)


def test_all_enums_are_nonempty_unique_str_tuples() -> None:
    for values in (
        EVIDENCE_TYPES, EVIDENCE_AUTHORITY_LEVELS, VERIFICATION_CASE_STATUSES,
        IDENTITY_STATUSES, LICENCE_STATUSES, PERMISSION_TYPES, PERMISSION_STATUSES,
        AUTOMATED_PERMISSION_STATUSES, ADMIN_ONLY_PERMISSION_STATUSES,
        SYSTEM_TRIGGERED_PERMISSION_STATUSES, COMMERCIAL_USE_INTENDED_CATEGORIES,
        UPSTREAM_RELATIONSHIP_TYPES, CONFLICT_SEVERITIES, REVERIFICATION_STATUSES,
        WITHDRAWAL_NOTICE_TYPES, REPORT_FIELD_PROVENANCE, EVIDENCE_CONTENT_TYPES,
        CASE_SECTION_STATUSES, EVIDENCE_RETRIEVAL_STATUSES, EVIDENCE_LINK_ENTITY_TYPES,
        EVIDENCE_LINK_ROLES, IDENTITY_SIGNAL_TYPES, UPSTREAM_VERIFICATION_STATUSES,
        CONFLICT_TYPES, CONFLICT_RESOLUTION_STATUSES, VERIFICATION_EVENT_TYPES,
        WITHDRAWAL_IMPACT_STATUSES,
    ):
        assert isinstance(values, tuple)
        assert len(values) > 0
        assert all(isinstance(v, str) for v in values)
        assert len(set(values)) == len(values)


def test_evidence_type_default_authority_keys_are_valid_evidence_types() -> None:
    assert set(EVIDENCE_TYPE_DEFAULT_AUTHORITY) <= set(EVIDENCE_TYPES)
    assert set(EVIDENCE_TYPE_DEFAULT_AUTHORITY.values()) <= set(EVIDENCE_AUTHORITY_LEVELS)


def test_authority_precedence_matches_authority_levels() -> None:
    assert AUTHORITY_PRECEDENCE == EVIDENCE_AUTHORITY_LEVELS
    assert AUTHORITY_PRECEDENCE[0] == "primary"
    assert AUTHORITY_PRECEDENCE[-1] == "manual_unverified"


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ("primary", "manual_unverified", True),
        ("manual_unverified", "primary", False),
        ("secondary", "secondary", True),
        ("official_supporting", "secondary", True),
        ("secondary", "official_supporting", False),
    ],
)
def test_higher_or_equal_authority(a, b, expected) -> None:
    assert higher_or_equal_authority(a, b) is expected


def test_authority_rank_raises_on_unknown_level() -> None:
    with pytest.raises(ValueError):
        authority_rank("not_a_real_level")


def test_default_authority_for_evidence_type_known_and_fallback() -> None:
    assert default_authority_for_evidence_type("licence_file") == "primary"
    assert default_authority_for_evidence_type("dataset_card") == "official_supporting"
    assert default_authority_for_evidence_type("provider_api_metadata") == "provider_declared"
    assert default_authority_for_evidence_type("something_unlisted") == "manual_unverified"


def test_verification_case_status_partitions_are_consistent() -> None:
    active = set(ACTIVE_VERIFICATION_CASE_STATUSES)
    terminal = set(TERMINAL_VERIFICATION_CASE_STATUSES)
    assert active | terminal == set(VERIFICATION_CASE_STATUSES)
    assert active & terminal == set()
    assert set(FINALIZABLE_FROM_CASE_STATUSES) <= active


def test_strong_identity_statuses_require_more_than_title_similarity() -> None:
    # Title-only similarity must never be sufficient to reach a strong
    # identity status -- this is enforced structurally here and again
    # behaviorally against the identity verification service itself.
    assert set(STRONG_IDENTITY_STATUSES) == {"verified"}
    assert "likely_match" not in STRONG_IDENTITY_STATUSES
    assert set(STRONG_IDENTITY_STATUSES) <= set(IDENTITY_STATUSES)


def test_permission_status_three_way_split_is_exhaustive_and_disjoint() -> None:
    groups = (
        set(AUTOMATED_PERMISSION_STATUSES),
        set(ADMIN_ONLY_PERMISSION_STATUSES),
        set(SYSTEM_TRIGGERED_PERMISSION_STATUSES),
    )
    assert groups[0] & groups[1] == set()
    assert groups[0] & groups[2] == set()
    assert groups[1] & groups[2] == set()
    assert groups[0] | groups[1] | groups[2] == set(PERMISSION_STATUSES)
    assert len(PERMISSION_STATUSES) == 10


def test_admin_only_permission_statuses_match_task_specification() -> None:
    assert set(ADMIN_ONLY_PERMISSION_STATUSES) == {
        "approved", "approved_with_conditions", "not_approved", "prohibited",
    }


def test_withdrawn_is_system_triggered_not_admin_only_or_automated() -> None:
    assert "withdrawn" in SYSTEM_TRIGGERED_PERMISSION_STATUSES
    assert "withdrawn" not in AUTOMATED_PERMISSION_STATUSES
    assert "withdrawn" not in ADMIN_ONLY_PERMISSION_STATUSES


def test_not_applicable_is_automated_not_admin_only() -> None:
    assert "not_applicable" in AUTOMATED_PERMISSION_STATUSES
    assert "not_applicable" not in ADMIN_ONLY_PERMISSION_STATUSES


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("approved", True), ("approved_with_conditions", True),
        ("not_approved", True), ("prohibited", True),
        ("unknown", False), ("not_applicable", False), ("likely_allowed", False),
        ("likely_restricted", False), ("needs_legal_review", False), ("withdrawn", False),
    ],
)
def test_is_admin_only_permission_status(status, expected) -> None:
    assert is_admin_only_permission_status(status) is expected


def test_blocking_conflict_severity_is_subset_of_conflict_severities() -> None:
    assert set(BLOCKING_CONFLICT_SEVERITIES) == {"blocking"}
    assert set(BLOCKING_CONFLICT_SEVERITIES) <= set(CONFLICT_SEVERITIES)


@pytest.mark.parametrize(
    ("declared", "expected"),
    [
        ("CC-BY-4.0", "CC-BY-4.0"),
        ("cc-by-4.0", "CC-BY-4.0"),
        ("  CC BY 4.0  ", "CC-BY-4.0"),
        ("MIT License", "MIT"),
        ("Apache 2.0", "Apache-2.0"),
        ("Some Custom Proprietary Terms", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_spdx_identifier_is_exact_match_only(declared, expected) -> None:
    assert normalize_spdx_identifier(declared) == expected


def test_normalize_spdx_identifier_never_fuzzy_matches_partial_substrings() -> None:
    # A string that merely *contains* a known token must not match --
    # exact (whitespace/case-normalized) match only, never substring
    # or fuzzy matching that could misattribute a licence.
    assert normalize_spdx_identifier("MIT-like custom license") is None
    assert normalize_spdx_identifier("based on Apache-2.0 with modifications") is None
