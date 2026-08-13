"""MB-18: pure-module unit tests for core_model/mini_brain/training_pipeline/.

Covers text-only, multimodal, no-RAG-memory, deterministic-split
reproducibility, and hash-reproducibility paths the task spec's own
testing section names.
"""

import pytest

from core_model.mini_brain.training_pipeline.curriculum_planner import plan_curriculum
from core_model.mini_brain.training_pipeline.dataset_splitter import split_dataset
from core_model.mini_brain.training_pipeline.grounding_quality_analyzer import analyze_grounding_quality
from core_model.mini_brain.training_pipeline.hardware_estimator import estimate_hardware
from core_model.mini_brain.training_pipeline.image_statistics_analyzer import analyze_image_statistics
from core_model.mini_brain.training_pipeline.language_distribution_analyzer import (
    analyze_language_distribution,
)
from core_model.mini_brain.training_pipeline.package_manifest_builder import build_package_manifest
from core_model.mini_brain.training_pipeline.pipeline_report_generator import generate_readiness_report
from core_model.mini_brain.training_pipeline.reproducibility_hasher import (
    build_reproducibility_record,
    verify_reproducibility,
)
from core_model.mini_brain.training_pipeline.source_collector import collect_datasets, collect_rag_memory
from core_model.mini_brain.training_pipeline.tokenizer_coverage_analyzer import analyze_tokenizer_coverage
from core_model.mini_brain.training_pipeline.training_recipe_builder import build_training_recipe

# -- source_collector ------------------------------------------------------------------------


def test_collect_datasets_accepts_only_admin_approved() -> None:
    sessions = [
        {"public_id": "d1", "status": "admin_approved", "record_count": 10},
        {"public_id": "d2", "status": "in_progress", "record_count": 5},
    ]
    report = collect_datasets(dataset_sessions=sessions)
    assert report["accepted_session_public_ids"] == ["d1"]
    assert report["rejected_session_public_ids"] == ["d2"]
    assert report["total_record_count"] == 10
    assert report["ready"] is True


def test_collect_datasets_not_ready_when_none_accepted() -> None:
    report = collect_datasets(dataset_sessions=[{"public_id": "d1", "status": "in_progress", "record_count": 0}])
    assert report["ready"] is False
    assert report["accepted_count"] == 0


def test_collect_rag_memory_accepts_only_approved_and_counts_grounded() -> None:
    entries = [
        {"public_id": "r1", "admin_decision": "approve", "hallucination_flag": False},
        {"public_id": "r2", "admin_decision": "approve", "hallucination_flag": True},
        {"public_id": "r3", "admin_decision": "reject", "hallucination_flag": False},
    ]
    report = collect_rag_memory(rag_memory_entries=entries)
    assert report["accepted_memory_public_ids"] == ["r1", "r2"]
    assert report["rejected_memory_public_ids"] == ["r3"]
    assert report["grounded_count"] == 1


def test_collect_rag_memory_ready_even_when_empty() -> None:
    """A training session with zero approved RAG queries is still a
    valid, text-only-grounding training session -- never a hard
    blocker on its own."""
    report = collect_rag_memory(rag_memory_entries=[])
    assert report["ready"] is True
    assert report["accepted_count"] == 0


# -- dataset_splitter -------------------------------------------------------------------------


def test_split_dataset_is_deterministic_regardless_of_input_order() -> None:
    ids = [f"rec-{i}" for i in range(50)]
    forward = split_dataset(record_public_ids=ids)
    reversed_input = split_dataset(record_public_ids=list(reversed(ids)))
    assert forward["train"] == reversed_input["train"]
    assert forward["validation"] == reversed_input["validation"]
    assert forward["test"] == reversed_input["test"]


def test_split_dataset_unaffected_by_global_random_state() -> None:
    import random

    ids = [f"rec-{i}" for i in range(30)]
    random.seed(999)
    before = split_dataset(record_public_ids=ids, seed=42)
    random.seed(1)
    after = split_dataset(record_public_ids=ids, seed=42)
    assert before == after


def test_split_dataset_different_seed_differs() -> None:
    ids = [f"rec-{i}" for i in range(30)]
    a = split_dataset(record_public_ids=ids, seed=1)
    b = split_dataset(record_public_ids=ids, seed=2)
    assert a["train"] != b["train"]


def test_split_dataset_dedupes_input() -> None:
    result = split_dataset(record_public_ids=["a", "a", "b"])
    assert result["counts"]["total"] == 2


def test_split_dataset_rejects_invalid_ratios() -> None:
    with pytest.raises(ValueError):
        split_dataset(record_public_ids=["a"], train_ratio=0.9, validation_ratio=0.2)


# -- tokenizer_coverage_analyzer --------------------------------------------------------------


def test_analyze_tokenizer_coverage_empty_texts() -> None:
    report = analyze_tokenizer_coverage(texts=[])
    assert report["total_character_count"] == 0
    assert "no text was supplied" in report["disclosure"]


def test_analyze_tokenizer_coverage_latin_text() -> None:
    report = analyze_tokenizer_coverage(texts=["Hello world 123!"])
    assert report["total_character_count"] > 0
    assert report["latin_ratio"] > 0
    assert "latin" in report["script_mix"]
    assert "digits" in report["script_mix"]


def test_analyze_tokenizer_coverage_tamil_text() -> None:
    report = analyze_tokenizer_coverage(texts=["இந்த படத்தில் என்ன உள்ளது?"])
    assert report["tamil_ratio"] > 0
    assert "tamil" in report["script_mix"]


def test_analyze_tokenizer_coverage_skips_empty_strings() -> None:
    report = analyze_tokenizer_coverage(texts=["", "abc"])
    assert report["total_character_count"] == 3


# -- language_distribution_analyzer -----------------------------------------------------------


def test_analyze_language_distribution_no_sessions() -> None:
    report = analyze_language_distribution(language_sessions=[])
    assert report["session_count"] == 0
    assert "honestly unavailable" in report["disclosure"]


def test_analyze_language_distribution_aggregates() -> None:
    sessions = [
        {"language_scan_report": {"dominant_language": "en"}, "quality_score_report": {"overall_language_quality": 80.0}},
        {"language_scan_report": {"dominant_language": "en"}, "quality_score_report": {"overall_language_quality": 90.0}},
        {"language_scan_report": {"dominant_language": "ta"}, "quality_score_report": {}},
    ]
    report = analyze_language_distribution(language_sessions=sessions)
    assert report["dominant_language_counts"] == {"en": 2, "ta": 1}
    assert report["average_language_quality"] == 85.0
    assert report["session_count"] == 3


# -- image_statistics_analyzer -----------------------------------------------------------------


def test_analyze_image_statistics_no_images_is_text_only() -> None:
    report = analyze_image_statistics(images=[])
    assert report["image_count"] == 0
    assert "text-only" in report["disclosure"]


def test_analyze_image_statistics_aggregates_real_metadata() -> None:
    images = [
        {"width_pixels": 200, "height_pixels": 150, "file_size_bytes": 1000, "checksum_sha256": "abc"},
        {"width_pixels": 100, "height_pixels": 100, "file_size_bytes": 500, "checksum_sha256": "abc"},
    ]
    report = analyze_image_statistics(images=images)
    assert report["image_count"] == 2
    assert report["total_pixels"] == 200 * 150 + 100 * 100
    assert report["total_bytes"] == 1500
    assert report["duplicate_checksum_count"] == 1


# -- grounding_quality_analyzer -----------------------------------------------------------------


def test_analyze_grounding_quality_no_memory_is_honestly_unavailable() -> None:
    report = analyze_grounding_quality(rag_memory_entries=[])
    assert report["query_count"] == 0
    assert report["average_confidence"] is None
    assert "honestly unavailable" in report["disclosure"]


def test_analyze_grounding_quality_aggregates_confidence_and_hallucination() -> None:
    entries = [
        {"confidence": 0.9, "hallucination_flag": False},
        {"confidence": 0.5, "hallucination_flag": True},
    ]
    report = analyze_grounding_quality(rag_memory_entries=entries)
    assert report["query_count"] == 2
    assert report["average_confidence"] == 0.7
    assert report["hallucination_flag_count"] == 1
    assert report["hallucination_rate"] == 0.5


# -- curriculum_planner -------------------------------------------------------------------------


def test_plan_curriculum_orders_by_fixed_difficulty() -> None:
    counts = {"qa": 5, "instruction": 10, "reasoning": 2}
    report = plan_curriculum(record_type_counts=counts)
    types_in_order = [stage["record_type"] for stage in report["stages"]]
    assert types_in_order == ["instruction", "qa", "reasoning"]
    assert report["total_records"] == 17


def test_plan_curriculum_handles_unranked_types() -> None:
    report = plan_curriculum(record_type_counts={"mystery_type": 3})
    assert report["stages"][0]["record_type"] == "mystery_type"
    assert report["stage_count"] == 1


def test_plan_curriculum_empty() -> None:
    report = plan_curriculum(record_type_counts={})
    assert report["stage_count"] == 0


# -- training_recipe_builder ---------------------------------------------------------------------


def test_build_training_recipe_small_dataset_gets_more_epochs() -> None:
    recipe = build_training_recipe(total_record_count=50, curriculum_stage_count=3)
    assert recipe["epochs"] == 5
    assert recipe["executed"] is False
    assert recipe["status"] == "suggested_only"


def test_build_training_recipe_large_dataset_enables_gradient_checkpointing() -> None:
    recipe = build_training_recipe(total_record_count=30000, curriculum_stage_count=5)
    assert recipe["gradient_checkpointing"] is True
    assert recipe["epochs"] == 2


def test_build_training_recipe_never_executes() -> None:
    recipe = build_training_recipe(total_record_count=1000, curriculum_stage_count=1)
    assert recipe["executed"] is False


# -- hardware_estimator --------------------------------------------------------------------------


def test_estimate_hardware_small_is_cpu_feasible() -> None:
    report = estimate_hardware(
        total_character_count=4000, image_count=0, total_image_pixels=0, total_image_bytes=0,
        total_text_bytes=4000,
    )
    assert report["cpu_only_feasible"] is True
    assert report["all_estimates_heuristic"] is True
    assert report["estimated_token_count"] == 1000


def test_estimate_hardware_large_requires_gpu() -> None:
    report = estimate_hardware(
        total_character_count=40_000_000, image_count=100, total_image_pixels=1_000_000,
        total_image_bytes=5_000_000, total_text_bytes=40_000_000,
    )
    assert report["cpu_only_feasible"] is False
    assert report["expected_training_duration_category"] == "many_hours_to_days"


def test_estimate_hardware_images_disable_cpu_only_at_medium_tier() -> None:
    report = estimate_hardware(
        total_character_count=2_400_000, image_count=5, total_image_pixels=100,
        total_image_bytes=100, total_text_bytes=2_400_000,
    )
    assert report["cpu_only_feasible"] is False


# -- package_manifest_builder --------------------------------------------------------------------


def test_build_package_manifest_excludes_self_and_discloses() -> None:
    entries = [{"artifact_name": "a.json", "relative_path": "a.json", "sha256": "x", "file_size_bytes": 1}]
    manifest = build_package_manifest(
        session_public_id="s1", topic="t", source_dataset_public_ids=["d1"],
        source_rag_memory_public_ids=[], artifact_entries=entries, created_at="2026-01-01",
    )
    assert manifest["artifact_count"] == 1
    assert manifest["model_weights_included"] is False
    assert "not self-listed" in manifest["note"]
    assert manifest["sensitive_content_warnings"] == []


# -- reproducibility_hasher ----------------------------------------------------------------------


def test_reproducibility_record_is_reproducible_for_identical_inputs() -> None:
    manifest = {"a": 1, "b": [1, 2, 3]}
    first = build_reproducibility_record(
        package_manifest=manifest, split_seed=42, source_dataset_public_ids=["d2", "d1"],
        source_rag_memory_public_ids=["r1"],
    )
    second = build_reproducibility_record(
        package_manifest=manifest, split_seed=42, source_dataset_public_ids=["d1", "d2"],
        source_rag_memory_public_ids=["r1"],
    )
    assert first == second


def test_reproducibility_record_differs_for_different_seed() -> None:
    manifest = {"a": 1}
    first = build_reproducibility_record(
        package_manifest=manifest, split_seed=1, source_dataset_public_ids=["d1"],
        source_rag_memory_public_ids=[],
    )
    second = build_reproducibility_record(
        package_manifest=manifest, split_seed=2, source_dataset_public_ids=["d1"],
        source_rag_memory_public_ids=[],
    )
    assert first["input_set_checksum_sha256"] != second["input_set_checksum_sha256"]


def test_verify_reproducibility_true_for_matching_checksum() -> None:
    from backend.core.json_utils import dumps_json

    manifest = {"a": 1}
    record = build_reproducibility_record(
        package_manifest=manifest, split_seed=1, source_dataset_public_ids=[], source_rag_memory_public_ids=[],
    )
    assert verify_reproducibility(
        manifest_json=dumps_json(manifest), expected_checksum=record["manifest_checksum_sha256"],
    ) is True


def test_verify_reproducibility_false_for_tampered_manifest() -> None:
    from backend.core.json_utils import dumps_json

    manifest = {"a": 1}
    record = build_reproducibility_record(
        package_manifest=manifest, split_seed=1, source_dataset_public_ids=[], source_rag_memory_public_ids=[],
    )
    assert verify_reproducibility(
        manifest_json=dumps_json({"a": 2}), expected_checksum=record["manifest_checksum_sha256"],
    ) is False


# -- pipeline_report_generator -------------------------------------------------------------------


def _readiness_kwargs(**overrides):
    base = dict(
        session_public_id="s1", topic="t",
        dataset_collection_report={"ready": True, "accepted_count": 1, "total_record_count": 10},
        rag_memory_collection_report={"accepted_count": 0},
        language_distribution_report={"session_count": 1, "dominant_language_counts": {"en": 1}},
        image_statistics_report={"image_count": 0},
        grounding_quality_report={"query_count": 0, "hallucination_rate": None},
        tokenizer_coverage_report={"total_character_count": 100, "unique_character_count": 20, "script_mix": ["latin"], "unseen_character_risk": 0.0},
        curriculum_report={"stage_count": 2},
        hardware_estimate_report={"estimated_token_count": 25},
        reproducibility_record={"manifest_checksum_sha256": "abc"},
    )
    base.update(overrides)
    return base


def test_generate_readiness_report_ready_when_all_signals_good() -> None:
    report = generate_readiness_report(**_readiness_kwargs())
    assert report["status"] == "Ready"
    assert report["training_executed"] is False
    assert report["benchmark_executed"] is False
    assert "no training has been executed" in report["disclaimer"]


def test_generate_readiness_report_blocks_on_no_certified_dataset() -> None:
    report = generate_readiness_report(**_readiness_kwargs(
        dataset_collection_report={"ready": False, "accepted_count": 0, "total_record_count": 0},
    ))
    assert report["status"] == "Not Ready"
    assert any("no certified" in issue for issue in report["blocking_issues"])


def test_generate_readiness_report_blocks_on_high_hallucination_rate() -> None:
    report = generate_readiness_report(**_readiness_kwargs(
        grounding_quality_report={"query_count": 5, "hallucination_rate": 0.5, "average_confidence": 0.4},
    ))
    assert report["status"] == "Not Ready"
    assert any("hallucination rate" in issue for issue in report["blocking_issues"])


def test_generate_readiness_report_blocks_on_empty_tokenizer_coverage() -> None:
    report = generate_readiness_report(**_readiness_kwargs(
        tokenizer_coverage_report={"total_character_count": 0, "unique_character_count": 0, "script_mix": [], "unseen_character_risk": 0.0},
    ))
    assert report["status"] == "Not Ready"
    assert any("tokenizer coverage is empty" in issue for issue in report["blocking_issues"])
