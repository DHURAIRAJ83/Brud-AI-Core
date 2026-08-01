from core_model.data_discovery.scoring import (
    compute_suitability_score,
    score_accessibility,
    score_conflict_penalty,
    score_dataset_card_presence,
    score_format_suitability,
    score_gated_access_penalty,
    score_intended_use_fit,
    score_language_fit,
    score_metadata_completeness,
    score_modality_fit,
    score_provider_trust,
    score_recency,
    score_requirement_fit,
    score_risk_penalty,
    score_size_suitability,
    score_task_fit,
    score_unknown_licence_penalty,
    score_version_traceability,
)


def test_language_fit_full_overlap() -> None:
    component = score_language_fit(
        requirement_languages=("tamil",), candidate_languages=("tamil", "english"), weight=1.5
    )
    assert component.raw_value == 1.0
    assert component.score == 1.5
    assert "tamil" in component.reason


def test_language_fit_no_overlap() -> None:
    component = score_language_fit(
        requirement_languages=("tamil",), candidate_languages=("english",), weight=1.5
    )
    assert component.raw_value == 0.0
    assert component.score == 0.0


def test_language_fit_no_requirement_is_neutral() -> None:
    component = score_language_fit(
        requirement_languages=(), candidate_languages=("tamil",), weight=1.5
    )
    assert component.raw_value == 0.5


def test_modality_fit_match_and_mismatch() -> None:
    match = score_modality_fit(requirement_modality="text", candidate_modality="text", weight=1.0)
    assert match.raw_value == 1.0
    mismatch = score_modality_fit(
        requirement_modality="text", candidate_modality="image", weight=1.0
    )
    assert mismatch.raw_value == 0.0
    unknown = score_modality_fit(requirement_modality="text", candidate_modality=None, weight=1.0)
    assert unknown.raw_value == 0.3


def test_task_fit_and_intended_use_fit_overlap() -> None:
    task = score_task_fit(requirement_tasks=("chat",), candidate_tasks=("chat", "qa"), weight=1.25)
    assert task.raw_value == 1.0
    use = score_intended_use_fit(
        requirement_uses=("training", "rag"), candidate_use_signals=("training",), weight=1.0
    )
    assert use.raw_value == 0.5


def test_requirement_fit_and_metadata_completeness() -> None:
    fit = score_requirement_fit(matched_fields=3, total_fields=4, weight=1.5)
    assert fit.raw_value == 0.75
    completeness = score_metadata_completeness(
        present_field_count=5, total_field_count=10, weight=0.75
    )
    assert completeness.raw_value == 0.5


def test_provider_trust_scales_with_trust_status() -> None:
    unverified = score_provider_trust(trust_status="unverified", weight=0.75)
    verified = score_provider_trust(trust_status="government_verified", weight=0.75)
    assert unverified.raw_value < verified.raw_value


def test_dataset_card_presence() -> None:
    present = score_dataset_card_presence(present=True, weight=0.5)
    missing = score_dataset_card_presence(present=False, weight=0.5)
    assert present.raw_value == 1.0
    assert missing.raw_value == 0.0
    assert "missing" in missing.reason


def test_version_traceability() -> None:
    both = score_version_traceability(has_version=True, has_revision=True, weight=0.5)
    neither = score_version_traceability(has_version=False, has_revision=False, weight=0.5)
    assert both.raw_value == 1.0
    assert neither.raw_value == 0.0


def test_size_suitability() -> None:
    unknown = score_size_suitability(
        download_size_bytes=None, maximum_download_size_bytes=1000, weight=0.5
    )
    within = score_size_suitability(
        download_size_bytes=500, maximum_download_size_bytes=1000, weight=0.5
    )
    over = score_size_suitability(
        download_size_bytes=2000, maximum_download_size_bytes=1000, weight=0.5
    )
    assert unknown.raw_value == 0.5
    assert within.raw_value == 1.0
    assert over.raw_value == 0.2


def test_format_suitability() -> None:
    match = score_format_suitability(
        candidate_formats=("jsonl", "csv"), preferred_formats=("jsonl",), weight=0.5
    )
    no_match = score_format_suitability(
        candidate_formats=("parquet",), preferred_formats=("jsonl",), weight=0.5
    )
    assert match.raw_value == 1.0
    assert no_match.raw_value == 0.2


def test_recency_unknown_vs_known() -> None:
    unknown = score_recency(last_modified_at=None, weight=0.25)
    known = score_recency(last_modified_at="2025-01-01", weight=0.25)
    assert unknown.raw_value < known.raw_value


def test_accessibility_penalizes_restrictions() -> None:
    open_access = score_accessibility(
        gated=False, private=False, requires_authentication=False, weight=0.25
    )
    restricted = score_accessibility(
        gated=True, private=True, requires_authentication=True, weight=0.25
    )
    assert open_access.raw_value == 1.0
    assert restricted.raw_value < open_access.raw_value


def test_penalty_dimensions() -> None:
    assert score_risk_penalty(blocking_reason_count=0, weight=-1.0).raw_value == 0.0
    assert score_risk_penalty(blocking_reason_count=2, weight=-1.0).raw_value == 1.0
    assert score_unknown_licence_penalty(licence_status="unknown", weight=-0.75).raw_value == 1.0
    assert score_unknown_licence_penalty(licence_status="declared", weight=-0.75).raw_value == 0.0
    assert score_gated_access_penalty(gated=True, private=False, weight=-0.5).raw_value == 1.0
    assert score_gated_access_penalty(gated=False, private=False, weight=-0.5).raw_value == 0.0
    assert score_conflict_penalty(is_possible_duplicate=True, weight=-0.5).raw_value == 1.0


def test_compute_suitability_score_is_reproducible() -> None:
    components = [
        score_language_fit(
            requirement_languages=("tamil",), candidate_languages=("tamil",), weight=1.5
        ),
        score_modality_fit(requirement_modality="text", candidate_modality="text", weight=1.0),
        score_dataset_card_presence(present=True, weight=0.5),
        score_unknown_licence_penalty(licence_status="unknown", weight=-0.75),
    ]
    first = compute_suitability_score(components)
    second = compute_suitability_score(components)
    assert first == second
    assert 0 <= first["overall"] <= 100


def test_compute_suitability_score_never_exceeds_bounds_even_with_all_penalties() -> None:
    components = [
        score_risk_penalty(blocking_reason_count=5, weight=-1.0),
        score_unknown_licence_penalty(licence_status="unknown", weight=-0.75),
        score_gated_access_penalty(gated=True, private=True, weight=-0.5),
        score_conflict_penalty(is_possible_duplicate=True, weight=-0.5),
    ]
    result = compute_suitability_score(components)
    assert result["overall"] == 0


def test_compute_suitability_score_rejects_unknown_dimension() -> None:
    from core_model.data_discovery.scoring import ScoreComponent

    bad = ScoreComponent(
        dimension="not_a_real_dimension", raw_value=1.0, weight=1.0, score=1.0, reason="x"
    )
    try:
        compute_suitability_score([bad])
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_scoring_never_uses_popularity_signal() -> None:
    """No function in this module accepts a downloads/popularity/star
    count parameter -- structural confirmation of rule 8's "must not
    treat popularity as quality"."""

    import inspect

    from core_model.data_discovery import scoring

    for name, func in inspect.getmembers(scoring, inspect.isfunction):
        if not name.startswith("score_"):
            continue
        params = set(inspect.signature(func).parameters)
        assert not params & {"downloads", "popularity", "stars", "download_count", "star_count"}
