import sqlite3
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.services.incremental_training_checkpoint_acceptance_service import (
    IncrementalTrainingCheckpointAcceptanceService,
)
from backend.services.incremental_training_checkpoint_service import (
    IncrementalTrainingCheckpointService,
)
from backend.services.incremental_training_human_review_service import (
    IncrementalTrainingHumanReviewService,
)
from backend.services.incremental_training_report_service import IncrementalTrainingReportService
from tests.backend.test_incremental_training_checkpoint_and_comparison import (
    _first_checkpoint,
    _run_continued_pretraining,
)
from tests.backend.test_incremental_training_run_and_execution import (
    _materialized_promotion,
    _pretraining_refs,
)
from tests.backend.test_training_suitability_and_transformation import ADMIN_ID


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "incremental_training_acceptance.db",
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


def _verified_and_evaluated_checkpoint(settings: Settings) -> tuple[dict, dict]:
    promotion = _materialized_promotion(settings, candidate_count=3)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    run = _run_continued_pretraining(settings, refs, promotion, total_steps=2)
    checkpoint = _first_checkpoint(settings, run)
    checkpoint_service = IncrementalTrainingCheckpointService(settings)
    checkpoint_service.verify(checkpoint["public_id"], admin_id=ADMIN_ID)
    checkpoint_service.evaluate(checkpoint["public_id"], admin_id=ADMIN_ID)
    training = TrainingIncrementalRepository(settings.resolved_database_path)
    return run, training.get_checkpoint(checkpoint["public_id"])


def _passing_human_review(settings: Settings, checkpoint_public_id: str) -> dict:
    service = IncrementalTrainingHumanReviewService(settings)
    return service.add_review(
        checkpoint_public_id,
        {
            "prompt_text": "தமிழில் ஒரு வாக்கியம் எழுது.",
            "decision": "pass",
            "tamil_fluency": True,
            "english_fluency": True,
            "instruction_following": True,
            "hallucination_risk": False,
            "regression": False,
        },
        admin_id=ADMIN_ID,
    )


def test_human_review_requires_evaluated_checkpoint(settings: Settings) -> None:
    promotion = _materialized_promotion(settings, candidate_count=3)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    run = _run_continued_pretraining(settings, refs, promotion, total_steps=2)
    checkpoint = _first_checkpoint(settings, run)

    review_service = IncrementalTrainingHumanReviewService(settings)
    with pytest.raises(ValidationError):
        review_service.add_review(
            checkpoint["public_id"], {"prompt_text": "hi", "decision": "pass"}, admin_id=ADMIN_ID,
        )


def test_finalize_report_computes_recommendation(settings: Settings) -> None:
    run, checkpoint = _verified_and_evaluated_checkpoint(settings)
    _passing_human_review(settings, checkpoint["public_id"])

    report_service = IncrementalTrainingReportService(settings)
    report = report_service.finalize_report(
        run["public_id"], checkpoint["public_id"], admin_id=ADMIN_ID,
    )
    assert report["report_version"] == 1
    assert report["checkpoint_recommendation"] in (
        "accept_candidate", "accept_with_conditions", "reject", "needs_more_training",
        "needs_more_evaluation",
    )
    assert report["production_release_readiness"] == "not_assessed"
    assert report["report"]["checkpoint_public_id"] == checkpoint["public_id"]

    second = report_service.finalize_report(
        run["public_id"], checkpoint["public_id"], admin_id=ADMIN_ID,
    )
    assert second["report_version"] == 2


def test_accept_checkpoint_registers_model_candidate(settings: Settings) -> None:
    run, checkpoint = _verified_and_evaluated_checkpoint(settings)
    _passing_human_review(settings, checkpoint["public_id"])
    report_service = IncrementalTrainingReportService(settings)
    report = report_service.finalize_report(
        run["public_id"], checkpoint["public_id"], admin_id=ADMIN_ID,
    )

    acceptance_service = IncrementalTrainingCheckpointAcceptanceService(settings)
    acceptance = acceptance_service.accept(
        checkpoint["public_id"], report["public_id"],
        {"decision": "accepted_candidate", "reason": "meets bar for this test"},
        admin_id=ADMIN_ID,
    )
    assert acceptance["decision"] == "accepted_candidate"
    assert acceptance["model_candidate_public_id"]

    training = TrainingIncrementalRepository(settings.resolved_database_path)
    updated_checkpoint = training.get_checkpoint(checkpoint["public_id"])
    assert updated_checkpoint["status"] == "accepted_candidate"

    with sqlite3.connect(settings.resolved_database_path) as connection:
        row = connection.execute(
            "SELECT lifecycle_status FROM core_model_versions WHERE public_id=?",
            (acceptance["model_candidate_public_id"],),
        ).fetchone()
    assert row[0] == "staging"


def test_accept_requires_non_stale_latest_report(settings: Settings) -> None:
    run, checkpoint = _verified_and_evaluated_checkpoint(settings)
    _passing_human_review(settings, checkpoint["public_id"])
    report_service = IncrementalTrainingReportService(settings)
    stale_report = report_service.finalize_report(
        run["public_id"], checkpoint["public_id"], admin_id=ADMIN_ID,
    )
    report_service.finalize_report(run["public_id"], checkpoint["public_id"], admin_id=ADMIN_ID)

    acceptance_service = IncrementalTrainingCheckpointAcceptanceService(settings)
    with pytest.raises(ValidationError):
        acceptance_service.accept(
            checkpoint["public_id"], stale_report["public_id"],
            {"decision": "accepted_candidate", "reason": "using a stale report"},
            admin_id=ADMIN_ID,
        )


def test_accept_rejects_unknown_decision(settings: Settings) -> None:
    run, checkpoint = _verified_and_evaluated_checkpoint(settings)
    _passing_human_review(settings, checkpoint["public_id"])
    report_service = IncrementalTrainingReportService(settings)
    report = report_service.finalize_report(
        run["public_id"], checkpoint["public_id"], admin_id=ADMIN_ID,
    )
    acceptance_service = IncrementalTrainingCheckpointAcceptanceService(settings)
    with pytest.raises(ValidationError):
        acceptance_service.accept(
            checkpoint["public_id"], report["public_id"],
            {"decision": "not_a_real_decision", "reason": "x"},
            admin_id=ADMIN_ID,
        )


def test_reject_checkpoint_does_not_register_model_candidate(settings: Settings) -> None:
    run, checkpoint = _verified_and_evaluated_checkpoint(settings)
    _passing_human_review(settings, checkpoint["public_id"])
    report_service = IncrementalTrainingReportService(settings)
    report = report_service.finalize_report(
        run["public_id"], checkpoint["public_id"], admin_id=ADMIN_ID,
    )
    acceptance_service = IncrementalTrainingCheckpointAcceptanceService(settings)
    acceptance = acceptance_service.accept(
        checkpoint["public_id"], report["public_id"],
        {"decision": "rejected", "reason": "not good enough for this test"},
        admin_id=ADMIN_ID,
    )
    assert acceptance["decision"] == "rejected"
    assert acceptance["model_candidate_public_id"] is None

    training = TrainingIncrementalRepository(settings.resolved_database_path)
    updated_checkpoint = training.get_checkpoint(checkpoint["public_id"])
    assert updated_checkpoint["status"] == "rejected"
