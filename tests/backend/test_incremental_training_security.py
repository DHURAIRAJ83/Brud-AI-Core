import re
from datetime import UTC, datetime, timedelta
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
from backend.services.incremental_training_execution_service import (
    IncrementalTrainingExecutionService,
)
from backend.services.incremental_training_report_service import IncrementalTrainingReportService
from backend.services.incremental_training_run_approval_service import (
    IncrementalTrainingRunApprovalService,
)
from backend.services.training_resource_preview_service import TrainingResourcePreviewService
from tests.backend.test_incremental_training_checkpoint_and_comparison import (
    _first_checkpoint,
    _run_continued_pretraining,
)
from tests.backend.test_incremental_training_review_report_and_acceptance import (
    _passing_human_review,
)
from tests.backend.test_incremental_training_run_and_execution import (
    _TINY_CONFIG,
    _materialized_promotion,
    _pretraining_refs,
)
from tests.backend.test_training_suitability_and_transformation import ADMIN_ID

_PHASE14_SERVICE_FILES = list(
    (Path(__file__).resolve().parents[2] / "backend" / "services").glob(
        "incremental_training_*.py"
    )
) + list(
    (Path(__file__).resolve().parents[2] / "backend" / "services").glob("training_*.py")
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "incremental_training_security.db",
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


# -- static guards: the two production-adjacent lines this phase must never cross ------------


def test_no_phase14_service_ever_writes_lifecycle_status_active() -> None:
    pattern = re.compile(r"lifecycle_status\s*=\s*['\"]active['\"]")
    for path in _PHASE14_SERVICE_FILES:
        text = path.read_text(encoding="utf-8")
        assert not pattern.search(text), f"{path.name} appears to write lifecycle_status='active'"


def test_no_phase14_service_ever_imports_model_release_service() -> None:
    import_pattern = re.compile(
        r"^\s*(from\s+\S+\s+)?import\s+.*\bModelReleaseService\b", re.MULTILINE
    )
    for path in _PHASE14_SERVICE_FILES:
        text = path.read_text(encoding="utf-8")
        assert not import_pattern.search(text), f"{path.name} imports ModelReleaseService"


def test_no_phase14_service_ever_writes_inference_model_assignments() -> None:
    for path in _PHASE14_SERVICE_FILES:
        text = path.read_text(encoding="utf-8")
        assert "inference_model_assignments" not in text, (
            f"{path.name} references inference_model_assignments -- production inference "
            "routing must never be touched by this phase"
        )


# -- resource bounds (Step 36: hard-enforce, addressing Phase 13's deferred gap) --------------


def test_resource_preview_blocks_unsafe_batch_size(settings: Settings) -> None:
    service = TrainingResourcePreviewService(settings)
    with pytest.raises(ValidationError):
        service.build_preview(
            "continued_pretraining", {**_TINY_CONFIG, "batch_size": 999_999},
        )


def test_resource_preview_blocks_excessive_gradient_accumulation(settings: Settings) -> None:
    service = TrainingResourcePreviewService(settings)
    with pytest.raises(ValidationError):
        service.build_preview(
            "continued_pretraining", {**_TINY_CONFIG, "gradient_accumulation_steps": 999_999},
        )


# -- staleness / expiry guards ------------------------------------------------------------------


def test_expired_run_approval_blocks_start_and_cannot_be_overridden(settings: Settings) -> None:
    promotion = _materialized_promotion(settings, candidate_count=3)
    refs = _pretraining_refs(settings, promotion["dataset_version_public_id"])
    approval_service = IncrementalTrainingRunApprovalService(settings)
    request = approval_service.create_run_request(
        promotion["public_id"],
        {
            "training_strategy": "continued_pretraining",
            "tokenizer_version_public_id": refs["tokenizer"],
            "configuration": {**_TINY_CONFIG, "core_model_version_public_id": refs["model"]},
        },
        admin_id=ADMIN_ID,
    )
    approval_service.submit_for_approval(request["public_id"], admin_id=ADMIN_ID)
    approval = approval_service.request_approval(request["public_id"], admin_id=ADMIN_ID)
    already_past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    approval_service.approve(approval["public_id"], admin_id=ADMIN_ID, expires_at=already_past)

    execution_service = IncrementalTrainingExecutionService(settings)
    with pytest.raises(ValidationError, match="expired"):
        execution_service.start_run(approval["public_id"], admin_id=ADMIN_ID)

    training = TrainingIncrementalRepository(settings.resolved_database_path)
    assert training.get_run_approval(approval["public_id"])["status"] == "expired"


def test_expired_promotion_request_blocks_materialize(settings: Settings) -> None:
    from backend.services.training_dataset_promotion_service import TrainingDatasetPromotionService
    from backend.services.training_suitability_service import TrainingSuitabilityError
    from tests.backend.test_training_contamination_replay_and_promotion import _approved_candidate

    assessment, candidate = _approved_candidate(settings)
    service = TrainingDatasetPromotionService(settings)
    request = service.create_request(
        assessment["public_id"], {"candidate_public_ids": [candidate["public_id"]]},
        admin_id=ADMIN_ID,
    )
    service.submit_for_approval(request["public_id"], admin_id=ADMIN_ID)
    already_past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    service.approve(request["public_id"], admin_id=ADMIN_ID, expires_at=already_past)

    with pytest.raises(TrainingSuitabilityError, match="expired"):
        service.materialize(request["public_id"], admin_id=ADMIN_ID)

    training = TrainingIncrementalRepository(settings.resolved_database_path)
    assert training.get_promotion_request(request["public_id"])["status"] == "expired"


# -- major_regression is a hard, non-overridable block on checkpoint acceptance --------------


def test_major_regression_comparison_blocks_checkpoint_acceptance_even_with_override(
    settings: Settings,
) -> None:
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

    # Fabricate a major_regression comparison directly -- exercising the real
    # regression-classification thresholds already has its own dedicated
    # unit tests; this test only needs a major_regression row to exist so it
    # can prove the acceptance-blocking behavior around it.
    training = TrainingIncrementalRepository(settings.resolved_database_path)
    training.add_comparison(
        checkpoint_b["public_id"],
        {
            "parent_checkpoint_public_id": checkpoint_a["public_id"],
            "comparison_type": "forgetting_check",
            "result_status": "major_regression",
            "metrics": {"final_validation_loss": {"left": 5.0, "right": 1.0}},
        },
    )

    _passing_human_review(settings, checkpoint_b["public_id"])
    report_service = IncrementalTrainingReportService(settings)
    report = report_service.finalize_report(
        run_b["public_id"], checkpoint_b["public_id"], admin_id=ADMIN_ID,
    )
    assert report["checkpoint_recommendation"] == "reject"

    acceptance_service = IncrementalTrainingCheckpointAcceptanceService(settings)
    with pytest.raises(ValidationError, match="major_regression"):
        acceptance_service.accept(
            checkpoint_b["public_id"], report["public_id"],
            {
                "decision": "accepted_candidate",
                "reason": "attempting to override a major regression",
                "override_comment": "I am overriding this on purpose",
            },
            admin_id=ADMIN_ID,
        )

    training = TrainingIncrementalRepository(settings.resolved_database_path)
    assert training.list_acceptances(checkpoint_b["public_id"]) == []
