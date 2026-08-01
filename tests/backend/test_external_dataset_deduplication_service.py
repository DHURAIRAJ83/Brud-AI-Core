from pathlib import Path

import pytest

from backend.database.migrations import initialize_database
from backend.database.repositories.external_data_providers import (
    ExternalDataProviderRepository,
)
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.external_dataset_deduplication_service import (
    ExternalDatasetDeduplicationService,
)
from backend.services.external_dataset_normalization_service import (
    ExternalDatasetNormalizationService,
)
from core_model.data_discovery.candidate_model import NormalizedDatasetMetadata

ADMIN_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def database_path(tmp_path: Path) -> Path:
    path = tmp_path / "dedup.db"
    initialize_database(path)
    return path


@pytest.fixture
def discovery_repository(database_path: Path) -> ExternalDatasetDiscoveryRepository:
    return ExternalDatasetDiscoveryRepository(database_path)


@pytest.fixture
def provider_repository(database_path: Path) -> ExternalDataProviderRepository:
    return ExternalDataProviderRepository(database_path)


@pytest.fixture
def huggingface_id(provider_repository: ExternalDataProviderRepository) -> str:
    return provider_repository.get_provider_by_code("huggingface")["public_id"]


@pytest.fixture
def github_id(provider_repository: ExternalDataProviderRepository) -> str:
    return provider_repository.get_provider_by_code("github")["public_id"]


@pytest.fixture
def session_public_id(discovery_repository: ExternalDatasetDiscoveryRepository) -> str:
    session = discovery_repository.create_session(
        {"session_code": "dedup-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    return session["public_id"]


def _seed_candidate(
    discovery_repository, session_public_id, provider_public_id, metadata: NormalizedDatasetMetadata
):
    candidate_fields = ExternalDatasetNormalizationService.build_candidate_fields(metadata)
    candidate = discovery_repository.create_candidate(session_public_id, candidate_fields)
    source_fields = ExternalDatasetNormalizationService.build_candidate_source_fields(
        metadata, provider_public_id=provider_public_id
    )
    discovery_repository.add_candidate_source(candidate["public_id"], source_fields)
    return candidate


def test_resolve_returns_new_when_no_existing_candidates(
    discovery_repository, session_public_id, huggingface_id
) -> None:
    service = ExternalDatasetDeduplicationService(discovery_repository)
    metadata = NormalizedDatasetMetadata(provider_dataset_id="org/x", name="Tamil Corpus")
    decision = service.resolve(
        session_public_id=session_public_id,
        provider_public_id=huggingface_id,
        provider_code="huggingface",
        metadata=metadata,
    )
    assert decision.action == "new"
    assert decision.target_candidate_public_id is None


def test_resolve_merges_on_exact_re_seen_provider_dataset_id(
    discovery_repository, session_public_id, huggingface_id
) -> None:
    metadata = NormalizedDatasetMetadata(provider_dataset_id="org/x", name="Tamil Corpus")
    candidate = _seed_candidate(discovery_repository, session_public_id, huggingface_id, metadata)

    service = ExternalDatasetDeduplicationService(discovery_repository)
    decision = service.resolve(
        session_public_id=session_public_id,
        provider_public_id=huggingface_id,
        provider_code="huggingface",
        metadata=metadata,
    )
    assert decision.action == "merge_exact_source"
    assert decision.target_candidate_public_id == candidate["public_id"]


def test_resolve_merges_on_matching_org_and_name_across_providers(
    discovery_repository, session_public_id, huggingface_id, github_id
) -> None:
    existing = NormalizedDatasetMetadata(
        provider_dataset_id="hf-id", name="Indic Voices", organization="ai4bharat"
    )
    candidate = _seed_candidate(discovery_repository, session_public_id, huggingface_id, existing)

    incoming = NormalizedDatasetMetadata(
        provider_dataset_id="gh-id", name="Indic Voices", organization="ai4bharat"
    )
    service = ExternalDatasetDeduplicationService(discovery_repository)
    decision = service.resolve(
        session_public_id=session_public_id,
        provider_public_id=github_id,
        provider_code="github",
        metadata=incoming,
    )
    assert decision.action == "merge_strong_signal"
    assert decision.target_candidate_public_id == candidate["public_id"]


def test_resolve_merges_on_identical_repository_url(
    discovery_repository, session_public_id, huggingface_id, github_id
) -> None:
    existing = NormalizedDatasetMetadata(
        provider_dataset_id="hf-id",
        name="Different Name One",
        repository_url="https://github.com/org/repo",
    )
    candidate = _seed_candidate(discovery_repository, session_public_id, huggingface_id, existing)

    incoming = NormalizedDatasetMetadata(
        provider_dataset_id="gh-id",
        name="Totally Different Name Two",
        repository_url="https://github.com/org/repo/",
    )
    service = ExternalDatasetDeduplicationService(discovery_repository)
    decision = service.resolve(
        session_public_id=session_public_id,
        provider_public_id=github_id,
        provider_code="github",
        metadata=incoming,
    )
    assert decision.action == "merge_strong_signal"
    assert decision.target_candidate_public_id == candidate["public_id"]


def test_resolve_merges_on_cross_referenced_url(
    discovery_repository, session_public_id, huggingface_id, github_id
) -> None:
    existing = NormalizedDatasetMetadata(
        provider_dataset_id="hf-id",
        name="HF Dataset",
        homepage_url="https://huggingface.co/datasets/org/x",
    )
    candidate = _seed_candidate(discovery_repository, session_public_id, huggingface_id, existing)

    # a github mirror whose own homepage points at the original HF page
    incoming = NormalizedDatasetMetadata(
        provider_dataset_id="gh-id",
        name="GitHub Mirror",
        repository_url="https://github.com/org/mirror",
        homepage_url="https://huggingface.co/datasets/org/x",
    )
    service = ExternalDatasetDeduplicationService(discovery_repository)
    decision = service.resolve(
        session_public_id=session_public_id,
        provider_public_id=github_id,
        provider_code="github",
        metadata=incoming,
    )
    assert decision.action == "merge_strong_signal"
    assert decision.target_candidate_public_id == candidate["public_id"]


def test_resolve_flags_possible_duplicate_on_same_name_different_org(
    discovery_repository, session_public_id, huggingface_id, github_id
) -> None:
    existing = NormalizedDatasetMetadata(
        provider_dataset_id="hf-id", name="Common Corpus Name", organization="org-a"
    )
    candidate = _seed_candidate(discovery_repository, session_public_id, huggingface_id, existing)

    incoming = NormalizedDatasetMetadata(
        provider_dataset_id="gh-id", name="Common Corpus Name", organization="org-b"
    )
    service = ExternalDatasetDeduplicationService(discovery_repository)
    decision = service.resolve(
        session_public_id=session_public_id,
        provider_public_id=github_id,
        provider_code="github",
        metadata=incoming,
    )
    assert decision.action == "possible_duplicate"
    assert decision.target_candidate_public_id == candidate["public_id"]


def test_resolve_leaves_renamed_datasets_unrelated(
    discovery_repository, session_public_id, huggingface_id, github_id
) -> None:
    existing = NormalizedDatasetMetadata(
        provider_dataset_id="hf-id", name="Old Dataset Name", organization="org-a"
    )
    _seed_candidate(discovery_repository, session_public_id, huggingface_id, existing)

    incoming = NormalizedDatasetMetadata(
        provider_dataset_id="gh-id", name="Brand New Dataset Title", organization="org-a"
    )
    service = ExternalDatasetDeduplicationService(discovery_repository)
    decision = service.resolve(
        session_public_id=session_public_id,
        provider_public_id=github_id,
        provider_code="github",
        metadata=incoming,
    )
    assert decision.action == "new"


def test_resolve_leaves_differently_named_multilingual_variants_unrelated(
    discovery_repository, session_public_id, huggingface_id, github_id
) -> None:
    existing = NormalizedDatasetMetadata(
        provider_dataset_id="hf-id", name="Corpus Tamil", organization="org-a"
    )
    _seed_candidate(discovery_repository, session_public_id, huggingface_id, existing)

    incoming = NormalizedDatasetMetadata(
        provider_dataset_id="gh-id", name="Corpus Hindi", organization="org-a"
    )
    service = ExternalDatasetDeduplicationService(discovery_repository)
    decision = service.resolve(
        session_public_id=session_public_id,
        provider_public_id=github_id,
        provider_code="github",
        metadata=incoming,
    )
    assert decision.action == "new"
