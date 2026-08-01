import pytest

from core_model.data_discovery import (
    ALL_SCORING_DIMENSIONS,
    COMMERCIAL_REQUIREMENTS,
    FIELD_SOURCES,
    FULLY_SUPPORTED_MODALITIES,
    LANGUAGES,
    METADATA_ONLY_MODALITIES,
    MODALITIES,
    PROVIDER_RUN_STATUSES,
    SEARCH_SESSION_STATUSES,
    TASKS,
    USE_APPROVAL_STATUSES,
    is_provider_searchable,
    requirement_language_from_category,
)


def test_fully_supported_and_metadata_only_modalities_partition_modalities() -> None:
    assert set(FULLY_SUPPORTED_MODALITIES) | set(METADATA_ONLY_MODALITIES) == set(MODALITIES)
    assert set(FULLY_SUPPORTED_MODALITIES) & set(METADATA_ONLY_MODALITIES) == set()
    assert FULLY_SUPPORTED_MODALITIES == ("text",)


def test_use_approval_statuses_never_include_approved() -> None:
    assert "approved" not in USE_APPROVAL_STATUSES
    assert set(USE_APPROVAL_STATUSES) == {"not_approved", "unknown"}


@pytest.mark.parametrize(
    ("enabled", "lifecycle_status", "has_search", "has_manual", "expected"),
    [
        (True, "enabled", True, False, True),
        (True, "enabled", False, True, True),
        (True, "enabled", False, False, False),
        (False, "enabled", True, False, False),
        (True, "draft", True, False, False),
        (True, "disabled", True, False, False),
        (True, "restricted", True, False, False),
        (True, "blocked", True, False, False),
        (True, "archived", True, False, False),
        (True, "connection_tested", True, False, True),
    ],
)
def test_is_provider_searchable(
    enabled, lifecycle_status, has_search, has_manual, expected
) -> None:
    assert (
        is_provider_searchable(
            enabled=enabled,
            lifecycle_status=lifecycle_status,
            has_search_capability=has_search,
            has_manual_discovery_capability=has_manual,
        )
        is expected
    )


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("ta", "tamil"), ("en", "english"), ("tgl", "tanglish"), ("mixed", "mixed"),
        ("unknown", "unknown"), ("xx", "unknown"),
    ],
)
def test_requirement_language_from_category(category, expected) -> None:
    assert requirement_language_from_category(category) == expected


def test_all_enums_are_nonempty_unique_str_tuples() -> None:
    for values in (
        MODALITIES, LANGUAGES, TASKS, COMMERCIAL_REQUIREMENTS, FIELD_SOURCES,
        SEARCH_SESSION_STATUSES, PROVIDER_RUN_STATUSES, ALL_SCORING_DIMENSIONS,
    ):
        assert isinstance(values, tuple)
        assert len(values) > 0
        assert all(isinstance(v, str) for v in values)
        assert len(set(values)) == len(values)
