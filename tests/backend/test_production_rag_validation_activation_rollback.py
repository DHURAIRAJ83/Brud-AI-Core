import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.database.repositories.rag import RagRepository
from backend.services.production_rag_activation_service import ProductionRagActivationService
from backend.services.production_rag_candidate_service import ProductionRagCandidateService
from backend.services.production_rag_promotion_service import ProductionRagPromotionService
from backend.services.production_rag_validation_service import ProductionRagValidationService
from backend.services.rag_ingestion_service import RagIngestionService
from tests.backend.test_production_rag_eligibility_and_promotion import (
    _insert_knowledge_space,
    _mark_eligible_for_production_rag,
)
from tests.backend.test_training_suitability_and_transformation import (
    ADMIN_ID,
    _build_accepted_experiment,
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "production_rag_activation.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _register_deterministic_embedding_model(settings: Settings) -> str:
    ingestion = RagIngestionService(RagRepository(settings.resolved_database_path), settings)
    from backend.models.rag import EmbeddingModelCreate

    model = ingestion.create_embedding_model(
        EmbeddingModelCreate(
            name=f"test-embed-{uuid4().hex[:8]}", version="v1",
            provider_type="deterministic_test_embedding", dimensions=8,
            maximum_input_tokens=512,
        ),
        ADMIN_ID,
    )
    return model["public_id"]


def _approved_promotion_request(
    settings: Settings, *, code_suffix: str = "1"
) -> tuple[dict, list[dict]]:
    built = _build_accepted_experiment(
        settings, record_text="தமிழ் என்றால் என்ன? தமிழ் ஒரு திராவிட மொழி. Say hello வணக்கம்.",
        code_suffix=code_suffix,
    )
    _mark_eligible_for_production_rag(settings, built["experiment"]["public_id"])
    space_id = _insert_knowledge_space(settings)
    embedding_model_id = _register_deterministic_embedding_model(settings)

    promotion_service = ProductionRagPromotionService(settings)
    request = promotion_service.create_request(
        {
            "rag_sandbox_experiment_public_id": built["experiment"]["public_id"],
            "knowledge_space_public_id": space_id,
            "selected_record_ids": [r["public_id"] for r in built["records"]],
            "embedding_assignment_key": embedding_model_id,
        },
        admin_id=ADMIN_ID,
    )
    promotion_service.submit_for_review(request["public_id"], admin_id=ADMIN_ID)
    approval = promotion_service.request_approval(request["public_id"], admin_id=ADMIN_ID)
    promotion_service.approve(approval["public_id"], admin_id=ADMIN_ID)
    request = ProductionReadinessRepository(
        settings.resolved_database_path
    ).get_rag_promotion_request(request["public_id"])
    return request, built["records"]


def test_full_rag_candidate_build_validate_activate_rollback(settings: Settings) -> None:
    request, _records = _approved_promotion_request(settings)

    candidate_service = ProductionRagCandidateService(settings)
    candidate = candidate_service.build_candidate(request["public_id"], admin_id=ADMIN_ID)
    assert candidate["status"] == "built"
    assert candidate["retrieval_profile_public_id"]
    assert candidate["production_visible"] is False

    validation_service = ProductionRagValidationService(settings)
    result = validation_service.run_validation(candidate["public_id"], admin_id=ADMIN_ID)
    assert result["candidate"]["status"] == "validated"
    assert len(result["results"]) >= 1

    activation_service = ProductionRagActivationService(settings)
    activated = activation_service.activate(candidate["public_id"], admin_id=ADMIN_ID)
    assert activated["status"] == "activated"
    assert activated["production_visible"] is True

    with sqlite3.connect(settings.resolved_database_path) as connection:
        profile_status = connection.execute(
            "SELECT status FROM rag_retrieval_profiles WHERE public_id=?",
            (candidate["retrieval_profile_public_id"],),
        ).fetchone()[0]
    assert profile_status == "active"

    repository = ProductionReadinessRepository(settings.resolved_database_path)
    refreshed_request = repository.get_rag_promotion_request(request["public_id"])
    assert refreshed_request["status"] == "ready_for_activation"

    events = repository.list_rag_activation_events(candidate["public_id"])
    assert {e["event_type"] for e in events} == {"pre_activation_snapshot", "activated"}

    # This was the space's first-ever activation -- there is no previous
    # active profile to roll back to, and the service correctly refuses
    # rather than pretending there is one.
    with pytest.raises(ValidationError):
        activation_service.rollback(candidate["public_id"], admin_id=ADMIN_ID)


def test_rollback_reactivates_the_previous_profile(settings: Settings) -> None:
    request, _records = _approved_promotion_request(settings)
    candidate_service = ProductionRagCandidateService(settings)
    validation_service = ProductionRagValidationService(settings)
    activation_service = ProductionRagActivationService(settings)

    first = candidate_service.build_candidate(request["public_id"], admin_id=ADMIN_ID)
    validation_service.run_validation(first["public_id"], admin_id=ADMIN_ID)
    activation_service.activate(first["public_id"], admin_id=ADMIN_ID)

    second_request, _ = _approved_promotion_request(settings, code_suffix="2")
    with sqlite3.connect(settings.resolved_database_path) as connection:
        connection.execute(
            "UPDATE production_rag_promotion_requests SET knowledge_space_id=("
            "SELECT knowledge_space_id FROM production_rag_promotion_requests WHERE public_id=?"
            ") WHERE public_id=?",
            (request["public_id"], second_request["public_id"]),
        )
        connection.commit()
    second = candidate_service.build_candidate(second_request["public_id"], admin_id=ADMIN_ID)
    validation_service.run_validation(second["public_id"], admin_id=ADMIN_ID)
    activated_second = activation_service.activate(second["public_id"], admin_id=ADMIN_ID)
    assert activated_second["status"] == "activated"

    repository = ProductionReadinessRepository(settings.resolved_database_path)
    with sqlite3.connect(settings.resolved_database_path) as connection:
        first_profile_status = connection.execute(
            "SELECT status FROM rag_retrieval_profiles WHERE public_id=?",
            (first["retrieval_profile_public_id"],),
        ).fetchone()[0]
    assert first_profile_status == "archived"

    rollback_event = activation_service.rollback(second["public_id"], admin_id=ADMIN_ID)
    assert rollback_event["event_type"] == "rolled_back"
    with sqlite3.connect(settings.resolved_database_path) as connection:
        first_profile_status = connection.execute(
            "SELECT status FROM rag_retrieval_profiles WHERE public_id=?",
            (first["retrieval_profile_public_id"],),
        ).fetchone()[0]
        second_profile_status = connection.execute(
            "SELECT status FROM rag_retrieval_profiles WHERE public_id=?",
            (second["retrieval_profile_public_id"],),
        ).fetchone()[0]
    assert first_profile_status == "active"
    assert second_profile_status != "active"
    superseded = repository.get_rag_release_candidate(second["public_id"])
    assert superseded["status"] == "superseded"
    assert superseded["production_visible"] is False


def test_activation_requires_approved_promotion(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    _mark_eligible_for_production_rag(settings, built["experiment"]["public_id"])
    space_id = _insert_knowledge_space(settings)
    embedding_model_id = _register_deterministic_embedding_model(settings)

    promotion_service = ProductionRagPromotionService(settings)
    request = promotion_service.create_request(
        {
            "rag_sandbox_experiment_public_id": built["experiment"]["public_id"],
            "knowledge_space_public_id": space_id,
            "selected_record_ids": [r["public_id"] for r in built["records"]],
            "embedding_assignment_key": embedding_model_id,
        },
        admin_id=ADMIN_ID,
    )
    # Never approved -- build_candidate must refuse.
    candidate_service = ProductionRagCandidateService(settings)
    with pytest.raises(ValidationError):
        candidate_service.build_candidate(request["public_id"], admin_id=ADMIN_ID)


def test_activation_blocks_when_candidate_not_validated(settings: Settings) -> None:
    request, _records = _approved_promotion_request(settings)
    candidate_service = ProductionRagCandidateService(settings)
    candidate = candidate_service.build_candidate(request["public_id"], admin_id=ADMIN_ID)

    activation_service = ProductionRagActivationService(settings)
    with pytest.raises(ValidationError):
        activation_service.activate(candidate["public_id"], admin_id=ADMIN_ID)
