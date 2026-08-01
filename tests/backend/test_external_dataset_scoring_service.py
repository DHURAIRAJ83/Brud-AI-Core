from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.external_dataset_scoring_service import (
    ExternalDatasetScoringService,
    compute_candidate_score,
    derive_warnings_and_blocking_reasons,
)
from core_model.data_discovery import ALL_SCORING_DIMENSIONS

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def repository(tmp_path: Path) -> ExternalDatasetDiscoveryRepository:
    database_path = tmp_path / "scoring.db"
    initialize_database(database_path)
    return ExternalDatasetDiscoveryRepository(database_path)


@pytest.fixture
def session_public_id(repository: ExternalDatasetDiscoveryRepository) -> str:
    session = repository.create_session(
        {"session_code": "scoring-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    return session["public_id"]


def _requirement(repository, session_public_id, **overrides):
    values = {
        "modality": "text",
        "languages": ["tamil"],
        "tasks": ["asr"],
        "intended_uses": ["research"],
        "commercial_requirement": "not_required",
    }
    values.update(overrides)
    return repository.upsert_requirements(session_public_id, values)


def _candidate(repository, session_public_id, **overrides):
    values = {
        "canonical_name": "Tamil ASR Corpus",
        "normalized_name": "tamil asr corpus",
        "description": "Speech transcripts",
        "organization": "org",
        "modality": "text",
        "languages": ["tamil"],
        "tasks": ["asr"],
        "declared_licence": "cc-by-4.0",
        "licence_status": "declared",
        "record_count": 1000,
        "file_formats": ["parquet"],
        "dataset_card_present": True,
        "dataset_card_url": "https://huggingface.co/datasets/org/x",
        "last_modified_at": "2025-01-01T00:00:00Z",
        "version": "1.0",
    }
    values.update(overrides)
    return repository.create_candidate(session_public_id, values)


def test_compute_candidate_score_covers_all_dimensions_and_is_reproducible(
    repository, session_public_id
) -> None:
    requirement = _requirement(repository, session_public_id)
    candidate = _candidate(repository, session_public_id)

    first = compute_candidate_score(
        candidate, requirement, provider_trust_status="domain_verified"
    )
    second = compute_candidate_score(
        candidate, requirement, provider_trust_status="domain_verified"
    )

    assert {c["dimension"] for c in first["components"]} == set(ALL_SCORING_DIMENSIONS)
    assert 0 <= first["overall"] <= 100
    assert first == second


def test_high_quality_candidate_gets_recommended_for_review(repository, session_public_id) -> None:
    requirement = _requirement(repository, session_public_id)
    candidate = _candidate(repository, session_public_id)
    result = compute_candidate_score(
        candidate, requirement, provider_trust_status="research_verified"
    )
    assert result["recommendation_status"] == "recommended_for_review"
    assert result["blocking_reasons"] == []


def test_sparse_candidate_is_insufficient_metadata(repository, session_public_id) -> None:
    requirement = _requirement(repository, session_public_id)
    candidate = _candidate(
        repository,
        session_public_id,
        description="",
        organization=None,
        declared_licence=None,
        licence_status="unknown",
        record_count=None,
        file_formats=[],
        dataset_card_present=False,
        dataset_card_url=None,
        last_modified_at=None,
        version=None,
    )
    result = compute_candidate_score(candidate, requirement, provider_trust_status="unverified")
    assert result["recommendation_status"] == "insufficient_metadata"


def test_commercial_required_forces_high_risk(repository, session_public_id) -> None:
    requirement = _requirement(repository, session_public_id, commercial_requirement="required")
    candidate = _candidate(repository, session_public_id)
    result = compute_candidate_score(
        candidate, requirement, provider_trust_status="domain_verified"
    )
    assert result["recommendation_status"] == "high_risk"
    assert "commercial_use_required_but_not_verifiable_in_this_phase" in result["blocking_reasons"]


def test_derive_warnings_flags_missing_card_and_unknown_licence() -> None:
    candidate = {
        "dataset_card_present": False,
        "licence_status": "unknown",
        "last_modified_at": None,
    }
    requirement = {"commercial_requirement": "not_required"}
    warnings, blocking_reasons = derive_warnings_and_blocking_reasons(candidate, requirement)
    assert "dataset_card_missing" in warnings
    assert "licence_unknown" in warnings
    assert "last_modified_unknown" in warnings
    assert blocking_reasons == []


def test_rescore_candidate_persists_scores_and_summary_fields(
    repository, session_public_id
) -> None:
    requirement = _requirement(repository, session_public_id)
    candidate = _candidate(repository, session_public_id)
    service = ExternalDatasetScoringService(repository)

    updated = service.rescore_candidate(
        candidate["public_id"], requirement, provider_trust_status="domain_verified"
    )
    assert updated["suitability_score"] is not None
    assert updated["recommendation_status"] == "recommended_for_review"

    persisted_scores = repository.list_candidate_scores(candidate["public_id"])
    assert {item["dimension"] for item in persisted_scores} == set(ALL_SCORING_DIMENSIONS)
