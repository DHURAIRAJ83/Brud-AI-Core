from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.external_dataset_comparison_service import (
    ComparisonValidationError,
    ExternalDatasetComparisonService,
)
from backend.services.external_dataset_scoring_service import ExternalDatasetScoringService

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def repository(tmp_path: Path) -> ExternalDatasetDiscoveryRepository:
    database_path = tmp_path / "comparison.db"
    initialize_database(database_path)
    return ExternalDatasetDiscoveryRepository(database_path)


@pytest.fixture
def session_public_id(repository: ExternalDatasetDiscoveryRepository) -> str:
    session = repository.create_session(
        {"session_code": "comparison-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    return session["public_id"]


@pytest.fixture
def requirement(repository, session_public_id):
    return repository.upsert_requirements(
        session_public_id,
        {"modality": "text", "languages": ["tamil"], "tasks": ["asr"]},
    )


def _scored_candidate(repository, session_public_id, requirement, *, name, trust_status):
    candidate = repository.create_candidate(
        session_public_id,
        {
            "canonical_name": name,
            "normalized_name": name.lower(),
            "languages": ["tamil"],
            "tasks": ["asr"],
            "dataset_card_present": True,
            "declared_licence": "cc-by-4.0",
            "licence_status": "declared",
        },
    )
    scoring_service = ExternalDatasetScoringService(repository)
    return scoring_service.rescore_candidate(
        candidate["public_id"], requirement, provider_trust_status=trust_status
    )


def test_create_comparison_persists_summary(repository, session_public_id, requirement) -> None:
    high = _scored_candidate(
        repository,
        session_public_id,
        requirement,
        name="High Trust",
        trust_status="research_verified",
    )
    low = _scored_candidate(
        repository, session_public_id, requirement, name="Low Trust", trust_status="unverified"
    )

    service = ExternalDatasetComparisonService(repository)
    comparison = service.create_comparison(
        session_public_id,
        [high["public_id"], low["public_id"]],
        created_by_admin_public_id=ADMIN_ID,
    )

    assert set(comparison["candidate_ids"]) == {high["public_id"], low["public_id"]}
    summary = comparison["summary"]
    assert summary["best_overall_candidate_public_id"] == high["public_id"]
    assert "provider_trust" in summary["dimensions"]
    assert summary["dimensions"]["provider_trust"]["best_candidate_public_id"] == high["public_id"]

    fetched = repository.get_comparison(comparison["public_id"])
    assert fetched == comparison

    listed = repository.list_comparisons(session_public_id)
    assert [item["public_id"] for item in listed] == [comparison["public_id"]]


def test_create_comparison_rejects_too_few_candidates(
    repository, session_public_id, requirement
) -> None:
    only = _scored_candidate(
        repository, session_public_id, requirement, name="Only One", trust_status="unverified"
    )
    service = ExternalDatasetComparisonService(repository)
    with pytest.raises(ComparisonValidationError):
        service.create_comparison(
            session_public_id, [only["public_id"]], created_by_admin_public_id=ADMIN_ID
        )


def test_create_comparison_rejects_too_many_candidates(
    repository, session_public_id, requirement
) -> None:
    ids = [
        _scored_candidate(
            repository,
            session_public_id,
            requirement,
            name=f"Candidate {i}",
            trust_status="unverified",
        )["public_id"]
        for i in range(6)
    ]
    service = ExternalDatasetComparisonService(repository)
    with pytest.raises(ComparisonValidationError):
        service.create_comparison(session_public_id, ids, created_by_admin_public_id=ADMIN_ID)


def test_create_comparison_rejects_candidate_from_other_session(
    repository, session_public_id, requirement
) -> None:
    a = _scored_candidate(
        repository, session_public_id, requirement, name="A", trust_status="unverified"
    )
    other_session = repository.create_session(
        {"session_code": "other-session", "requested_by_admin_public_id": ADMIN_ID}
    )
    other_requirement = repository.upsert_requirements(other_session["public_id"], {})
    b = _scored_candidate(
        repository,
        other_session["public_id"],
        other_requirement,
        name="B",
        trust_status="unverified",
    )

    service = ExternalDatasetComparisonService(repository)
    with pytest.raises(ComparisonValidationError):
        service.create_comparison(
            session_public_id,
            [a["public_id"], b["public_id"]],
            created_by_admin_public_id=ADMIN_ID,
        )


def test_build_comparison_summary_warns_when_candidate_unscored(
    repository, session_public_id, requirement
) -> None:
    scored = _scored_candidate(
        repository, session_public_id, requirement, name="Scored", trust_status="unverified"
    )
    unscored = repository.create_candidate(
        session_public_id, {"canonical_name": "Unscored", "normalized_name": "unscored"}
    )
    service = ExternalDatasetComparisonService(repository)
    summary = service.build_comparison_summary(
        session_public_id, [scored["public_id"], unscored["public_id"]]
    )
    assert any("has not been scored yet" in warning for warning in summary["warnings"])
