from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.services.admin_assistant_service import ACTION_EXECUTORS, AdminAssistantService
from core_model.admin_assistant.action_registry import ACTION_DEFINITIONS, is_blocked_action_type
from tests.backend.test_production_model_release_validation_activation import (
    _accepted_checkpoint,
)
from tests.backend.test_production_rag_eligibility_and_promotion import (
    _insert_knowledge_space,
    _mark_eligible_for_production_rag,
)
from tests.backend.test_training_suitability_and_transformation import (
    ADMIN_ID,
    _build_accepted_experiment,
)

_PHASE15_ACTION_TYPES = (
    "create_production_rag_promotion_request",
    "submit_production_rag_promotion_request",
    "create_production_model_release_request",
    "submit_production_model_release_request",
    "check_production_release_candidate_artifact_security",
    "run_production_api_abuse_readiness_check",
    "run_production_secret_redaction_check",
    "compile_production_readiness_report",
    # Phase 15A Step 28-29
    "run_production_backup_readiness_check",
    "run_production_restore_readiness_check",
    "assess_production_backup_encryption",
    "encrypt_production_backup",
    "verify_production_encrypted_restore",
)

# The Admin Assistant must never approve a production RAG/model release,
# build or validate a RAG candidate, start a canary, activate or roll
# back anything, or submit the final production-acceptance review --
# only a human Admin, acting directly through the Production Readiness
# dashboard/API, can.
_FORBIDDEN_PHASE15_MARKERS = (
    "approve", "activate", "canary", "rollback", "acceptance_review", "build_candidate",
    "validate_candidate",
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "production_readiness_admin_assistant.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        tokenizer_corpus_dir=tmp_path / "tokenizer_corpus",
        tokenizer_dir=tmp_path / "tokenizers",
        core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        release_artifact_dir=tmp_path / "release_artifacts",
        release_bundle_dir=tmp_path / "release_bundles",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def test_phase15_action_types_are_registered_and_never_blocked() -> None:
    known = {action.action_type for action in ACTION_DEFINITIONS}
    for action_type in _PHASE15_ACTION_TYPES:
        assert action_type in known
        assert action_type in ACTION_EXECUTORS
        assert not is_blocked_action_type(action_type)


def test_no_phase15_admin_assistant_action_can_approve_or_activate_production() -> None:
    for action_type in _PHASE15_ACTION_TYPES:
        assert not any(marker in action_type for marker in _FORBIDDEN_PHASE15_MARKERS), (
            f"{action_type} looks like it could approve/activate/roll back production -- the "
            "Admin Assistant must never be given such an action"
        )


def test_create_and_submit_production_rag_promotion_request_via_admin_assistant(
    settings: Settings,
) -> None:
    built = _build_accepted_experiment(settings)
    _mark_eligible_for_production_rag(settings, built["experiment"]["public_id"])
    knowledge_space_id = _insert_knowledge_space(settings)
    service = AdminAssistantService(settings)

    proposal = service.propose(
        action_type="create_production_rag_promotion_request",
        target_type="rag_sandbox_experiment",
        target_public_id=built["experiment"]["public_id"],
        request_payload={"knowledge_space_public_id": knowledge_space_id},
        requested_by=ADMIN_ID,
        summary="Propose a production RAG promotion request",
    )
    assert proposal.risk_level == "moderate"
    service.review(proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=ADMIN_ID)
    assert executed.execution_status == "succeeded"
    assert executed.execution_result["status"] == "draft"
    promotion_public_id = executed.execution_result["public_id"]

    submit_proposal = service.propose(
        action_type="submit_production_rag_promotion_request",
        target_type="production_rag_promotion_request",
        target_public_id=promotion_public_id,
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Submit the promotion request for Admin approval",
    )
    service.review(
        submit_proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
    )
    submitted = service.execute(submit_proposal.public_id, executor_public_id=ADMIN_ID)
    assert submitted.execution_status == "succeeded"
    assert submitted.execution_result["status"] == "awaiting_review"


def test_create_and_submit_production_model_release_request_via_admin_assistant(
    settings: Settings,
) -> None:
    checkpoint = _accepted_checkpoint(settings)
    service = AdminAssistantService(settings)

    proposal = service.propose(
        action_type="create_production_model_release_request",
        target_type="incremental_training_checkpoint",
        target_public_id=checkpoint["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Propose a production model release request",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=ADMIN_ID)
    assert executed.execution_status == "succeeded"
    assert executed.execution_result["status"] == "draft"
    release_request_public_id = executed.execution_result["public_id"]

    submit_proposal = service.propose(
        action_type="submit_production_model_release_request",
        target_type="production_model_release_request",
        target_public_id=release_request_public_id,
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Submit the release request for Admin approval",
    )
    service.review(
        submit_proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
    )
    submitted = service.execute(submit_proposal.public_id, executor_public_id=ADMIN_ID)
    assert submitted.execution_status == "succeeded"
    assert submitted.execution_result["status"] == "awaiting_review"


def test_production_readiness_system_checks_via_admin_assistant(settings: Settings) -> None:
    service = AdminAssistantService(settings)

    for action_type in (
        "run_production_api_abuse_readiness_check",
        "run_production_secret_redaction_check",
    ):
        proposal = service.propose(
            action_type=action_type,
            target_type="production_readiness_system",
            target_public_id="system",
            request_payload={},
            requested_by=ADMIN_ID,
            summary="Run a production readiness safety check",
        )
        assert proposal.risk_level == "low"
        service.review(
            proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
        )
        executed = service.execute(proposal.public_id, executor_public_id=ADMIN_ID)
        assert executed.execution_status == "succeeded"
        assert executed.execution_result["result_status"] == "passed"

    report_proposal = service.propose(
        action_type="compile_production_readiness_report",
        target_type="production_readiness_system",
        target_public_id="system",
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Compile the production readiness report",
    )
    service.review(
        report_proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
    )
    report_executed = service.execute(report_proposal.public_id, executor_public_id=ADMIN_ID)
    assert report_executed.execution_status == "succeeded"
    assert report_executed.execution_result["recommendation"] == "not_ready"


def test_production_backup_and_encryption_checks_via_admin_assistant(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import base64
    import os
    import shutil

    settings.resolved_backup_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        settings.resolved_database_path,
        settings.resolved_backup_dir / "brud_ai_before_v38_20260101000000.db",
    )
    monkeypatch.setenv(
        settings.backup_encryption_key_env_var,
        base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
    )
    service = AdminAssistantService(settings)

    def run(action_type: str, expected_risk: str = "low") -> dict:
        proposal = service.propose(
            action_type=action_type,
            target_type="production_readiness_system",
            target_public_id="system",
            request_payload={},
            requested_by=ADMIN_ID,
            summary=f"Run {action_type}",
        )
        assert proposal.risk_level == expected_risk
        service.review(proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)
        executed = service.execute(proposal.public_id, executor_public_id=ADMIN_ID)
        assert executed.execution_status == "succeeded", executed.execution_result
        return executed.execution_result

    backup_result = run("run_production_backup_readiness_check")
    assert backup_result["result_status"] in {"passed", "passed_with_warning"}

    restore_result = run("run_production_restore_readiness_check")
    assert restore_result["result_status"] == "passed"

    assessment_before = run("assess_production_backup_encryption")
    assert assessment_before["result_status"] == "not_encrypted"

    encrypt_result = run("encrypt_production_backup", expected_risk="moderate")
    assert encrypt_result["result_status"] == "encrypted"

    assessment_after = run("assess_production_backup_encryption")
    assert assessment_after["result_status"] == "encrypted"

    restore_verify_result = run("verify_production_encrypted_restore")
    assert restore_verify_result["result_status"] == "passed"


def test_check_release_candidate_artifact_security_via_admin_assistant(settings: Settings) -> None:
    from backend.services.production_model_release_request_service import (
        ProductionModelReleaseRequestService,
    )

    checkpoint = _accepted_checkpoint(settings)
    request_service = ProductionModelReleaseRequestService(settings)
    request = request_service.create_request(
        {"incremental_training_checkpoint_public_id": checkpoint["public_id"]}, admin_id=ADMIN_ID,
    )
    # No family/candidate was supplied, so there is no release candidate to
    # check yet -- register one directly via the existing model registry,
    # mirroring what an Admin would do outside the assistant.
    from backend.database.repositories.model_release import ModelReleaseRepository
    from backend.models.model_release import ModelReleaseCandidateCreate, ModelReleaseFamilyCreate
    from backend.services.model_release_service import ModelReleaseService

    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    family = release_service.create_family(
        ModelReleaseFamilyCreate(name="Assistant Test", slug="assistant-test"), ADMIN_ID,
    )
    repository = ProductionReadinessRepository(settings.resolved_database_path)
    eligibility = request_service._eligibility.check_eligibility(  # noqa: SLF001
        checkpoint["public_id"]
    )
    candidate = release_service.create_candidate(
        ModelReleaseCandidateCreate(
            model_release_family_public_id=family["public_id"],
            core_model_version_public_id=eligibility["model_candidate_public_id"],
        ),
        ADMIN_ID,
    )
    release_service.collect_artifacts(candidate["public_id"], ADMIN_ID)
    del repository, request

    service = AdminAssistantService(settings)
    proposal = service.propose(
        action_type="check_production_release_candidate_artifact_security",
        target_type="model_release_candidate",
        target_public_id=candidate["public_id"],
        request_payload={},
        requested_by=ADMIN_ID,
        summary="Independently re-verify this candidate's collected artifacts",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=ADMIN_ID)
    assert executed.execution_status == "succeeded"
    assert executed.execution_result["items"]
