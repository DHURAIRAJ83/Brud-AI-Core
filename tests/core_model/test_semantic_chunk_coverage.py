import pytest

from core_model.semantic_chunk.coverage import (
    plan_boundary_move,
    plan_merge,
    plan_split,
    validate_page_coverage,
)


def test_split_produces_two_contiguous_fragments_with_no_loss():
    text = "First sentence here. Second sentence here."
    plan = plan_split(text, 0, len(text), 21)
    assert plan["first"]["text"] + plan["second"]["text"] == text
    assert plan["first"]["offset_end"] == plan["second"]["offset_start"] == 21


def test_split_rejects_point_outside_chunk_boundaries():
    with pytest.raises(ValueError, match="strictly inside"):
        plan_split("hello world", 0, 5, 10)


def test_split_rejects_empty_fragment():
    with pytest.raises(ValueError, match="empty fragment"):
        plan_split("a    ", 0, 5, 1)


def test_merge_adjacent_chunks_preserves_combined_text():
    first = {"page": 1, "offset_start": 0, "offset_end": 10, "text": "0123456789"}
    second = {"page": 1, "offset_start": 10, "offset_end": 15, "text": "abcde"}
    plan = plan_merge(first, second)
    assert plan["text"] == "0123456789abcde"
    assert plan["start_offset"] == 0
    assert plan["end_offset"] == 15
    assert plan["warnings"] == []


def test_merge_overlapping_chunks_is_rejected():
    first = {"page": 1, "offset_start": 0, "offset_end": 10, "text": "0123456789"}
    second = {"page": 1, "offset_start": 5, "offset_end": 20, "text": "56789abcde"}
    with pytest.raises(ValueError, match="overlap"):
        plan_merge(first, second)


def test_merge_with_a_gap_falls_back_to_concatenation_without_full_text():
    first = {"page": 1, "offset_start": 0, "offset_end": 10, "text": "0123456789"}
    second = {"page": 1, "offset_start": 12, "offset_end": 17, "text": "abcde"}
    plan = plan_merge(first, second)
    assert plan["text"] == "0123456789abcde"


def test_merge_with_a_gap_preserves_the_separator_text_when_full_text_is_given():
    full_text = "0123456789  abcde"  # two-space separator between the chunks
    first = {"page": 1, "offset_start": 0, "offset_end": 10, "text": "0123456789"}
    second = {"page": 1, "offset_start": 12, "offset_end": 17, "text": "abcde"}
    plan = plan_merge(first, second, full_text=full_text)
    assert plan["text"] == "0123456789  abcde"


def test_cross_page_merge_is_allowed_but_warned():
    first = {"page": 1, "offset_start": 0, "offset_end": 10, "text": "0123456789"}
    second = {"page": 2, "offset_start": 10, "offset_end": 15, "text": "abcde"}
    plan = plan_merge(first, second)
    assert "cross_page_merge" in plan["warnings"]


def test_boundary_move_shrinks_chunk_and_grows_neighbor_with_no_gap_or_overlap():
    full_text = "0123456789abcdefghij"
    chunk = {"offset_start": 0, "offset_end": 10}
    neighbor = {"offset_start": 10, "offset_end": 20}
    result = plan_boundary_move(chunk, neighbor, edge="end", new_offset=8, full_text=full_text)
    assert result["chunk"]["text"] == "01234567"
    assert result["neighbor"]["text"] == "89abcdefghij"
    assert result["chunk"]["text"] + result["neighbor"]["text"] == full_text


def test_boundary_move_rejects_a_move_beyond_the_neighbors_own_end():
    full_text = "0123456789abcdefghij"
    chunk = {"offset_start": 0, "offset_end": 10}
    neighbor = {"offset_start": 10, "offset_end": 20}
    with pytest.raises(ValueError, match="overlap"):
        plan_boundary_move(chunk, neighbor, edge="end", new_offset=25, full_text=full_text)


def test_validate_page_coverage_detects_no_issues_for_a_clean_partition():
    page_text = "0123456789"
    segments = [
        {"offset_start": 0, "offset_end": 5},
        {"offset_start": 5, "offset_end": 10},
    ]
    result = validate_page_coverage(page_text, segments)
    assert result["issues"] == []
    assert result["assigned_ratio"] == 1.0
    assert result["coverage_computable"] is True


def test_validate_page_coverage_detects_a_gap():
    page_text = "0123456789"
    segments = [{"offset_start": 0, "offset_end": 4}, {"offset_start": 6, "offset_end": 10}]
    result = validate_page_coverage(page_text, segments)
    codes = {issue["code"] for issue in result["issues"]}
    assert "SOURCE_TEXT_LOSS" in codes
    assert result["gap_count"] >= 1


def test_validate_page_coverage_detects_an_overlap():
    page_text = "0123456789"
    segments = [{"offset_start": 0, "offset_end": 6}, {"offset_start": 4, "offset_end": 10}]
    result = validate_page_coverage(page_text, segments)
    codes = {issue["code"] for issue in result["issues"]}
    assert "SOURCE_TEXT_OVERLAP" in codes


def test_validate_page_coverage_excludes_non_offset_segments_from_ratio():
    page_text = "0123456789"
    segments = [
        {"offset_start": 0, "offset_end": 10},
        {"page": 1},  # region/line locator only -- not offset-computable
    ]
    result = validate_page_coverage(page_text, segments)
    assert result["non_offset_chunk_count"] == 1
    assert result["coverage_computable"] is False
