"""MB-16: pure-module unit tests for
core_model/mini_brain/multimodal_dataset_generator/.

Covers all supported data-type combinations the task spec names: text
only, image only, text+image (multimodal), and the honest-absence
paths when no upstream session is linked.
"""

from core_model.mini_brain.multimodal_dataset_generator.conversation_builder import build_conversations
from core_model.mini_brain.multimodal_dataset_generator.dataset_draft_assembler import (
    assemble_dataset_draft,
)
from core_model.mini_brain.multimodal_dataset_generator.dataset_memory_builder import (
    build_dataset_memory,
)
from core_model.mini_brain.multimodal_dataset_generator.dataset_report_generator import (
    generate_dataset_report,
)
from core_model.mini_brain.multimodal_dataset_generator.duplicate_report_builder import (
    build_duplicate_report,
)
from core_model.mini_brain.multimodal_dataset_generator.image_section_builder import (
    build_image_section,
)
from core_model.mini_brain.multimodal_dataset_generator.instruction_builder import build_instructions
from core_model.mini_brain.multimodal_dataset_generator.knowledge_graph_reference import (
    reference_knowledge_graph,
)
from core_model.mini_brain.multimodal_dataset_generator.metadata_merger import merge_metadata
from core_model.mini_brain.multimodal_dataset_generator.quality_engine import score_dataset_quality
from core_model.mini_brain.multimodal_dataset_generator.source_collector import collect_sources
from core_model.mini_brain.multimodal_dataset_generator.text_section_builder import build_text_section

# -- source_collector ---------------------------------------------------------------------


def test_collect_sources_document_always_available() -> None:
    result = collect_sources(
        document_source_public_id="doc1", dataset_source_public_id=None,
        language_session_public_id=None, vision_session_public_id=None,
        vision_model_session_public_id=None,
    )
    assert result["sources"]["document"]["available"] is True
    assert result["available_source_count"] == 1
    assert result["text_capable"] is True
    assert result["image_capable"] is False


def test_collect_sources_all_linked() -> None:
    result = collect_sources(
        document_source_public_id="doc1", dataset_source_public_id="ds1",
        language_session_public_id="ls1", vision_session_public_id="vs1",
        vision_model_session_public_id="vms1",
    )
    assert result["available_source_count"] == 5
    assert result["image_capable"] is True


# -- text_section_builder ----------------------------------------------------------------


def test_build_text_section_without_language_session() -> None:
    result = build_text_section(ocr_text="hello world", language_session=None)
    assert result["language_session_linked"] is False
    assert result["language_quality_score"] is None
    assert result["ocr_char_count"] == 11


def test_build_text_section_reuses_mb13_reports() -> None:
    language_session = {
        "language_scan_report": {"dominant_language": "tamil"},
        "unicode_report": {"unicode_score": 95.0},
        "quality_score_report": {"overall_language_quality": 88.0},
        "language_report": {"status": "Ready"},
    }
    result = build_text_section(ocr_text="தமிழ்", language_session=language_session)
    assert result["language_session_linked"] is True
    assert result["dominant_language"] == "tamil"
    assert result["language_quality_score"] == 88.0


def test_build_text_section_empty_ocr_text() -> None:
    result = build_text_section(ocr_text="", language_session=None)
    assert result["ocr_char_count"] == 0


# -- image_section_builder ----------------------------------------------------------------


def test_build_image_section_without_vision_session() -> None:
    result = build_image_section(
        vision_session=None, images=[], objects=[], vision_model_session=None, vm_predictions=[],
        vm_corrections=[],
    )
    assert result["vision_session_linked"] is False
    assert result["image_count"] == 0


def test_build_image_section_reuses_mb14_data() -> None:
    vision_session = {
        "caption_report": {"long_description": "A scene."},
        "knowledge_graph_report": {"nodes": [], "edges": []},
        "quality_report": {"average_quality_score": 90.0},
    }
    images = [{"public_id": "img1", "page_number": 1, "image_format": "png", "width_pixels": 100, "height_pixels": 100, "checksum_sha256": "a"}]
    objects = [{"label": "Tree", "confidence": 1.0, "bounding_box": {"x": 0}, "source": "admin_added"}]
    result = build_image_section(
        vision_session=vision_session, images=images, objects=objects, vision_model_session=None,
        vm_predictions=[], vm_corrections=[],
    )
    assert result["vision_session_linked"] is True
    assert result["image_count"] == 1
    assert result["caption"]["long_description"] == "A scene."
    assert result["vision_model_session_linked"] is False


def test_build_image_section_with_vision_model_session_prefers_its_caption() -> None:
    vision_session = {"caption_report": {}, "knowledge_graph_report": {"edges": []}, "quality_report": {}}
    vision_model_session = {
        "caption_report": {"long_description": "A richer real caption."},
        "scene_report": {"scene": "forest"},
        "knowledge_graph_report": {"nodes": [], "edges": [{"from": "a", "to": "b", "relationship": "near"}]},
    }
    result = build_image_section(
        vision_session=vision_session, images=[], objects=[], vision_model_session=vision_model_session,
        vm_predictions=[{"label": "X", "confidence": 0.5, "bounding_box": None, "source": "ai_predicted"}],
        vm_corrections=[{"action": "reject", "wrong_label": "X", "correct_label": None}],
    )
    assert result["caption"]["long_description"] == "A richer real caption."
    assert result["scene"]["scene"] == "forest"
    assert len(result["relationships"]["edges"]) == 1
    assert len(result["admin_corrections"]) == 1


# -- knowledge_graph_reference -------------------------------------------------------------


def test_reference_knowledge_graph_never_regenerates() -> None:
    graph = {"nodes": [{"id": "a"}], "edges": [{"from": "a", "to": "b", "relationship": "near"}]}
    result = reference_knowledge_graph(graph=graph)
    assert result["node_count"] == 1
    assert result["edge_count"] == 1
    assert result["regenerated"] is False


def test_reference_knowledge_graph_handles_empty_graph() -> None:
    result = reference_knowledge_graph(graph={})
    assert result["node_count"] == 0
    assert result["edge_count"] == 0


# -- metadata_merger ----------------------------------------------------------------------


def test_merge_metadata_detects_multimodal() -> None:
    source_report = {"sources": {}}
    text_section = {"ocr_char_count": 10}
    image_section = {"image_count": 1}
    kg = {"node_count": 0, "edge_count": 0}
    result = merge_metadata(source_report=source_report, text_section=text_section, image_section=image_section, knowledge_graph=kg)
    assert result["is_multimodal"] is True


def test_merge_metadata_text_only_is_not_multimodal() -> None:
    result = merge_metadata(
        source_report={"sources": {}}, text_section={"ocr_char_count": 10}, image_section={"image_count": 0},
        knowledge_graph={},
    )
    assert result["is_multimodal"] is False


# -- conversation_builder -------------------------------------------------------------------


def test_build_conversations_from_qa_and_ocr() -> None:
    merged = {
        "images": {"images": [{"public_id": "img1"}], "objects": [], "caption": {}},
        "text": {"ocr_text": "hello"}, "knowledge_graph": {"node_count": 0, "edge_count": 0},
    }
    qa_items = [{"question": "What is shown?", "answer_hint": "A thing."}]
    result = build_conversations(merged_metadata=merged, qa_items=qa_items, document_source_public_id="doc1")
    assert result["conversation_count"] == 2
    assert all(c["verified"] is False for c in result["conversations"])


def test_build_conversations_no_qa_no_text() -> None:
    merged = {"images": {"images": [], "objects": [], "caption": {}}, "text": {"ocr_text": ""}, "knowledge_graph": {"node_count": 0, "edge_count": 0}}
    result = build_conversations(merged_metadata=merged, qa_items=[], document_source_public_id="doc1")
    assert result["conversation_count"] == 0


# -- instruction_builder --------------------------------------------------------------------


def test_build_instructions_covers_text_caption_and_objects() -> None:
    merged = {
        "text": {"ocr_text": "hello world"},
        "images": {"caption": {"long_description": "A scene."}, "objects": [{"label": "Tree"}, {"label": "Rock"}]},
    }
    result = build_instructions(merged_metadata=merged)
    assert result["instruction_count"] == 3


def test_build_instructions_empty_metadata() -> None:
    merged = {"text": {"ocr_text": ""}, "images": {"caption": {}, "objects": []}}
    result = build_instructions(merged_metadata=merged)
    assert result["instruction_count"] == 0


# -- dataset_draft_assembler -----------------------------------------------------------------


def test_assemble_dataset_draft_covers_every_record_type() -> None:
    conversations = [{
        "user": "What is shown?", "assistant": "A thing", "evidence": ["MB-14 QA generation (reused, never regenerated)"],
    }]
    instructions = [{"instruction": "Describe.", "input": None, "output": "A thing"}]
    merged = {
        "images": {
            "images": [{"public_id": "img1"}],
            "objects": [{"label": "Tree", "confidence": 1.0, "bounding_box": {"x": 0}}],
            "caption": {"long_description": "A scene."}, "scene": None,
        },
        "knowledge_graph": {"edges": [{"from": "a", "to": "b", "relationship": "near"}]},
    }
    result = assemble_dataset_draft(conversations=conversations, instructions=instructions, merged_metadata=merged)
    assert set(result["counts_by_type"]) == {"conversation", "qa", "instruction", "training", "caption", "vision", "grounding", "reasoning"}
    assert result["verified"] is False
    assert result["status"] == "needs_admin_review"


def test_assemble_dataset_draft_empty_input() -> None:
    merged = {"images": {"images": [], "objects": [], "caption": {}, "scene": None}, "knowledge_graph": {"edges": []}}
    result = assemble_dataset_draft(conversations=[], instructions=[], merged_metadata=merged)
    assert result["record_count"] == 0


# -- quality_engine -------------------------------------------------------------------------


def test_score_dataset_quality_full_marks() -> None:
    result = score_dataset_quality(
        language_quality_score=100.0, vision_quality_score=100.0, ocr_match_score=100.0,
        object_quality_score=100.0, caption_quality_score=100.0, knowledge_graph_edge_count=5,
        conversation_count=1, instruction_count=1,
    )
    assert result["overall_dataset_quality"] == 100.0


def test_score_dataset_quality_missing_sources_score_zero_not_fabricated() -> None:
    result = score_dataset_quality(
        language_quality_score=None, vision_quality_score=None, ocr_match_score=None,
        object_quality_score=None, caption_quality_score=None, knowledge_graph_edge_count=0,
        conversation_count=0, instruction_count=0,
    )
    assert result["components"]["language_quality"] == 0.0
    assert result["overall_dataset_quality"] == 0.0


# -- duplicate_report_builder ------------------------------------------------------------------


def test_build_duplicate_report_summarizes_groups() -> None:
    result = build_duplicate_report(
        exact_groups=[["a", "b"]], normalized_groups=[["c", "d"], ["e", "f"]], image_checksum_groups=[["g", "h"]],
    )
    assert result["exact_duplicate_count"] == 2
    assert result["normalized_duplicate_count"] == 4
    assert result["image_duplicate_count"] == 2
    assert "ExternalDatasetDuplicateService" in result["reused_service"]


def test_build_duplicate_report_empty() -> None:
    result = build_duplicate_report(exact_groups=[], normalized_groups=[], image_checksum_groups=[])
    assert result["exact_duplicate_count"] == 0


# -- dataset_report_generator ----------------------------------------------------------------


def test_generate_dataset_report_ready() -> None:
    quality_report = {"overall_dataset_quality": 90.0, "components": {}}
    duplicate_report = {"exact_duplicate_count": 0, "normalized_duplicate_count": 0}
    result = generate_dataset_report(
        multimodal_dataset_session_public_id="mm1", document_source_public_id="doc1",
        quality_report=quality_report, record_count=10, duplicate_report=duplicate_report,
    )
    assert result["status"] == "Ready"
    assert result["recommendation"] == "approve"


def test_generate_dataset_report_flags_duplicates_and_empty_draft() -> None:
    quality_report = {"overall_dataset_quality": 10.0, "components": {}}
    duplicate_report = {"exact_duplicate_count": 2, "normalized_duplicate_count": 0}
    result = generate_dataset_report(
        multimodal_dataset_session_public_id="mm1", document_source_public_id="doc1",
        quality_report=quality_report, record_count=0, duplicate_report=duplicate_report,
    )
    assert result["status"] == "Not Ready"
    assert len(result["problems"]) == 2


# -- dataset_memory_builder ------------------------------------------------------------------


def test_build_dataset_memory_assembles_all_fields() -> None:
    result = build_dataset_memory(
        generated_at="2026-01-01 00:00:00", source_document_public_id="doc1", source_dataset_public_id=None,
        source_language_session_public_id="ls1", source_vision_session_public_id="vs1",
        source_vision_model_session_public_id=None, total_records=5, correction_history=[{"a": 1}],
        learning_memory=[{"b": 2}], provider_key="onnx_cpu",
    )
    assert result["total_records"] == 5
    assert result["provider_information"] == {"provider_key": "onnx_cpu"}


def test_build_dataset_memory_no_provider() -> None:
    result = build_dataset_memory(
        generated_at="2026-01-01 00:00:00", source_document_public_id="doc1", source_dataset_public_id=None,
        source_language_session_public_id=None, source_vision_session_public_id=None,
        source_vision_model_session_public_id=None, total_records=0, correction_history=[],
        learning_memory=[], provider_key=None,
    )
    assert result["provider_information"] == {}
