import pytest

from core_model.data_providers import (
    ACCESS_MODES,
    AUTHENTICATION_TYPES,
    CAPABILITY_TYPES,
    CAPABILITY_TYPES_DISABLED_IN_PHASE_9,
    CONNECTION_TEST_RESULTS,
    CREDENTIAL_STATUSES,
    CREDENTIAL_TYPES,
    DOMAIN_TYPES,
    DOMAIN_VERIFICATION_STATUSES,
    EVIDENCE_REQUIRED_TRUST_STATUSES,
    INACTIVE_LIFECYCLE_STATUSES,
    LIFECYCLE_STATUSES,
    PROVIDER_EVENT_TYPES,
    PROVIDER_TYPES,
    TRUST_STATUSES,
    is_usable_for_discovery,
)


def test_credential_types_excludes_none() -> None:
    assert "none" not in CREDENTIAL_TYPES
    assert set(CREDENTIAL_TYPES) == set(AUTHENTICATION_TYPES) - {"none"}


def test_capability_types_disabled_in_phase_9_are_a_subset() -> None:
    assert set(CAPABILITY_TYPES_DISABLED_IN_PHASE_9) <= set(CAPABILITY_TYPES)
    assert "download_full" in CAPABILITY_TYPES_DISABLED_IN_PHASE_9
    assert "upload" in CAPABILITY_TYPES_DISABLED_IN_PHASE_9
    assert "read_metadata" not in CAPABILITY_TYPES_DISABLED_IN_PHASE_9


def test_evidence_required_trust_statuses_are_a_subset() -> None:
    assert set(EVIDENCE_REQUIRED_TRUST_STATUSES) <= set(TRUST_STATUSES)
    assert "unverified" not in EVIDENCE_REQUIRED_TRUST_STATUSES
    assert "blocked" not in EVIDENCE_REQUIRED_TRUST_STATUSES


def test_inactive_lifecycle_statuses_are_a_subset() -> None:
    assert set(INACTIVE_LIFECYCLE_STATUSES) <= set(LIFECYCLE_STATUSES)
    assert "enabled" not in INACTIVE_LIFECYCLE_STATUSES
    assert "draft" in INACTIVE_LIFECYCLE_STATUSES


@pytest.mark.parametrize(
    ("lifecycle_status", "enabled", "expected"),
    [
        ("enabled", True, True),
        ("enabled", False, False),
        ("draft", True, False),
        ("disabled", True, False),
        ("restricted", True, False),
        ("blocked", True, False),
        ("archived", True, False),
        ("connection_tested", True, True),
        ("needs_review", True, True),
        ("approved", True, True),
        ("not_a_real_status", True, False),
    ],
)
def test_is_usable_for_discovery(lifecycle_status, enabled, expected) -> None:
    assert is_usable_for_discovery(lifecycle_status=lifecycle_status, enabled=enabled) is expected


def test_all_enums_are_nonempty_tuples_of_str() -> None:
    for values in (
        PROVIDER_TYPES, ACCESS_MODES, AUTHENTICATION_TYPES, TRUST_STATUSES,
        LIFECYCLE_STATUSES, DOMAIN_TYPES, DOMAIN_VERIFICATION_STATUSES,
        CAPABILITY_TYPES, CREDENTIAL_TYPES, CREDENTIAL_STATUSES,
        CONNECTION_TEST_RESULTS, PROVIDER_EVENT_TYPES,
    ):
        assert isinstance(values, tuple)
        assert len(values) > 0
        assert all(isinstance(v, str) for v in values)
        assert len(set(values)) == len(values)
