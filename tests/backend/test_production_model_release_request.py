from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.models.model_release import ModelReleaseFamilyCreate
from backend.services.model_release_service import ModelReleaseService
from backend.services.production_model_release_request_service import (
    ProductionModelReleaseEligibilityService,
    ProductionModelReleaseRequestService,
)
from tests.backend.test_incremental_training_checkpoint_and_comparison import (
    _first_checkpoint,
    _run_continued_pretraining,
)
from tests.backend.test_incremental_training_review_report_and_acceptance import (
    _passing_human_review,
    _verified_and_evaluated_checkpoint,
)
from tests.backend.test_incremental_training_run_and_execution import (
    _materialized_promotion,
    _pretraining_refs,
)
from tests.backend.test_training_suitability_and_transformation import ADMIN_ID


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "production_model_release.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        tokenizer_corpus_dir=tmp_path / "tokenizer_corpus",
        tokenizer_dir=tmp_path / "tokenizers",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _accepted_checkpoint(settings: Settings) -> dict:
    from backend.services.incremental_training_checkpoint_acceptance_service import (
        IncrementalTrainingCheckpointAcceptanceService,
    )
    from backend.services.incremental_training_report_service import (
        IncrementalTrainingReportService,
    )

    run, checkpoint = _verified_and_evaluated_checkpoint(settings)
    _passing_human_review(settings, checkpoint["public_id"])
    report_service = IncrementalTrainingReportService(settings)
    report = report_service.finalize_report(
        run["public_id"], checkpoint["public_id"], admin_id=ADMIN_ID,
    )
    acceptance_service = IncrementalTrainingCheckpointAcceptanceService(settings)
    acceptance_service.accept(
        checkpoint["public_id"], report["public_id"],
        {"decision": "accepted_candidate", "reason": "meets bar for this test"},
        admin_id=ADMIN_ID,
    )
    return checkpoint


def _register_family(settings: Settings) -> str:
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    family = release_service.create_family(
        ModelReleaseFamilyCreate(name="Brud Core Test", slug="brud-core-test"), ADMIN_ID,
    )
    return family["public_id"]


# -- eligibility -----------------------------------------------------------------------------


def test_eligibility_blocks_unevaluated_checkpoint(settings: Settings) -> None:
    promotion = _materialized_promotion(settings, candidate_count=3)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    run = _run_continued_pretraining(settings, refs, promotion, total_steps=2)
    checkpoint = _first_checkpoint(settings, run)

    service = ProductionModelReleaseEligibilityService(settings)
    result = service.check_eligibility(checkpoint["public_id"])
    assert result["eligible"] is False


def test_eligibility_passes_for_accepted_checkpoint(settings: Settings) -> None:
    checkpoint = _accepted_checkpoint(settings)
    service = ProductionModelReleaseEligibilityService(settings)
    result = service.check_eligibility(checkpoint["public_id"])
    assert result["eligible"] is True, result["blocking_reasons"]
    assert result["model_candidate_public_id"]


# -- release request ---------------------------------------------------------------------------


def test_create_request_blocked_when_not_eligible(settings: Settings) -> None:
    promotion = _materialized_promotion(settings, candidate_count=3)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    run = _run_continued_pretraining(settings, refs, promotion, total_steps=2)
    checkpoint = _first_checkpoint(settings, run)

    service = ProductionModelReleaseRequestService(settings)
    with pytest.raises(ValidationError):
        service.create_request(
            {"incremental_training_checkpoint_public_id": checkpoint["public_id"]},
            admin_id=ADMIN_ID,
        )


def test_create_request_links_a_real_model_release_candidate(settings: Settings) -> None:
    checkpoint = _accepted_checkpoint(settings)
    family_id = _register_family(settings)

    service = ProductionModelReleaseRequestService(settings)
    request = service.create_request(
        {
            "incremental_training_checkpoint_public_id": checkpoint["public_id"],
            "model_release_family_public_id": family_id,
            "release_type": "experimental",
        },
        admin_id=ADMIN_ID,
    )
    assert request["status"] == "draft"
    assert request["model_release_candidate_public_id"]
    assert request["model_candidate_public_id"]

    submitted = service.submit_for_review(request["public_id"], admin_id=ADMIN_ID)
    assert submitted["status"] == "awaiting_review"


def test_create_request_without_family_records_governance_row_only(settings: Settings) -> None:
    checkpoint = _accepted_checkpoint(settings)
    service = ProductionModelReleaseRequestService(settings)
    request = service.create_request(
        {"incremental_training_checkpoint_public_id": checkpoint["public_id"]},
        admin_id=ADMIN_ID,
    )
    assert request["model_release_candidate_public_id"] is None
    assert request["model_candidate_public_id"]
