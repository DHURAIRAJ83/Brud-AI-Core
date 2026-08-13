"""MB-14: pure-module unit tests for
core_model/mini_brain/vision_intelligence/.

Every module is honest about the absence of a vision model,
object-detection model, or captioning model anywhere in this
codebase -- these tests verify that absence is reported, never
fabricated, and that every deterministic computation (geometry,
thresholds, aggregation) is correct against real, hand-constructed
fixtures.
"""

from core_model.mini_brain.vision_intelligence.annotation_recorder import record_annotation
from core_model.mini_brain.vision_intelligence.bounding_box_planner import plan_bounding_boxes
from core_model.mini_brain.vision_intelligence.caption_generator import generate_captions
from core_model.mini_brain.vision_intelligence.image_extraction_report import summarize_extraction
from core_model.mini_brain.vision_intelligence.image_quality_analyzer import analyze_image_quality
from core_model.mini_brain.vision_intelligence.knowledge_graph_builder import build_knowledge_graph
from core_model.mini_brain.vision_intelligence.ocr_cross_validator import cross_validate_ocr
from core_model.mini_brain.vision_intelligence.vision_dataset_draft_builder import (
    build_vision_dataset_draft,
)
from core_model.mini_brain.vision_intelligence.vision_question_generator import generate_questions
from core_model.mini_brain.vision_intelligence.vision_quality_engine import score_vision_quality
from core_model.mini_brain.vision_intelligence.vision_report_generator import generate_vision_report
from core_model.mini_brain.vision_intelligence.vision_understanding import detect_objects

# -- image_extraction_report -------------------------------------------------------------


def test_summarize_extraction_counts_pages_formats_and_bytes() -> None:
    images = [
        {"page_number": 1, "image_format": "png", "file_size_bytes": 100, "checksum_sha256": "a", "public_id": "i1"},
        {"page_number": 1, "image_format": "jpeg", "file_size_bytes": 200, "checksum_sha256": "b", "public_id": "i2"},
        {"page_number": 2, "image_format": "png", "file_size_bytes": 150, "checksum_sha256": "a", "public_id": "i3"},
    ]
    result = summarize_extraction(images=images)
    assert result["total_images"] == 3
    assert result["images_per_page"] == {"1": 2, "2": 1}
    assert result["format_counts"] == {"png": 2, "jpeg": 1}
    assert result["total_bytes"] == 450
    assert result["never_modified_original"] is True


def test_summarize_extraction_detects_exact_duplicate_by_checksum() -> None:
    images = [
        {"page_number": 1, "image_format": "png", "file_size_bytes": 100, "checksum_sha256": "same", "public_id": "i1"},
        {"page_number": 3, "image_format": "png", "file_size_bytes": 100, "checksum_sha256": "same", "public_id": "i2"},
    ]
    result = summarize_extraction(images=images)
    assert result["exact_duplicate_count"] == 2
    assert result["exact_duplicate_groups"] == [["i1", "i2"]]


def test_summarize_extraction_empty_list() -> None:
    result = summarize_extraction(images=[])
    assert result["total_images"] == 0
    assert result["exact_duplicate_groups"] == []


# -- image_quality_analyzer --------------------------------------------------------------


def test_analyze_image_quality_clean_image_scores_100() -> None:
    result = analyze_image_quality(
        width=1000, height=800, brightness_mean=120.0, contrast_std=50.0, blur_variance=500.0,
        exif_rotation=0,
    )
    assert result["quality_score"] == 100.0
    assert result["issues"] == []
    assert result["not_detected"] == ["crop", "noise"]


def test_analyze_image_quality_flags_low_resolution_dark_and_blurry() -> None:
    result = analyze_image_quality(
        width=50, height=50, brightness_mean=10.0, contrast_std=5.0, blur_variance=10.0,
        exif_rotation=90,
    )
    assert "low_resolution" in result["issues"]
    assert "too_dark" in result["issues"]
    assert "low_contrast" in result["issues"]
    assert "possibly_blurry" in result["issues"]
    assert "rotated_90_degrees" in result["issues"]
    assert result["quality_score"] == 25.0  # 100 - 5 issues * 15, floored at 0


def test_analyze_image_quality_flags_too_bright() -> None:
    result = analyze_image_quality(
        width=1000, height=800, brightness_mean=250.0, contrast_std=50.0, blur_variance=500.0,
        exif_rotation=None,
    )
    assert "too_bright" in result["issues"]


# -- vision_understanding -----------------------------------------------------------------


def test_detect_objects_never_fabricates_a_real_detection() -> None:
    result = detect_objects(image_public_ids=["img1", "img2"])
    assert result["vision_model_available"] is False
    assert result["object_count"] == 0
    assert result["images_pending_review"] == 2
    assert all(o["label"] == "Unknown Object" and o["confidence"] == 0.0 for o in result["detected_objects"])
    assert all(o["admin_review_required"] is True for o in result["detected_objects"])


def test_detect_objects_empty_input() -> None:
    result = detect_objects(image_public_ids=[])
    assert result["detected_objects"] == []
    assert result["images_pending_review"] == 0


# -- ocr_cross_validator -------------------------------------------------------------------


def test_cross_validate_ocr_missing_when_no_ocr_text() -> None:
    result = cross_validate_ocr(ocr_text="", dataset_text="something", language_report_status=None)
    assert result["status"] == "missing"
    assert result["match_ratio"] is None
    assert result["auto_corrected"] is False


def test_cross_validate_ocr_missing_when_no_dataset_text() -> None:
    result = cross_validate_ocr(ocr_text="some real text", dataset_text=None, language_report_status=None)
    assert result["status"] == "missing"


def test_cross_validate_ocr_match_for_identical_text() -> None:
    text = "the quick brown fox jumps over the lazy dog"
    result = cross_validate_ocr(ocr_text=text, dataset_text=text, language_report_status="valid")
    assert result["status"] == "match"
    assert result["match_ratio"] == 1.0
    assert result["language_intelligence_status"] == "valid"


def test_cross_validate_ocr_conflict_for_disjoint_text() -> None:
    result = cross_validate_ocr(
        ocr_text="completely different words here", dataset_text="totally unrelated content entirely",
        language_report_status=None,
    )
    assert result["status"] == "conflict"


def test_cross_validate_ocr_never_auto_corrects() -> None:
    result = cross_validate_ocr(ocr_text="a b c", dataset_text="a b d", language_report_status=None)
    assert result["auto_corrected"] is False


# -- caption_generator --------------------------------------------------------------------


def test_generate_captions_without_admin_caption_is_unavailable() -> None:
    result = generate_captions()
    assert result["source"] == "unavailable"
    assert result["dataset_caption"] is None
    assert result["verified"] is False


def test_generate_captions_with_admin_caption_populates_all_fields() -> None:
    result = generate_captions(admin_caption="A mountain scene with a river.")
    assert result["source"] == "admin_supplied"
    assert result["dataset_caption"] == "A mountain scene with a river."
    assert result["detailed_caption"] == "A mountain scene with a river."
    assert result["verified"] is False


def test_generate_captions_short_caption_is_truncated() -> None:
    long_caption = "x" * 200
    result = generate_captions(admin_caption=long_caption)
    assert len(result["short_caption"]) == 80
    assert result["detailed_caption"] == long_caption


# -- bounding_box_planner ------------------------------------------------------------------


def test_plan_bounding_boxes_only_includes_admin_drawn_boxes() -> None:
    objects = [
        {"public_id": "o1", "label": "Tree", "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}, "confidence": 1.0, "source": "admin_added"},
        {"public_id": "o2", "label": "Unknown Object", "bounding_box": None, "confidence": 0.0, "source": "auto_unknown"},
    ]
    result = plan_bounding_boxes(objects=objects)
    assert result["box_count"] == 1
    assert result["unboxed_object_count"] == 1
    assert result["auto_accepted"] is False
    assert result["planned_boxes"][0]["object_public_id"] == "o1"


def test_plan_bounding_boxes_empty_input() -> None:
    result = plan_bounding_boxes(objects=[])
    assert result["box_count"] == 0
    assert result["unboxed_object_count"] == 0


# -- annotation_recorder -------------------------------------------------------------------


def test_record_annotation_rejects_unknown_action() -> None:
    result = record_annotation(action="teleport", current_object=None, payload={})
    assert result["allowed"] is False
    assert "unknown action" in result["reason"]


def test_record_annotation_requires_existing_object_for_rename() -> None:
    result = record_annotation(action="rename", current_object=None, payload={"label": "Tree"})
    assert result["allowed"] is False
    assert "requires an existing object" in result["reason"]


def test_record_annotation_add_requires_non_empty_label() -> None:
    result = record_annotation(action="add", current_object=None, payload={"label": "  "})
    assert result["allowed"] is False


def test_record_annotation_redraw_box_requires_bounding_box() -> None:
    current = {"public_id": "o1", "label": "Tree"}
    result = record_annotation(action="redraw_box", current_object=current, payload={})
    assert result["allowed"] is False
    assert "requires a bounding_box" in result["reason"]


def test_record_annotation_allows_valid_rename() -> None:
    current = {"public_id": "o1", "label": "Unknown Object"}
    result = record_annotation(action="rename", current_object=current, payload={"label": "Mountain"})
    assert result["allowed"] is True
    assert result["action"] == "rename"


def test_record_annotation_allows_delete_of_existing_object() -> None:
    current = {"public_id": "o1", "label": "Mountain"}
    result = record_annotation(action="delete", current_object=current, payload={})
    assert result["allowed"] is True


# -- knowledge_graph_builder ----------------------------------------------------------------


def test_build_knowledge_graph_detects_containment() -> None:
    objects = [
        {"public_id": "mountain", "label": "Mountain", "confidence": 0.0, "bounding_box": {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}},
        {"public_id": "river", "label": "River", "confidence": 1.0, "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.3, "height": 0.3}},
    ]
    result = build_knowledge_graph(objects=objects)
    assert result["node_count"] == 2
    assert result["edge_count"] == 1
    edge = result["edges"][0]
    assert edge["from"] == "mountain"
    assert edge["to"] == "river"
    assert edge["relationship"] == "contains"


def test_build_knowledge_graph_ignores_objects_without_boxes() -> None:
    objects = [
        {"public_id": "o1", "label": "Unknown Object", "confidence": 0.0, "bounding_box": None},
        {"public_id": "o2", "label": "Unknown Object", "confidence": 0.0, "bounding_box": None},
    ]
    result = build_knowledge_graph(objects=objects)
    assert result["edge_count"] == 0
    assert result["unboxed_node_count"] == 2


def test_build_knowledge_graph_no_relationship_for_distant_boxes() -> None:
    objects = [
        {"public_id": "a", "label": "A", "confidence": 1.0, "bounding_box": {"x": 0.0, "y": 0.0, "width": 0.05, "height": 0.05}},
        {"public_id": "b", "label": "B", "confidence": 1.0, "bounding_box": {"x": 0.9, "y": 0.9, "width": 0.05, "height": 0.05}},
    ]
    result = build_knowledge_graph(objects=objects)
    assert result["edge_count"] == 0


# -- vision_question_generator --------------------------------------------------------------


def test_generate_questions_includes_what_is_shown_when_caption_present() -> None:
    result = generate_questions(objects=[], caption="A river scene.")
    assert any(q["question"] == "What is shown in this image?" for q in result["questions"])
    assert result["verified"] is False


def test_generate_questions_includes_location_question_per_object() -> None:
    objects = [{"label": "Tree", "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1}}]
    result = generate_questions(objects=objects, caption=None)
    assert any("Where is the Tree located?" == q["question"] for q in result["questions"])


def test_generate_questions_includes_how_many_for_repeated_labels() -> None:
    objects = [
        {"label": "Tree", "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.1, "height": 0.1}},
        {"label": "Tree", "bounding_box": {"x": 0.3, "y": 0.3, "width": 0.1, "height": 0.1}},
    ]
    result = generate_questions(objects=objects, caption=None)
    assert any("How many" in q["question"] and "Tree" in q["question"] for q in result["questions"])


def test_generate_questions_empty_input_yields_no_questions() -> None:
    result = generate_questions(objects=[], caption=None)
    assert result["question_count"] == 0


# -- vision_dataset_draft_builder ------------------------------------------------------------


def test_build_vision_dataset_draft_is_never_verified() -> None:
    result = build_vision_dataset_draft(
        image_metadata=[], ocr_text="", caption_report={}, bounding_box_report={}, objects=[],
        qa_report={}, knowledge_graph_report={},
    )
    assert result["verified"] is False
    assert result["status"] == "needs_admin_review"


# -- vision_quality_engine -----------------------------------------------------------------


def test_score_vision_quality_full_marks_scenario() -> None:
    result = score_vision_quality(
        average_image_quality_score=100.0, average_ocr_match_ratio=1.0, caption_available=True,
        total_object_count=2, admin_verified_object_count=2, qa_question_count=10, kg_edge_count=5,
    )
    assert result["components"]["image_quality"] == 100.0
    assert result["components"]["ocr_match"] == 100.0
    assert result["components"]["object_accuracy"] == 100.0
    assert result["overall_vision_score"] == 100.0


def test_score_vision_quality_zero_objects_does_not_divide_by_zero() -> None:
    result = score_vision_quality(
        average_image_quality_score=0.0, average_ocr_match_ratio=None, caption_available=False,
        total_object_count=0, admin_verified_object_count=0, qa_question_count=0, kg_edge_count=0,
    )
    assert result["components"]["object_accuracy"] == 0.0
    assert result["overall_vision_score"] == 0.0


def test_score_vision_quality_discloses_proxy_nature() -> None:
    result = score_vision_quality(
        average_image_quality_score=50.0, average_ocr_match_ratio=0.5, caption_available=False,
        total_object_count=1, admin_verified_object_count=0, qa_question_count=1, kg_edge_count=0,
    )
    assert "no vision model exists" in result["disclosure"]


# -- vision_report_generator ---------------------------------------------------------------


def test_generate_vision_report_ready_when_score_high() -> None:
    quality_score_report = {"overall_vision_score": 90.0, "components": {}}
    result = generate_vision_report(
        session_public_id="s1", document_source_public_id="d1", quality_score_report=quality_score_report,
        unknown_object_count=0, ocr_status_counts={"match": 1},
    )
    assert result["status"] == "Ready"
    assert result["recommendation"] == "approve"
    assert result["risk"] == "Low"
    assert result["problems"] == []


def test_generate_vision_report_not_ready_when_score_low() -> None:
    quality_score_report = {"overall_vision_score": 10.0, "components": {}}
    result = generate_vision_report(
        session_public_id="s1", document_source_public_id="d1", quality_score_report=quality_score_report,
        unknown_object_count=3, ocr_status_counts={"conflict": 2, "missing": 1},
    )
    assert result["status"] == "Not Ready"
    assert result["recommendation"] == "request_fix"
    assert result["risk"] == "High"
    assert len(result["problems"]) == 3


def test_generate_vision_report_needs_review_band() -> None:
    quality_score_report = {"overall_vision_score": 50.0, "components": {}}
    result = generate_vision_report(
        session_public_id="s1", document_source_public_id="d1", quality_score_report=quality_score_report,
        unknown_object_count=0, ocr_status_counts={},
    )
    assert result["status"] == "Needs Review"
    assert result["risk"] == "Medium"
