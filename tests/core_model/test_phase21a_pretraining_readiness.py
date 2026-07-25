from core_model.pretraining_readiness.readiness import (
    READINESS_DIMENSIONS,
    build_readiness_report,
    overall_readiness,
)
from core_model.pretraining_readiness.resource_profiles import (
    DEFAULT_SAFE_RAM_CEILING_BYTES,
    estimate_resource_profile,
    maximum_safe_local_config,
    micro_smoke_test_config,
    small_experimental_config,
)
from core_model.pretraining_readiness.sufficiency import (
    SufficiencyThresholds,
    build_sufficiency_report,
    character_category_counts,
    classify_sufficiency,
)
from core_model.pretraining_readiness.tokenizer_selection import (
    classify_candidate,
    score_candidate,
    select_recommended_candidate,
)

# --- sufficiency -----------------------------------------------------


def test_character_category_counts_distinguishes_tamil_english_digits_punctuation():
    counts = character_category_counts("தமிழ் text 123, ஒன்று.")
    assert counts["tamil"] > 0
    assert counts["english"] > 0
    assert counts["digits"] == 3
    assert counts["punctuation"] >= 1


def test_classify_sufficiency_requires_script_diversity():
    assert (
        classify_sufficiency(
            total_characters=10_000_000, total_records=200_000, script_categories_present=1
        )
        == "insufficient"
    )


def test_classify_sufficiency_thresholds_are_honest_about_tiny_corpora():
    assert (
        classify_sufficiency(
            total_characters=500, total_records=5, script_categories_present=2
        )
        == "insufficient"
    )
    assert (
        classify_sufficiency(
            total_characters=30_000, total_records=60, script_categories_present=2
        )
        == "experimental"
    )
    assert (
        classify_sufficiency(
            total_characters=25_000_000, total_records=200_000, script_categories_present=2
        )
        == "production_candidate"
    )


def test_classify_sufficiency_custom_thresholds():
    thresholds = SufficiencyThresholds(experimental_min_characters=10, experimental_min_records=1)
    assert (
        classify_sufficiency(
            total_characters=20, total_records=2, script_categories_present=2,
            thresholds=thresholds,
        )
        == "experimental"
    )


def test_build_sufficiency_report_uses_real_language_categories_not_script_guessing():
    records = [
        {"text": "தமிழ் வாக்கியம்", "language_category": "ta", "domain": "general",
         "style": "formal", "source": "a", "licence_family": "public_domain"},
        {"text": "epdi eppadi", "language_category": "tgl", "domain": "general",
         "style": "informal", "source": "a", "licence_family": "public_domain"},
        {"text": "hello world", "language_category": "en", "domain": "general",
         "style": "formal", "source": "b", "licence_family": "public_domain"},
    ]
    report = build_sufficiency_report(records)
    assert report["tamil_only_record_count"] == 1
    assert report["tanglish_record_count"] == 1
    assert report["english_only_record_count"] == 1
    assert report["total_records"] == 3
    assert report["sufficiency_state"] == "insufficient"


def test_build_sufficiency_report_empty_input():
    report = build_sufficiency_report([])
    assert report["total_records"] == 0
    assert report["sufficiency_state"] == "insufficient"


# --- resource profiles -----------------------------------------------------


def test_micro_smoke_test_profile_is_one_to_three_million_params():
    config = micro_smoke_test_config(4000)
    from core_model.evaluation.architecture_checks import estimate_parameters

    params = estimate_parameters(config)
    assert 500_000 <= params <= 5_000_000


def test_small_experimental_profile_is_ten_to_thirty_million_params():
    config = small_experimental_config(4000)
    from core_model.evaluation.architecture_checks import estimate_parameters

    params = estimate_parameters(config)
    assert 5_000_000 <= params <= 40_000_000


def test_maximum_safe_local_config_respects_ram_ceiling():
    config = maximum_safe_local_config(4000, safe_ram_ceiling_bytes=500_000_000)
    from core_model.evaluation.architecture_checks import estimate_memory

    memory = estimate_memory(config, batch_size=2)
    assert memory["training_adamw"] <= 500_000_000


def test_maximum_safe_local_falls_back_to_micro_when_ceiling_too_small():
    config = maximum_safe_local_config(4000, safe_ram_ceiling_bytes=1)
    assert config.hidden_size == micro_smoke_test_config(4000).hidden_size


def test_estimate_resource_profile_rejects_unknown_profile():
    import pytest

    with pytest.raises(ValueError):
        estimate_resource_profile("nonexistent_profile", 4000)


def test_estimate_resource_profile_within_safe_limit_flag():
    estimate = estimate_resource_profile(
        "micro_smoke_test", 4000, safe_ram_ceiling_bytes=DEFAULT_SAFE_RAM_CEILING_BYTES
    )
    assert estimate.within_safe_limit is True
    assert estimate.parameter_count > 0
    assert estimate.checkpoint_disk_bytes > 0
    assert estimate.optimizer_disk_bytes > 0
    assert estimate.estimated_training_duration_seconds_min <= (
        estimate.estimated_training_duration_seconds_max
    )


def test_estimate_resource_profile_unsafe_when_ceiling_too_low():
    estimate = estimate_resource_profile("small_experimental", 4000, safe_ram_ceiling_bytes=1000)
    assert estimate.within_safe_limit is False


# --- readiness gate -----------------------------------------------------


def test_overall_readiness_any_fail_is_not_ready():
    results = dict.fromkeys(READINESS_DIMENSIONS, "pass")
    results["checkpoint_integrity"] = "fail"
    assert overall_readiness(results) == "not_ready"


def test_overall_readiness_warning_caps_at_experimental():
    results = dict.fromkeys(READINESS_DIMENSIONS, "pass")
    results["tokenizer_quality"] = "warning"
    assert overall_readiness(results) == "ready_for_experimental_pretraining"


def test_overall_readiness_not_evaluated_caps_at_experimental_not_bounded():
    results = dict.fromkeys(READINESS_DIMENSIONS, "pass")
    results["audit_completeness"] = "not_evaluated"
    assert overall_readiness(results) == "ready_for_experimental_pretraining"


def test_overall_readiness_all_pass_is_ready_for_bounded_pretraining():
    results = dict.fromkeys(READINESS_DIMENSIONS, "pass")
    assert overall_readiness(results) == "ready_for_bounded_pretraining"


def test_build_readiness_report_counts():
    results = dict.fromkeys(READINESS_DIMENSIONS, "pass")
    results["checkpoint_integrity"] = "fail"
    results["tokenizer_quality"] = "warning"
    report = build_readiness_report(results)
    assert report["overall_result"] == "not_ready"
    assert report["fail_count"] == 1
    assert report["warning_count"] == 1
    assert report["pass_count"] == len(READINESS_DIMENSIONS) - 2


# --- tokenizer selection -----------------------------------------------------


def test_score_candidate_flags_hard_fails():
    metrics = {
        "tamil_fragmentation_ratio": 1.0, "tanglish_fragmentation_ratio": 1.0,
        "unknown_token_rate": 0.5, "round_trip_integrity_rate": 0.99,
        "characters_per_token": 2.0, "mixed_script_fragmentation_ratio": 1.0,
        "artifact_checksum_verified": False, "within_memory_limit": True,
    }
    dims = score_candidate(metrics, corpus_sufficiency_state="candidate")
    assert dims["unknown_token_rate"] == "fail"
    assert dims["artifact_integrity"] == "fail"
    assert classify_candidate(dims) == "rejected"


def test_select_recommended_candidate_prefers_smallest_in_best_tier():
    candidates = [
        {"vocabulary_size": 8000, "final_status": "recommended"},
        {"vocabulary_size": 2000, "final_status": "recommended"},
        {"vocabulary_size": 4000, "final_status": "experimental"},
    ]
    selected = select_recommended_candidate(candidates)
    assert selected["vocabulary_size"] == 2000


def test_select_recommended_candidate_never_picks_rejected():
    candidates = [
        {"vocabulary_size": 1000, "final_status": "rejected"},
        {"vocabulary_size": 4000, "final_status": "experimental"},
    ]
    selected = select_recommended_candidate(candidates)
    assert selected["vocabulary_size"] == 4000


def test_select_recommended_candidate_returns_none_when_all_rejected():
    candidates = [{"vocabulary_size": 2000, "final_status": "rejected"}]
    assert select_recommended_candidate(candidates) is None
