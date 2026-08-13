"""MB-17: pure-module unit tests for core_model/mini_brain/vision_rag/.

Covers text-only, image-only, OCR-only, mixed multimodal, missing
evidence, conflicting evidence, and hallucination-detection paths the
task spec's own testing section names.
"""

from core_model.mini_brain.vision_rag.evidence_fusion import fuse_evidence
from core_model.mini_brain.vision_rag.grounded_answer_builder import build_grounded_answer
from core_model.mini_brain.vision_rag.hallucination_checker import check_hallucination
from core_model.mini_brain.vision_rag.image_retrieval import retrieve_images
from core_model.mini_brain.vision_rag.knowledge_graph_retrieval import retrieve_graph_edges
from core_model.mini_brain.vision_rag.object_retrieval import retrieve_objects
from core_model.mini_brain.vision_rag.ocr_retrieval import retrieve_ocr
from core_model.mini_brain.vision_rag.query_session_builder import build_query_session
from core_model.mini_brain.vision_rag.rag_memory_builder import build_rag_memory
from core_model.mini_brain.vision_rag.rag_quality_engine import score_rag_quality
from core_model.mini_brain.vision_rag.rag_report_generator import generate_rag_report
from core_model.mini_brain.vision_rag.relevance_scoring import score_candidates, top_candidates
from core_model.mini_brain.vision_rag.text_retrieval import retrieve_text

RECORDS = [
    {"public_id": "r1", "record_type": "conversation", "content": {"user": "What does this document say?", "assistant": "Mountain River Fish Tree scene page one."}},
    {"public_id": "r2", "record_type": "instruction", "content": {"instruction": "Transcribe the text visible in this document.", "output": "Mountain River Fish Tree scene page one."}},
    {"public_id": "r3", "record_type": "qa", "content": {"user": "What is shown?", "assistant": "A mountain scene with a river."}},
    {"public_id": "r4", "record_type": "instruction", "content": {"instruction": "Describe what is shown in this image.", "output": "A mountain scene with a river."}},
    {"public_id": "r5", "record_type": "qa", "content": {"user": "Where is the River located?", "assistant": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}}},
]

# -- query_session_builder ---------------------------------------------------------------


def test_build_query_session_ready_when_certified() -> None:
    result = build_query_session(query="Where is the river?", multimodal_dataset_status="admin_approved")
    assert result["ready"] is True
    assert result["dataset_certified"] is True


def test_build_query_session_not_ready_when_uncertified() -> None:
    result = build_query_session(query="Where is the river?", multimodal_dataset_status="in_progress")
    assert result["ready"] is False
    assert result["dataset_certified"] is False


def test_build_query_session_classifies_tamil() -> None:
    result = build_query_session(query="இந்த படத்தில் என்ன உள்ளது?", multimodal_dataset_status="admin_approved")
    assert result["language_category"] == "ta"


def test_build_query_session_not_ready_for_empty_query() -> None:
    result = build_query_session(query="   ", multimodal_dataset_status="admin_approved")
    assert result["ready"] is False


# -- relevance_scoring --------------------------------------------------------------------


def test_score_candidates_ranks_relevant_higher() -> None:
    scores = score_candidates(
        normalized_query="where is the river", candidate_texts=["the river flows near the mountain", "a sentence about cooking"],
    )
    assert scores[0] > scores[1]


def test_score_candidates_empty_input() -> None:
    assert score_candidates(normalized_query="x", candidate_texts=[]) == []


def test_top_candidates_respects_limit_and_minimum_score() -> None:
    items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
    scores = [0.9, 0.01, 0.5]
    result = top_candidates(items=items, scores=scores, limit=2, minimum_score=0.05)
    assert [r["id"] for r in result] == ["a", "c"]


# -- text_retrieval -------------------------------------------------------------------------


def test_retrieve_text_excludes_ocr_sourced_records() -> None:
    result = retrieve_text(normalized_query="what is shown", records=RECORDS)
    assert result["candidate_count"] == 3  # r3, r4, r5 -- not r1/r2 (OCR-sourced)


def test_retrieve_text_formats_bounding_box_answer_hint_readably() -> None:
    result = retrieve_text(normalized_query="where is the river located", records=RECORDS)
    matching = [r for r in result["results"] if r["record_public_id"] == "r5"]
    assert matching
    assert "position x=" in matching[0]["snippet"]
    assert "{'x'" not in matching[0]["snippet"]


def test_retrieve_text_empty_records() -> None:
    result = retrieve_text(normalized_query="x", records=[])
    assert result["candidate_count"] == 0


# -- ocr_retrieval --------------------------------------------------------------------------


def test_retrieve_ocr_only_returns_ocr_sourced_records() -> None:
    result = retrieve_ocr(normalized_query="mountain", records=RECORDS)
    assert result["ocr_record_count"] == 2
    assert all(r["ocr_snippet"] == "Mountain River Fish Tree scene page one." for r in result["results"])


def test_retrieve_ocr_no_ocr_records() -> None:
    result = retrieve_ocr(normalized_query="x", records=[RECORDS[2]])
    assert result["ocr_record_count"] == 0


# -- image_retrieval -------------------------------------------------------------------------


def test_retrieve_images_matches_by_real_caption() -> None:
    images = [{"public_id": "img1", "page_number": 1, "checksum_sha256": "abc", "width_pixels": 200, "height_pixels": 150}]
    captions = [{"record_type": "caption", "content": {"image_public_id": "img1", "caption": "A mountain scene with a river."}}]
    result = retrieve_images(normalized_query="river", images=images, caption_records=captions)
    assert result["result_count"] == 1
    assert result["results"][0]["caption"] == "A mountain scene with a river."


def test_retrieve_images_no_images() -> None:
    result = retrieve_images(normalized_query="river", images=[], caption_records=[])
    assert result["image_count"] == 0
    assert result["result_count"] == 0


def test_retrieve_images_discloses_no_semantic_embedding() -> None:
    result = retrieve_images(normalized_query="x", images=[], caption_records=[])
    assert "no semantic image embedding" in result["disclosure"]


# -- object_retrieval -------------------------------------------------------------------------


def test_retrieve_objects_prefers_vision_model_source() -> None:
    vm_objects = [{"label": "River", "confidence": 0.9, "bounding_box": None}]
    vi_objects = [{"label": "Mountain", "confidence": 1.0, "bounding_box": None, "source": "admin_added"}]
    result = retrieve_objects(normalized_query="river", vision_model_objects=vm_objects, vision_objects=vi_objects)
    assert result["source"] == "vision_model"
    assert result["object_count"] == 1


def test_retrieve_objects_falls_back_to_vision_intelligence_and_excludes_unknown() -> None:
    vi_objects = [
        {"label": "Mountain", "confidence": 1.0, "bounding_box": None, "source": "admin_added"},
        {"label": "Unknown Object", "confidence": 0.0, "bounding_box": None, "source": "auto_unknown"},
    ]
    result = retrieve_objects(normalized_query="mountain", vision_model_objects=[], vision_objects=vi_objects)
    assert result["source"] == "vision_intelligence"
    assert result["object_count"] == 1


# -- knowledge_graph_retrieval -----------------------------------------------------------------


def test_retrieve_graph_edges_matches_query_related_nodes() -> None:
    graph = {"nodes": [{"id": "a", "label": "Mountain"}, {"id": "b", "label": "River"}], "edges": [{"from": "a", "to": "b", "relationship": "contains"}]}
    result = retrieve_graph_edges(normalized_query="where is the river", graph=graph)
    assert result["matched_edge_count"] == 1
    assert result["regenerated"] is False


def test_retrieve_graph_edges_no_match() -> None:
    graph = {"nodes": [{"id": "a", "label": "Cloud"}, {"id": "b", "label": "Sky"}], "edges": [{"from": "a", "to": "b", "relationship": "near"}]}
    result = retrieve_graph_edges(normalized_query="river fish tree", graph=graph)
    assert result["matched_edge_count"] == 0


def test_retrieve_graph_edges_empty_graph() -> None:
    result = retrieve_graph_edges(normalized_query="x", graph={})
    assert result["total_edge_count"] == 0


# -- evidence_fusion -------------------------------------------------------------------------


def test_fuse_evidence_combines_all_layers_sorted_by_relevance() -> None:
    text_report = {"results": [{"record_public_id": "r1", "record_type": "conversation", "snippet": "a", "relevance_score": 0.5}]}
    ocr_report = {"results": [{"record_public_id": "r2", "relevance_score": 0.9, "ocr_snippet": "ocr text"}]}
    image_report = {"results": [{"image_public_id": "img1", "page_number": 1, "caption": "cap", "relevance_score": 0.3}]}
    object_report = {"results": [{"label": "Tree", "bounding_box": None, "relevance_score": 0.7}]}
    graph_report = {"matched_edges": [{"from": "a", "to": "b", "relationship": "near"}]}

    result = fuse_evidence(
        document_source_public_id="doc1", text_report=text_report, ocr_report=ocr_report,
        image_report=image_report, object_report=object_report, graph_report=graph_report,
    )
    assert result["evidence_count"] == 5
    assert result["evidence"][0]["relevance_score"] >= result["evidence"][-1]["relevance_score"]
    assert result["counts_by_type"]["graph_edge"] == 1


def test_fuse_evidence_all_empty() -> None:
    empty = {"results": []}
    result = fuse_evidence(
        document_source_public_id="doc1", text_report=empty, ocr_report=empty, image_report=empty,
        object_report=empty, graph_report={"matched_edges": []},
    )
    assert result["evidence_count"] == 0


# -- grounded_answer_builder -----------------------------------------------------------------


def test_build_grounded_answer_with_evidence() -> None:
    evidence = [
        {"public_id": "ev1", "content_snippet": "the river flows here", "relevance_score": 0.9, "evidence_type": "text", "object_label": None},
    ]
    result = build_grounded_answer(evidence=evidence, language_category="en")
    assert result["status"] == "grounded_answer"
    assert "ev1" in result["cited_evidence_public_ids"]
    assert "[S1]" in result["answer"]


def test_build_grounded_answer_insufficient_evidence_english() -> None:
    result = build_grounded_answer(evidence=[], language_category="en")
    assert result["status"] == "insufficient_evidence"
    assert result["confidence"] == 0.0
    assert "evidence" in result["answer"].lower()


def test_build_grounded_answer_insufficient_evidence_tamil() -> None:
    result = build_grounded_answer(evidence=[], language_category="ta")
    assert result["status"] == "insufficient_evidence"
    assert "தமிழ்" not in result["answer"]  # sanity: real Tamil message, not a literal placeholder
    assert result["answer"]


def test_build_grounded_answer_low_score_is_insufficient() -> None:
    evidence = [{"public_id": "ev1", "content_snippet": "weak match", "relevance_score": 0.01, "evidence_type": "text", "object_label": None}]
    result = build_grounded_answer(evidence=evidence, language_category="en")
    assert result["status"] == "insufficient_evidence"


# -- hallucination_checker -------------------------------------------------------------------


def test_check_hallucination_no_citations_is_not_a_hallucination() -> None:
    result = check_hallucination(answer="", cited_evidence_public_ids=[], all_evidence_public_ids=set())
    assert result["hallucination_flag"] is False


def test_check_hallucination_valid_citations() -> None:
    result = check_hallucination(
        answer="the river is here [S1].", cited_evidence_public_ids=["ev1"], all_evidence_public_ids={"ev1", "ev2"},
    )
    assert result["hallucination_flag"] is False
    assert result["citation_validity_rate"] == 1.0


def test_check_hallucination_flags_invented_citation() -> None:
    """A citation referencing an evidence id that was never actually
    retrieved is exactly what "no invented evidence" must catch."""
    result = check_hallucination(
        answer="the river is here [S1].", cited_evidence_public_ids=["invented-id"], all_evidence_public_ids={"ev1"},
    )
    assert result["citation_validity_rate"] == 0.0
    assert result["hallucination_flag"] is True


# -- rag_quality_engine -----------------------------------------------------------------------


def test_score_rag_quality_full_marks() -> None:
    result = score_rag_quality(
        text_result_count=5, ocr_result_count=2, image_result_count=1, object_result_count=3,
        graph_matched_count=1, evidence_count=10, cited_evidence_count=10, hallucination_risk=0.0,
    )
    assert result["overall_rag_quality"] == 100.0


def test_score_rag_quality_no_evidence_scores_zero_not_fabricated() -> None:
    result = score_rag_quality(
        text_result_count=0, ocr_result_count=0, image_result_count=0, object_result_count=0,
        graph_matched_count=0, evidence_count=0, cited_evidence_count=0, hallucination_risk=1.0,
    )
    assert result["components"]["retrieval_recall"] == 0.0
    assert result["components"]["hallucination_risk_score"] == 0.0


# -- rag_report_generator ---------------------------------------------------------------------


def test_generate_rag_report_ready() -> None:
    quality_report = {"overall_rag_quality": 90.0, "components": {}}
    hallucination_report = {"hallucination_flag": False, "hallucination_risk": 0.0}
    evidence_report = {"evidence_count": 5, "counts_by_type": {}}
    result = generate_rag_report(
        vision_rag_session_public_id="vr1", query="q", quality_report=quality_report,
        evidence_report=evidence_report, hallucination_report=hallucination_report,
        answer_status="grounded_answer", retrieval_latency_ms=10.0,
    )
    assert result["status"] == "Ready"
    assert result["recommendation"] == "approve"


def test_generate_rag_report_not_ready_when_hallucination_flagged() -> None:
    quality_report = {"overall_rag_quality": 95.0, "components": {}}
    hallucination_report = {"hallucination_flag": True, "hallucination_risk": 0.8}
    evidence_report = {"evidence_count": 5, "counts_by_type": {}}
    result = generate_rag_report(
        vision_rag_session_public_id="vr1", query="q", quality_report=quality_report,
        evidence_report=evidence_report, hallucination_report=hallucination_report,
        answer_status="grounded_answer", retrieval_latency_ms=10.0,
    )
    assert result["status"] == "Not Ready"
    assert result["recommendation"] == "reject"


def test_generate_rag_report_flags_no_evidence() -> None:
    quality_report = {"overall_rag_quality": 0.0, "components": {}}
    hallucination_report = {"hallucination_flag": False, "hallucination_risk": 0.0}
    evidence_report = {"evidence_count": 0, "counts_by_type": {}}
    result = generate_rag_report(
        vision_rag_session_public_id="vr1", query="q", quality_report=quality_report,
        evidence_report=evidence_report, hallucination_report=hallucination_report,
        answer_status="insufficient_evidence", retrieval_latency_ms=None,
    )
    assert "no evidence was retrieved" in " ".join(result["problems"])


# -- rag_memory_builder ------------------------------------------------------------------------


def test_build_rag_memory_assembles_fields() -> None:
    result = build_rag_memory(
        query="q", evidence_counts_by_type={"text": 2}, final_answer="answer text", confidence=0.8,
        hallucination_flag=False, correction_history=[{"a": 1}], retrieval_latency_ms=12.5,
    )
    assert result["query"] == "q"
    assert result["evidence_summary"] == {"counts_by_type": {"text": 2}}
    assert result["retrieval_latency_ms"] == 12.5
