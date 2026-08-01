from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.services.admin_assistant_service import ACTION_EXECUTORS, AdminAssistantService
from core_model.admin_assistant.action_registry import ACTION_DEFINITIONS, is_blocked_action_type
from tests.backend.test_training_suitability_and_transformation import (
    ADMIN_ID,
    _build_accepted_experiment,
)

_PHASE14_ACTION_TYPES = (
    "assess_language_sample_suitability",
    "run_language_sample_suitability_check",
    "acknowledge_language_sample_assessment",
    "transform_language_sample_candidate",
    "review_language_sample_candidate",
    "create_replay_data_plan",
    "create_dataset_promotion_request",
    "submit_dataset_promotion_request",
)

# The Admin Assistant must never be able to start, approve, or execute a
# training run, or accept/register a checkpoint -- only a human Admin,
# acting directly through the Incremental Training dashboard/API, can.
_FORBIDDEN_ASSISTANT_ACTION_SUBSTRINGS = (
    "run_request", "run_approval", "start_run", "approve_dataset_promotion",
    "materialize", "verify_checkpoint", "evaluate_checkpoint", "accept_checkpoint",
    "register_model_candidate",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "incremental_training_admin_assistant.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def test_phase14_action_types_are_registered_and_never_blocked() -> None:
    known = {action.action_type for action in ACTION_DEFINITIONS}
    for action_type in _PHASE14_ACTION_TYPES:
        assert action_type in known
        assert action_type in ACTION_EXECUTORS
        assert not is_blocked_action_type(action_type)


def test_no_admin_assistant_action_can_run_or_approve_training() -> None:
    for action in ACTION_DEFINITIONS:
        lowered = action.action_type.lower()
        assert not any(marker in lowered for marker in _FORBIDDEN_ASSISTANT_ACTION_SUBSTRINGS), (
            f"{action.action_type} looks like it could start/approve/execute training or "
            "accept a checkpoint -- the Admin Assistant must never be given such an action"
        )


def test_assess_and_run_suitability_check_via_admin_assistant(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    service = AdminAssistantService(settings)

    proposal = service.propose(
        action_type="assess_language_sample_suitability",
        target_type="rag_sandbox_experiment",
        target_public_id=built["experiment"]["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Assess this accepted RAG sandbox experiment for training suitability",
    )
    assert proposal.risk_level == "low"
    service.review(proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=ADMIN_ID)
    assert executed.execution_status == "succeeded"
    assessment_public_id = executed.execution_result["public_id"]

    run_proposal = service.propose(
        action_type="run_language_sample_suitability_check",
        target_type="training_data_assessment",
        target_public_id=assessment_public_id,
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Run the suitability check",
    )
    service.review(run_proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)
    run_executed = service.execute(run_proposal.public_id, executor_public_id=ADMIN_ID)
    assert run_executed.execution_status == "succeeded"
    assert run_executed.execution_result["status"] == "assessed"


def test_transform_and_review_candidate_via_admin_assistant(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    service = AdminAssistantService(settings)
    training = TrainingIncrementalRepository(settings.resolved_database_path)

    assess_proposal = service.propose(
        action_type="assess_language_sample_suitability",
        target_type="rag_sandbox_experiment",
        target_public_id=built["experiment"]["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Assess",
    )
    service.review(
        assess_proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
    )
    assessment = service.execute(assess_proposal.public_id, executor_public_id=ADMIN_ID)
    assessment_public_id = assessment.execution_result["public_id"]

    run_proposal = service.propose(
        action_type="run_language_sample_suitability_check",
        target_type="training_data_assessment",
        target_public_id=assessment_public_id,
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Run",
    )
    service.review(run_proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)
    service.execute(run_proposal.public_id, executor_public_id=ADMIN_ID)

    item = training.list_items(assessment_public_id)[0]

    transform_proposal = service.propose(
        action_type="transform_language_sample_candidate",
        target_type="training_data_assessment_item",
        target_public_id=item["public_id"],
        request_payload={
            "transformation_type": "instruction_response_pair",
            "prompt_text": "தமிழ் என்றால் என்ன?",
            "assistant_text": "தமிழ் ஒரு திராவிட மொழி.",
            "language": "ta",
            "source_checksum": "chk-record-0",
        },
        requested_by=ADMIN_ID,
        summary="Transform this item into a candidate",
    )
    service.review(
        transform_proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
    )
    transformed = service.execute(transform_proposal.public_id, executor_public_id=ADMIN_ID)
    assert transformed.execution_status == "succeeded"
    candidate_public_id = transformed.execution_result["public_id"]
    assert transformed.execution_result["review_status"] == "pending_review"

    review_proposal = service.propose(
        action_type="review_language_sample_candidate",
        target_type="training_example_candidate",
        target_public_id=candidate_public_id,
        request_payload={"decision": "approved", "reason": "looks correct"},
        requested_by=ADMIN_ID,
        summary="Approve this candidate",
    )
    service.review(
        review_proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
    )
    reviewed = service.execute(review_proposal.public_id, executor_public_id=ADMIN_ID)
    assert reviewed.execution_status == "succeeded"
    assert reviewed.execution_result["review_status"] == "approved"
