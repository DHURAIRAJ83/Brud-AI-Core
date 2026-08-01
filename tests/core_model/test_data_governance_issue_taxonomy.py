from __future__ import annotations

import pytest

from core_model.data_governance.issue_taxonomy import (
    DATASET_QUALITY_ISSUE_CATEGORIES,
    MANUAL_DATA_ISSUE_CATEGORIES,
    SEMANTIC_CHUNK_ISSUE_CATEGORIES,
    categorize_issue_code,
)
from core_model.data_governance.review import ISSUE_CATEGORIES


def test_every_mapped_category_is_a_real_governance_category():
    for mapping in (
        DATASET_QUALITY_ISSUE_CATEGORIES,
        MANUAL_DATA_ISSUE_CATEGORIES,
        SEMANTIC_CHUNK_ISSUE_CATEGORIES,
    ):
        for category in mapping.values():
            assert category in ISSUE_CATEGORIES


def test_categorize_known_codes_from_each_source_system():
    assert categorize_issue_code("dataset_quality", "duplicate_existing") == "exact_duplicate"
    assert categorize_issue_code("manual_data", "HIGH_RISK_UNVERIFIED") == "high_risk_unverified"
    assert categorize_issue_code("semantic_chunk", "SOURCE_TEXT_LOSS") == "chunk_gap"
    assert categorize_issue_code("semantic_chunk", "SOURCE_TEXT_OVERLAP") == "chunk_overlap"


def test_unknown_source_system_raises():
    with pytest.raises(ValueError):
        categorize_issue_code("not_a_real_system", "duplicate_existing")


def test_unmapped_issue_code_raises_rather_than_guessing():
    with pytest.raises(ValueError):
        categorize_issue_code("dataset_quality", "never_seen_this_code")
