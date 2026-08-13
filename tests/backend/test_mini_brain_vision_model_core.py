"""MB-15: pure-module unit tests for
core_model/mini_brain/vision_model_integration/, plus the vision
inference backend adapters (backend.services.vision_inference_backend)
-- deterministic, no database required for either.
"""

import pytest

from backend.services.mini_brain_inference_backend import BackendUnavailableError
from backend.services.vision_inference_backend import (
    BACKEND_FACTORIES,
    LlavaGgufVisionBackend,
    OnnxVisionBackend,
    OpenVinoVisionBackend,
    backend_for_provider,
)
from core_model.mini_brain.vision_model_integration.admin_review_recorder import record_review
from core_model.mini_brain.vision_model_integration.caption_report_builder import build_caption_report
from core_model.mini_brain.vision_model_integration.correction_memory_summarizer import (
    summarize_corrections,
)
from core_model.mini_brain.vision_model_integration.detection_report import summarize_detections
from core_model.mini_brain.vision_model_integration.image_load_report import summarize_loaded_images
from core_model.mini_brain.vision_model_integration.learning_memory_builder import build_learning_memory
from core_model.mini_brain.vision_model_integration.ocr_cross_validator import cross_validate_vision
from core_model.mini_brain.vision_model_integration.provider_selector import select_provider
from core_model.mini_brain.vision_model_integration.relationship_detector import detect_relationships
from core_model.mini_brain.vision_model_integration.scene_report_builder import build_scene_report
from core_model.mini_brain.vision_model_integration.vision_model_quality_engine import (
    score_vision_model_quality,
)
from core_model.mini_brain.vision_model_integration.vision_model_report_generator import (
    generate_vision_model_report,
)

# -- vision_inference_backend --------------------------------------------------------------


def test_onnx_backend_honestly_unavailable() -> None:
    backend = OnnxVisionBackend()
    assert backend.is_available() is False
    with pytest.raises(BackendUnavailableError):
        backend.load("/nonexistent/model.onnx")


def test_openvino_backend_honestly_unavailable() -> None:
    backend = OpenVinoVisionBackend()
    assert backend.is_available() is False
    with pytest.raises(BackendUnavailableError):
        backend.load("/nonexistent/model.xml")


def test_llava_backend_library_available_but_no_model_configured() -> None:
    backend = LlavaGgufVisionBackend()
    assert backend.is_available() is True
    with pytest.raises(BackendUnavailableError, match="does not exist"):
        backend.load("/nonexistent/vision.gguf", mmproj_path="/nonexistent/mmproj.gguf")


def test_llava_backend_methods_raise_before_load() -> None:
    backend = LlavaGgufVisionBackend()
    with pytest.raises(BackendUnavailableError):
        backend.detect_objects(b"fake-bytes")
    with pytest.raises(BackendUnavailableError):
        backend.classify_scene(b"fake-bytes")
    with pytest.raises(BackendUnavailableError):
        backend.generate_caption(b"fake-bytes")


def test_backend_for_provider_returns_correct_type() -> None:
    assert isinstance(backend_for_provider("llava_gguf_cpu"), LlavaGgufVisionBackend)
    assert isinstance(backend_for_provider("onnx_cpu"), OnnxVisionBackend)
    assert isinstance(backend_for_provider("openvino_cpu"), OpenVinoVisionBackend)


def test_backend_for_provider_rejects_unregistered_key() -> None:
    with pytest.raises(BackendUnavailableError):
        backend_for_provider("cuda_future")


def test_backend_factories_cover_every_real_provider() -> None:
    assert set(BACKEND_FACTORIES) == {"onnx_cpu", "openvino_cpu", "llava_gguf_cpu"}


# -- image_load_report ------------------------------------------------------------------


def test_summarize_loaded_images() -> None:
    images = [{"page_number": 1, "file_size_bytes": 100}, {"page_number": 2, "file_size_bytes": 200}]
    result = summarize_loaded_images(images=images)
    assert result["image_count"] == 2
    assert result["pages"] == [1, 2]
    assert result["total_bytes"] == 300


# -- provider_selector -------------------------------------------------------------------


def test_select_provider_active_and_implemented() -> None:
    registry = [{"provider_key": "onnx_cpu", "status": "active", "display_name": "ONNX", "backend_type": "onnx", "hardware_target": "cpu"}]
    result = select_provider(provider_key="onnx_cpu", registry_rows=registry, implemented_provider_keys={"onnx_cpu"})
    assert result["selected"] is True


def test_select_provider_rejects_unregistered() -> None:
    result = select_provider(provider_key="unknown", registry_rows=[], implemented_provider_keys=set())
    assert result["selected"] is False
    assert "not a registered provider" in result["reason"]


def test_select_provider_rejects_inactive() -> None:
    registry = [{"provider_key": "onnx_cpu", "status": "inactive"}]
    result = select_provider(provider_key="onnx_cpu", registry_rows=registry, implemented_provider_keys={"onnx_cpu"})
    assert result["selected"] is False
    assert "disabled" in result["reason"]


def test_select_provider_rejects_unimplemented_future_placeholder() -> None:
    registry = [{"provider_key": "cuda_future", "status": "active"}]
    result = select_provider(provider_key="cuda_future", registry_rows=registry, implemented_provider_keys={"onnx_cpu"})
    assert result["selected"] is False
    assert "no backend implementation" in result["reason"]


# -- detection_report --------------------------------------------------------------------


def test_summarize_detections_provider_unavailable() -> None:
    result = summarize_detections(provider_available=False, predictions=[])
    assert result["object_count"] == 0
    assert result["provider_available"] is False


def test_summarize_detections_real_predictions() -> None:
    predictions = [
        {"label": "Tree", "confidence": 0.8, "bounding_box": None},
        {"label": "Tree", "confidence": 0.6, "bounding_box": {"x": 0}},
    ]
    result = summarize_detections(provider_available=True, predictions=predictions)
    assert result["object_count"] == 2
    assert result["label_counts"] == {"Tree": 2}
    assert result["average_confidence"] == 0.7
    assert result["bounding_box_count"] == 1


# -- scene_report_builder ----------------------------------------------------------------


def test_build_scene_report_unavailable() -> None:
    result = build_scene_report(provider_available=False, scene=None, confidence=None)
    assert result["scene"] is None


def test_build_scene_report_real() -> None:
    result = build_scene_report(provider_available=True, scene="forest", confidence=0.5)
    assert result["scene"] == "forest"
    assert result["confidence"] == 0.5


# -- caption_report_builder --------------------------------------------------------------


def test_build_caption_report_unavailable() -> None:
    result = build_caption_report(provider_available=False, caption=None, confidence=None)
    assert result["long_description"] is None
    assert result["verified"] is False


def test_build_caption_report_truncates_short_and_medium() -> None:
    caption = "x" * 300
    result = build_caption_report(provider_available=True, caption=caption, confidence=0.4)
    assert len(result["short_caption"]) == 80
    assert len(result["medium_caption"]) == 240
    assert result["long_description"] == caption
    assert result["verified"] is False


# -- relationship_detector (reuses MB-14 knowledge_graph_builder) -------------------------


def test_detect_relationships_reuses_real_geometry() -> None:
    objects = [
        {"public_id": "a", "label": "Mountain", "confidence": 1.0, "bounding_box": {"x": 0, "y": 0, "width": 1, "height": 1}},
        {"public_id": "b", "label": "River", "confidence": 1.0, "bounding_box": {"x": 0.1, "y": 0.1, "width": 0.2, "height": 0.2}},
    ]
    result = detect_relationships(objects=objects)
    assert result["edge_count"] == 1
    assert result["edges"][0]["relationship"] == "contains"


def test_detect_relationships_empty_input() -> None:
    result = detect_relationships(objects=[])
    assert result["node_count"] == 0
    assert result["edge_count"] == 0


# -- ocr_cross_validator ------------------------------------------------------------------


def test_cross_validate_vision_match_when_labels_found_in_text() -> None:
    result = cross_validate_vision(
        ocr_text="a mountain and a river scene", dataset_text=None, vision_labels=["mountain", "river"],
        document_dataset_status="match", language_report_status=None,
    )
    assert result["status"] == "match"
    assert result["missing_labels"] == []


def test_cross_validate_vision_flags_missing_labels() -> None:
    result = cross_validate_vision(
        ocr_text="a mountain scene", dataset_text=None, vision_labels=["mountain", "spaceship"],
        document_dataset_status="match", language_report_status=None,
    )
    assert result["status"] == "mismatch"
    assert "spaceship" in result["missing_labels"]


def test_cross_validate_vision_flags_duplicate_labels() -> None:
    result = cross_validate_vision(
        ocr_text="tree tree tree forest", dataset_text=None, vision_labels=["tree", "tree", "tree"],
        document_dataset_status="match", language_report_status=None,
    )
    assert "tree" in result["duplicate_labels"]


def test_cross_validate_vision_conflict_propagates() -> None:
    result = cross_validate_vision(
        ocr_text="", dataset_text=None, vision_labels=[], document_dataset_status="conflict",
        language_report_status=None,
    )
    assert result["status"] == "conflict"


def test_cross_validate_vision_never_auto_corrects() -> None:
    result = cross_validate_vision(
        ocr_text="x", dataset_text=None, vision_labels=[], document_dataset_status=None,
        language_report_status=None,
    )
    assert result["auto_corrected"] is False


# -- admin_review_recorder ----------------------------------------------------------------


def test_record_review_rejects_unknown_action() -> None:
    result = record_review(action="teleport", current_prediction=None, payload={})
    assert result["allowed"] is False


def test_record_review_requires_existing_prediction_for_approve() -> None:
    result = record_review(action="approve", current_prediction=None, payload={})
    assert result["allowed"] is False


def test_record_review_allows_add_without_existing_prediction() -> None:
    result = record_review(action="add", current_prediction=None, payload={"label": "Tree", "image_public_id": "img1"})
    assert result["allowed"] is True
    assert result["is_correction"] is False


def test_record_review_split_requires_at_least_two_new_predictions() -> None:
    result = record_review(
        action="split", current_prediction={"public_id": "p1"},
        payload={"new_predictions": [{"label": "A", "bounding_box": {"x": 0}}]},
    )
    assert result["allowed"] is False


def test_record_review_split_allows_valid_entries() -> None:
    result = record_review(
        action="split", current_prediction={"public_id": "p1"},
        payload={"new_predictions": [
            {"label": "A", "bounding_box": {"x": 0}}, {"label": "B", "bounding_box": {"x": 1}},
        ]},
    )
    assert result["allowed"] is True
    assert result["is_correction"] is True


def test_record_review_merge_requires_two_sources() -> None:
    result = record_review(
        action="merge", current_prediction=None,
        payload={"source_prediction_public_ids": ["p1"], "label": "X", "bounding_box": {"x": 0}},
    )
    assert result["allowed"] is False


def test_record_review_move_box_requires_bounding_box() -> None:
    result = record_review(action="move_box", current_prediction={"public_id": "p1"}, payload={})
    assert result["allowed"] is False


def test_record_review_approve_is_not_a_correction() -> None:
    result = record_review(action="approve", current_prediction={"public_id": "p1"}, payload={})
    assert result["allowed"] is True
    assert result["is_correction"] is False


def test_record_review_reject_is_a_correction() -> None:
    result = record_review(action="reject", current_prediction={"public_id": "p1"}, payload={})
    assert result["allowed"] is True
    assert result["is_correction"] is True


# -- correction_memory_summarizer ----------------------------------------------------------


def test_summarize_corrections_counts_actions_and_pairs() -> None:
    corrections = [
        {"action": "rename", "wrong_label": "Tree", "correct_label": "Bush"},
        {"action": "rename", "wrong_label": "Tree", "correct_label": "Bush"},
        {"action": "reject", "wrong_label": "Rock", "correct_label": None},
    ]
    result = summarize_corrections(corrections=corrections)
    assert result["total_corrections"] == 3
    assert result["action_counts"] == {"rename": 2, "reject": 1}
    assert result["most_frequent_wrong_to_correct_labels"][0]["pair"] == "Tree -> Bush"
    assert result["most_frequent_wrong_to_correct_labels"][0]["count"] == 2


def test_summarize_corrections_empty() -> None:
    result = summarize_corrections(corrections=[])
    assert result["total_corrections"] == 0


# -- learning_memory_builder ---------------------------------------------------------------


def test_build_learning_memory_counts_by_source_and_status() -> None:
    predictions = [
        {"review_status": "approved", "source": "ai_predicted"},
        {"review_status": "approved", "source": "admin_corrected"},
        {"review_status": "rejected", "source": "ai_predicted"},
        {"review_status": "deleted", "source": "ai_predicted"},
    ]
    result = build_learning_memory(predictions=predictions)
    assert result["total_predictions"] == 4
    assert result["approved_count"] == 1
    assert result["corrected_count"] == 1
    assert result["rejected_count"] == 2
    assert result["correction_rate"] == 0.25


def test_build_learning_memory_zero_predictions_no_divide_error() -> None:
    result = build_learning_memory(predictions=[])
    assert result["total_predictions"] == 0
    assert result["correction_rate"] is None


# -- vision_model_quality_engine ------------------------------------------------------------


def test_score_vision_model_quality_full_marks() -> None:
    result = score_vision_model_quality(
        total_predictions=2, approved_unchanged_count=2, caption_available=True, scene_available=True,
        bounding_box_count=2, relationship_edge_count=5, correction_rate=0.0, average_confidence=1.0,
    )
    assert result["overall_vision_model_score"] == 100.0


def test_score_vision_model_quality_zero_predictions_no_divide_error() -> None:
    result = score_vision_model_quality(
        total_predictions=0, approved_unchanged_count=0, caption_available=False, scene_available=False,
        bounding_box_count=0, relationship_edge_count=0, correction_rate=None, average_confidence=None,
    )
    assert result["components"]["detection_accuracy"] == 0.0
    assert result["components"]["correction_rate_score"] == 100.0


def test_score_vision_model_quality_high_correction_rate_lowers_score() -> None:
    low_corrections = score_vision_model_quality(
        total_predictions=10, approved_unchanged_count=10, caption_available=True, scene_available=True,
        bounding_box_count=0, relationship_edge_count=0, correction_rate=0.0, average_confidence=0.5,
    )
    high_corrections = score_vision_model_quality(
        total_predictions=10, approved_unchanged_count=10, caption_available=True, scene_available=True,
        bounding_box_count=0, relationship_edge_count=0, correction_rate=0.9, average_confidence=0.5,
    )
    assert high_corrections["components"]["correction_rate_score"] < low_corrections["components"]["correction_rate_score"]


# -- vision_model_report_generator -----------------------------------------------------------


def test_generate_vision_model_report_ready() -> None:
    quality_report = {"overall_vision_model_score": 90.0, "components": {}}
    result = generate_vision_model_report(
        vision_model_session_public_id="vms1", vision_session_public_id="vs1",
        quality_score_report=quality_report, approved_count=5, rejected_count=0, corrected_count=0,
        missing_labels=[], conflicts=[],
    )
    assert result["status"] == "Ready"
    assert result["recommendation"] == "approve"
    assert result["risk"] == "Low"


def test_generate_vision_model_report_not_ready_with_problems() -> None:
    quality_report = {"overall_vision_model_score": 10.0, "components": {}}
    result = generate_vision_model_report(
        vision_model_session_public_id="vms1", vision_session_public_id="vs1",
        quality_score_report=quality_report, approved_count=0, rejected_count=3, corrected_count=1,
        missing_labels=["spaceship"], conflicts=["conflict"],
    )
    assert result["status"] == "Not Ready"
    assert result["recommendation"] == "request_fix"
    assert len(result["problems"]) == 3
