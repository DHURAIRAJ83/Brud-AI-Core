from core_model.semantic_chunk.quality import assess_chunk_quality


def _chunk(**overrides):
    base = {"chunk_type": "paragraph", "language": "ta"}
    base.update(overrides)
    return base


def _revision(**overrides):
    base = {
        "text": "இது ஒரு முழுமையான வாக்கியம்.",
        "document_page_id": 1,
        "page_number": 1,
        "origin": "source_grounded",
    }
    base.update(overrides)
    return base


def test_clean_chunk_with_lineage_and_approved_page_scores_well():
    result = assess_chunk_quality(chunk=_chunk(), revision=_revision(), page_approved=True)
    assert result["blocking_issues"] == []
    assert result["recommended_status"] == "approved"


def test_missing_lineage_is_a_blocking_issue():
    result = assess_chunk_quality(
        chunk=_chunk(),
        revision=_revision(document_page_id=None, page_number=None),
        page_approved=True,
    )
    assert "MISSING_SOURCE_LINEAGE" in result["blocking_issues"]
    assert result["recommended_status"] == "draft"


def test_unapproved_page_source_is_a_blocking_issue():
    result = assess_chunk_quality(chunk=_chunk(), revision=_revision(), page_approved=False)
    assert "UNAPPROVED_PAGE_SOURCE" in result["blocking_issues"]


def test_empty_chunk_is_a_blocking_issue():
    result = assess_chunk_quality(
        chunk=_chunk(), revision=_revision(text="   "), page_approved=True
    )
    assert "EMPTY_CHUNK" in result["blocking_issues"]


def test_broken_sentence_boundary_blocks_prose_types():
    result = assess_chunk_quality(
        chunk=_chunk(chunk_type="paragraph"),
        revision=_revision(text="this has no terminal punctuation"),
        page_approved=True,
    )
    assert "BROKEN_SENTENCE_BOUNDARY" in result["blocking_issues"]


def test_missing_terminal_punctuation_is_only_a_warning_for_non_prose_types():
    result = assess_chunk_quality(
        chunk=_chunk(chunk_type="heading"),
        revision=_revision(text="Chapter One"),
        page_approved=True,
    )
    assert "BROKEN_SENTENCE_BOUNDARY" not in result["blocking_issues"]
    assert "no_terminal_punctuation" in result["warnings"]


def test_source_text_loss_and_overlap_are_blocking():
    result = assess_chunk_quality(
        chunk=_chunk(),
        revision=_revision(),
        page_approved=True,
        coverage_issue_codes=["SOURCE_TEXT_LOSS"],
    )
    assert "SOURCE_TEXT_LOSS" in result["blocking_issues"]


def test_unreviewed_human_synthesis_is_blocking():
    result = assess_chunk_quality(
        chunk=_chunk(chunk_type="answer"),
        revision=_revision(text="This is a synthesized answer.", origin="human_synthesized"),
        page_approved=True,
    )
    assert "UNREVIEWED_ADMIN_SYNTHESIS" in result["blocking_issues"]


def test_reviewed_human_synthesis_is_not_blocking():
    result = assess_chunk_quality(
        chunk=_chunk(chunk_type="answer"),
        revision=_revision(
            text="This is a synthesized answer.", origin="human_synthesized", reviewed=True
        ),
        page_approved=True,
    )
    assert "UNREVIEWED_ADMIN_SYNTHESIS" not in result["blocking_issues"]


def test_rights_block_is_blocking_regardless_of_other_scores():
    result = assess_chunk_quality(
        chunk=_chunk(),
        revision=_revision(),
        page_approved=True,
        usage_decision={"allowed": False},
    )
    assert "RIGHTS_BLOCK_TARGET_USE" in result["blocking_issues"]
    assert result["recommended_status"] != "approved"


def test_unresolved_table_structure_blocks_table_chunks():
    result = assess_chunk_quality(
        chunk=_chunk(chunk_type="table"),
        revision=_revision(text="raw table text", metadata={"table_structure": "raw"}),
        page_approved=True,
    )
    assert "UNRESOLVED_TABLE_STRUCTURE" in result["blocking_issues"]


def test_high_average_score_cannot_hide_a_blocking_issue():
    # Every other dimension is maximal; only source_traceability is zero
    # because lineage is missing -- overall average could still exceed
    # the threshold, but the blocking issue must win regardless.
    result = assess_chunk_quality(
        chunk=_chunk(),
        revision=_revision(document_page_id=None, page_number=None),
        page_approved=True,
    )
    assert result["overall_score"] < 100
    assert result["recommended_status"] != "approved"
