from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.services.incremental_training_checkpoint_service import (
    IncrementalTrainingCheckpointService,
)
from backend.services.incremental_training_comparison_service import (
    IncrementalTrainingComparisonService,
    classify_regression,
)
from backend.services.incremental_training_execution_service import (
    IncrementalTrainingExecutionService,
)
from backend.services.incremental_training_run_approval_service import (
    IncrementalTrainingRunApprovalService,
)
from tests.backend.test_incremental_training_run_and_execution import (
    _TINY_CONFIG,
    _materialized_promotion,
    _pretraining_refs,
)
from tests.backend.test_training_suitability_and_transformation import ADMIN_ID


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "incremental_training_checkpoint.db",
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


def _run_continued_pretraining(
    settings: Settings, refs: dict, promotion: dict, total_steps: int
) -> dict:
    approval_service = IncrementalTrainingRunApprovalService(settings)
    request = approval_service.create_run_request(
        promotion["public_id"],
        {
            "training_strategy": "continued_pretraining",
            "tokenizer_version_public_id": refs["tokenizer"],
            "configuration": {
                **_TINY_CONFIG, "total_steps": total_steps,
                "core_model_version_public_id": refs["model"],
            },
        },
        admin_id=ADMIN_ID,
    )
    approval_service.submit_for_approval(request["public_id"], admin_id=ADMIN_ID)
    approval = approval_service.request_approval(request["public_id"], admin_id=ADMIN_ID)
    approval_service.approve(approval["public_id"], admin_id=ADMIN_ID)
    execution_service = IncrementalTrainingExecutionService(settings)
    return execution_service.start_run(approval["public_id"], admin_id=ADMIN_ID)


def _first_checkpoint(settings: Settings, run: dict) -> dict:
    training = TrainingIncrementalRepository(settings.resolved_database_path)
    return training.list_checkpoints(run["public_id"])[0]


def test_verify_then_evaluate_checkpoint(settings: Settings) -> None:
    promotion = _materialized_promotion(settings, candidate_count=3)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    run = _run_continued_pretraining(settings, refs, promotion, total_steps=2)
    checkpoint = _first_checkpoint(settings, run)
    assert checkpoint["status"] == "created"

    checkpoint_service = IncrementalTrainingCheckpointService(settings)
    verified = checkpoint_service.verify(checkpoint["public_id"], admin_id=ADMIN_ID)
    assert verified["status"] == "verified"

    result = checkpoint_service.evaluate(checkpoint["public_id"], admin_id=ADMIN_ID)
    assert result["checkpoint"]["status"] == "evaluated"
    assert len(result["evaluations"]) == 2
    evaluation_types = {item["evaluation_type"] for item in result["evaluations"]}
    assert evaluation_types == {"validation_loss", "quality_readiness"}


def test_evaluate_rejects_unverified_checkpoint(settings: Settings) -> None:
    promotion = _materialized_promotion(settings, candidate_count=3)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    run = _run_continued_pretraining(settings, refs, promotion, total_steps=2)
    checkpoint = _first_checkpoint(settings, run)

    checkpoint_service = IncrementalTrainingCheckpointService(settings)
    with pytest.raises(ValidationError):
        checkpoint_service.evaluate(checkpoint["public_id"], admin_id=ADMIN_ID)


def test_classify_regression_thresholds() -> None:
    def _delta(left: float, right: float) -> dict:
        return {"fields": {"final_validation_loss": {"left": left, "right": right}}}

    assert classify_regression(_delta(0.5, 1.0)) == "improved"
    assert classify_regression(_delta(1.0, 1.0)) == "unchanged"
    assert classify_regression(_delta(1.10, 1.0)) == "minor_regression"
    assert classify_regression(_delta(1.50, 1.0)) == "major_regression"
    assert classify_regression(_delta(None, 1.0)) == "not_comparable"


def test_compare_checkpoints_end_to_end(settings: Settings) -> None:
    promotion = _materialized_promotion(settings, candidate_count=3)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    run_a = _run_continued_pretraining(settings, refs, promotion, total_steps=1)
    run_b = _run_continued_pretraining(settings, refs, promotion, total_steps=2)
    checkpoint_a = _first_checkpoint(settings, run_a)
    checkpoint_b = _first_checkpoint(settings, run_b)

    checkpoint_service = IncrementalTrainingCheckpointService(settings)
    for checkpoint in (checkpoint_a, checkpoint_b):
        checkpoint_service.verify(checkpoint["public_id"], admin_id=ADMIN_ID)
        checkpoint_service.evaluate(checkpoint["public_id"], admin_id=ADMIN_ID)

    comparison_service = IncrementalTrainingComparisonService(settings)
    comparison = comparison_service.compare(
        checkpoint_b["public_id"], checkpoint_a["public_id"], admin_id=ADMIN_ID,
    )
    assert comparison["comparison_type"] == "general_comparison"
    assert comparison["result_status"] in (
        "improved", "unchanged", "minor_regression", "major_regression", "not_comparable",
    )
    assert comparison["parent_checkpoint_public_id"] == checkpoint_a["public_id"]

    forgetting = comparison_service.compare_to_parent(
        checkpoint_b["public_id"], checkpoint_a["public_id"], admin_id=ADMIN_ID,
    )
    assert forgetting["comparison_type"] == "forgetting_check"


def test_compare_requires_evaluated_checkpoint(settings: Settings) -> None:
    promotion = _materialized_promotion(settings, candidate_count=3)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    run_a = _run_continued_pretraining(settings, refs, promotion, total_steps=1)
    run_b = _run_continued_pretraining(settings, refs, promotion, total_steps=1)
    checkpoint_a = _first_checkpoint(settings, run_a)
    checkpoint_b = _first_checkpoint(settings, run_b)

    comparison_service = IncrementalTrainingComparisonService(settings)
    with pytest.raises(ValidationError):
        comparison_service.compare(
            checkpoint_b["public_id"], checkpoint_a["public_id"], admin_id=ADMIN_ID,
        )
