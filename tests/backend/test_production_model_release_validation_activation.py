import hashlib
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.models.inference_runtime import (
    AssignmentApprovalCreate,
    AssignmentCreate,
)
from backend.models.model_release import (
    ApprovalCreate,
    ModelReleaseCreate,
    ModelReleaseFamilyCreate,
)
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService
from backend.services.model_release_service import ModelReleaseService
from backend.services.production_model_activation_service import ProductionModelActivationService
from backend.services.production_model_canary_service import ProductionModelCanaryService
from backend.services.production_model_release_approval_service import (
    ProductionModelReleaseApprovalService,
)
from backend.services.production_model_release_request_service import (
    ProductionModelReleaseRequestService,
)
from backend.services.production_model_release_validation_service import (
    ProductionModelReleaseValidationService,
)
from backend.services.production_rollback_service import ProductionRollbackPlanService
from tests.backend.test_incremental_training_review_report_and_acceptance import (
    _passing_human_review,
    _verified_and_evaluated_checkpoint,
)
from tests.backend.test_training_suitability_and_transformation import ADMIN_ID

# GOV-26/GOV-26c (P0-1): release and non-public inference-assignment
# approvals now require 2 distinct authenticated admins by default -- this
# file's own shared helpers below use these extra identities purely as
# test scaffolding, not as a subject of any assertion in this file.
SECOND_ADMIN_ID = "00000000-0000-0000-0000-0000000000f2"
THIRD_ADMIN_ID = "00000000-0000-0000-0000-0000000000f3"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "production_model_activation.db",
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


def _insert_evaluation_evidence(
    settings: Settings, candidate_core_model_public_id: str, suffix: str
) -> str:
    """A real, passing model_evaluation_runs/model_chat_readiness_assessments/
    model_evaluation_manifests chain -- required for `assess_eligibility()`
    to consider evaluation evidence present, mirroring
    tests/backend/test_inference_runtime_api.py::_insert_evaluation_evidence."""

    run_public_id = f"92000000-0000-0000-0000-00000000{suffix}0{suffix}0"
    with database_connection(settings.resolved_database_path) as connection:
        candidate_row = connection.execute(
            "SELECT id,tokenizer_version_id FROM core_model_versions WHERE public_id=?",
            (candidate_core_model_public_id,),
        ).fetchone()
        checkpoint_row = connection.execute(
            "SELECT id FROM pretraining_checkpoints ORDER BY id DESC LIMIT 1"
        ).fetchone()
        connection.execute(
            """INSERT OR IGNORE INTO model_evaluation_suites(public_id,name,version,status,
            created_by_admin_public_id) VALUES (?,?,?,?,?)""",
            ("92000000-0000-0000-0000-000000000001", "phase15-suite", "v1", "active", ADMIN_ID),
        )
        suite_id = connection.execute(
            "SELECT id FROM model_evaluation_suites WHERE public_id=?",
            ("92000000-0000-0000-0000-000000000001",),
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO model_evaluation_runs(public_id,model_evaluation_suite_id,
            candidate_core_model_version_id,checkpoint_id,tokenizer_version_id,status,
            fixture_count,completed_fixture_count,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                run_public_id, suite_id, candidate_row["id"], checkpoint_row["id"],
                candidate_row["tokenizer_version_id"], "completed", 6, 6, ADMIN_ID,
            ),
        )
        run_id = connection.execute(
            "SELECT id FROM model_evaluation_runs WHERE public_id=?", (run_public_id,)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO model_chat_readiness_assessments(public_id,model_evaluation_run_id,
            status,created_by_admin_public_id) VALUES (?,?,?,?)""",
            (
                f"92000000-0000-0000-0000-00000000{suffix}1{suffix}1",
                run_id, "evaluation_passed_with_limits", ADMIN_ID,
            ),
        )
        manifest_json = dumps_json({"run": run_public_id})
        connection.execute(
            """INSERT INTO model_evaluation_manifests(public_id,model_evaluation_run_id,
            manifest_json,manifest_checksum_sha256) VALUES (?,?,?,?)""",
            (
                f"92000000-0000-0000-0000-00000000{suffix}2{suffix}2",
                run_id, manifest_json, hashlib.sha256(manifest_json.encode()).hexdigest(),
            ),
        )
        connection.commit()
    return run_public_id


def _validated_release_request(
    settings: Settings, *, suffix: str = "1", checkpoint: dict | None = None
) -> dict:
    if checkpoint is None:
        checkpoint = _accepted_checkpoint(settings)
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    family = release_service.create_family(
        ModelReleaseFamilyCreate(name=f"Brud Core Test {suffix}", slug=f"brud-core-test-{suffix}"),
        ADMIN_ID,
    )
    request_service = ProductionModelReleaseRequestService(settings)
    eligibility_service = request_service._eligibility  # noqa: SLF001
    eligibility = eligibility_service.check_eligibility(checkpoint["public_id"])
    run_public_id = _insert_evaluation_evidence(
        settings, eligibility["model_candidate_public_id"], suffix=suffix,
    )
    request = request_service.create_request(
        {
            "incremental_training_checkpoint_public_id": checkpoint["public_id"],
            "model_release_family_public_id": family["public_id"],
            "release_type": "experimental",
            "model_evaluation_run_public_id": run_public_id,
        },
        admin_id=ADMIN_ID,
    )
    validation_service = ProductionModelReleaseValidationService(settings)
    result = validation_service.run_validation(request["public_id"], admin_id=ADMIN_ID)
    return result["request"]


def _approved_release_request(
    settings: Settings, *, suffix: str = "1", checkpoint: dict | None = None
) -> dict:
    validated = _validated_release_request(settings, suffix=suffix, checkpoint=checkpoint)
    assert validated["status"] == "validated", validated
    approval_service = ProductionModelReleaseApprovalService(settings)
    approval = approval_service.request_approval(validated["public_id"], admin_id=ADMIN_ID)
    approval_service.approve(approval["public_id"], admin_id=ADMIN_ID)
    repository = ProductionReadinessRepository(settings.resolved_database_path)
    return repository.get_model_release_request(validated["public_id"])


def _create_release(settings: Settings, candidate_public_id: str, version: str) -> dict:
    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    # GOV-26 (P0-1): the real, shipped default now requires 2 distinct
    # authenticated admins, not just 1 -- both approvals are pure test
    # scaffolding here, unrelated to whatever this file's own test is
    # actually asserting. GOV-33 (P0-1 Phase 15.2): ADMIN_ID is always the
    # candidate's own creator (via _validated_release_request /
    # _accepted_checkpoint) and can never approve it -- both approvals use
    # genuinely non-creator identities; ADMIN_ID is used only for
    # create_release() itself, which does not check self-approval.
    release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="first reviewer"),
        SECOND_ADMIN_ID,
    )
    release_service.submit_approval(
        candidate_public_id,
        ApprovalCreate(role="release", decision="approve", comment="second reviewer"),
        THIRD_ADMIN_ID,
    )
    return release_service.create_release(
        ModelReleaseCreate(candidate_public_id=candidate_public_id, version=version), ADMIN_ID,
    )


def _assignment_service(settings: Settings) -> ModelAssignmentService:
    runtime_repository = InferenceRuntimeRepository(settings.resolved_database_path)
    release_repository = ModelReleaseRepository(settings.resolved_database_path)
    runtime_service = InferenceRuntimeService(runtime_repository, release_repository, settings)
    return ModelAssignmentService(
        runtime_repository, release_repository, runtime_service, settings,
    )


def _profile(settings: Settings) -> str:
    from backend.models.inference_runtime import RuntimeProfileCreate

    runtime_repository = InferenceRuntimeRepository(settings.resolved_database_path)
    release_repository = ModelReleaseRepository(settings.resolved_database_path)
    runtime_service = InferenceRuntimeService(runtime_repository, release_repository, settings)
    profile = runtime_service.create_profile(
        RuntimeProfileCreate(
            name="cpu-profile",
            maximum_context_length=64,
            maximum_new_tokens=32,
            minimum_available_memory_bytes=0,
            minimum_available_disk_bytes=0,
        ),
        ADMIN_ID,
    )
    return profile["public_id"]


def _approved_admin_diagnostic_assignment(
    settings: Settings, assignment_service: ModelAssignmentService, release_public_id: str,
    profile_public_id: str,
) -> str:
    assignment = assignment_service.create_assignment(
        AssignmentCreate(
            scope="admin_diagnostic",
            release_public_id=release_public_id,
            runtime_profile_public_id=profile_public_id,
        ),
        ADMIN_ID,
    )
    assignment_service.validate_assignment(assignment["public_id"], ADMIN_ID)
    # GOV-31/GOV-32 (P0-1): the creator (ADMIN_ID) can no longer approve
    # their own assignment by default, and GOV-26c separately now requires
    # 2 distinct approvers -- both non-creator identities here are pure
    # test scaffolding, unrelated to whatever this file's own test is
    # actually asserting.
    assignment_service.approve_assignment(
        assignment["public_id"],
        AssignmentApprovalCreate(role="release", decision="approve", comment="first reviewer"),
        SECOND_ADMIN_ID,
    )
    assignment_service.approve_assignment(
        assignment["public_id"],
        AssignmentApprovalCreate(role="release", decision="approve", comment="second reviewer"),
        THIRD_ADMIN_ID,
    )
    return assignment["public_id"]


# -- validation ------------------------------------------------------------------------------


def test_run_validation_marks_request_validated(settings: Settings) -> None:
    request = _validated_release_request(settings)
    assert request["status"] == "validated"


def test_run_validation_fails_without_linked_candidate(settings: Settings) -> None:
    checkpoint = _accepted_checkpoint(settings)
    request_service = ProductionModelReleaseRequestService(settings)
    request = request_service.create_request(
        {"incremental_training_checkpoint_public_id": checkpoint["public_id"]}, admin_id=ADMIN_ID,
    )
    validation_service = ProductionModelReleaseValidationService(settings)
    with pytest.raises(ValidationError):
        validation_service.run_validation(request["public_id"], admin_id=ADMIN_ID)


# -- approval --------------------------------------------------------------------------------


def test_approval_flow_binds_fingerprint_and_approves(settings: Settings) -> None:
    validated = _validated_release_request(settings)
    approval_service = ProductionModelReleaseApprovalService(settings)
    approval = approval_service.request_approval(validated["public_id"], admin_id=ADMIN_ID)
    assert approval["target_fingerprint"]
    approved = approval_service.approve(approval["public_id"], admin_id=ADMIN_ID)
    assert approved["approved_by_admin_id"] == ADMIN_ID
    repository = ProductionReadinessRepository(settings.resolved_database_path)
    request = repository.get_model_release_request(validated["public_id"])
    assert request["status"] == "approved"


# -- activation --------------------------------------------------------------------------------


def test_activation_requires_a_verified_rollback_plan(settings: Settings) -> None:
    approved = _approved_release_request(settings)
    rollback_service = ProductionRollbackPlanService(settings)
    draft_plan = rollback_service.create_plan(
        {"target_type": "model", "rollback_steps": ["rollback_execute"]}, admin_id=ADMIN_ID,
    )
    activation_service = ProductionModelActivationService(settings)
    with pytest.raises(ValidationError):
        activation_service.activate(
            approved["public_id"], "irrelevant-assignment-id", draft_plan["public_id"],
            admin_id=ADMIN_ID,
        )


def test_activation_rejects_wrong_target_type(settings: Settings) -> None:
    approved = _approved_release_request(settings)
    rollback_service = ProductionRollbackPlanService(settings)
    rag_plan = rollback_service.create_plan(
        {"target_type": "rag", "rollback_steps": ["reactivate_previous_profile"]},
        admin_id=ADMIN_ID,
    )
    rollback_service.validate_plan(rag_plan["public_id"], admin_id=ADMIN_ID)
    activation_service = ProductionModelActivationService(settings)
    with pytest.raises(ValidationError):
        activation_service.activate(
            approved["public_id"], "irrelevant-assignment-id", rag_plan["public_id"],
            admin_id=ADMIN_ID,
        )


def test_full_activation_runs_a_real_post_activation_health_check(settings: Settings) -> None:
    approved = _approved_release_request(settings)
    repository = ProductionReadinessRepository(settings.resolved_database_path)
    created_release = _create_release(
        settings, approved["model_release_candidate_public_id"], "0.1.0-test",
    )
    assert created_release["status"] == "released"

    assignment_service = _assignment_service(settings)
    profile_public_id = _profile(settings)
    assignment_public_id = _approved_admin_diagnostic_assignment(
        settings, assignment_service, created_release["public_id"], profile_public_id,
    )

    rollback_service = ProductionRollbackPlanService(settings)
    plan = rollback_service.create_plan(
        {"target_type": "model", "rollback_steps": ["rollback_execute"]}, admin_id=ADMIN_ID,
    )
    rollback_service.validate_plan(plan["public_id"], admin_id=ADMIN_ID)

    activation_service = ProductionModelActivationService(settings)
    result = activation_service.activate(
        approved["public_id"], assignment_public_id, plan["public_id"], admin_id=ADMIN_ID,
    )
    assert result["activated"] is True
    assert result["health"]["overall_status"] == "healthy"

    request = repository.get_model_release_request(approved["public_id"])
    assert request["status"] == "activated"
    checks = repository.list_model_post_activation_checks(approved["public_id"])
    assert any(c["check_type"] == "post_activation_health" for c in checks)


def test_rollback_reactivates_the_previous_version(settings: Settings) -> None:
    from backend.models.inference_runtime import AssignmentPatch

    checkpoint = _accepted_checkpoint(settings)
    approved = _approved_release_request(settings, checkpoint=checkpoint)
    repository = ProductionReadinessRepository(settings.resolved_database_path)
    release_a = _create_release(
        settings, approved["model_release_candidate_public_id"], "0.1.0-rollback-a",
    )

    assignment_service = _assignment_service(settings)
    profile_public_id = _profile(settings)
    assignment_public_id = _approved_admin_diagnostic_assignment(
        settings, assignment_service, release_a["public_id"], profile_public_id,
    )

    rollback_service = ProductionRollbackPlanService(settings)
    plan_a = rollback_service.create_plan(
        {"target_type": "model", "rollback_steps": ["rollback_execute"]}, admin_id=ADMIN_ID,
    )
    rollback_service.validate_plan(plan_a["public_id"], admin_id=ADMIN_ID)

    activation_service = ProductionModelActivationService(settings)
    activation_service.activate(
        approved["public_id"], assignment_public_id, plan_a["public_id"], admin_id=ADMIN_ID,
    )
    version_1_public_id = assignment_service.versions(assignment_public_id)["items"][0][
        "public_id"
    ]

    approved_2 = _approved_release_request(settings, suffix="2", checkpoint=checkpoint)
    release_b = _create_release(
        settings, approved_2["model_release_candidate_public_id"], "0.1.0-rollback-b",
    )
    assignment_service.patch_assignment(
        assignment_public_id, AssignmentPatch(release_public_id=release_b["public_id"]), ADMIN_ID,
    )
    assignment_service.validate_assignment(assignment_public_id, ADMIN_ID)
    # GOV-31/GOV-32 (P0-1): the assignment's creator (ADMIN_ID) can no
    # longer approve it themselves by default. Approval records are tied to
    # the assignment's own id, not reset per validate/patch round -- the
    # first round's 2 distinct approvers (from _approved_admin_diagnostic_assignment,
    # above) already satisfy GOV-26c's floor of 2, so exactly one additional
    # non-creator approval is enough to re-satisfy the policy for this "v2" round.
    assignment_service.approve_assignment(
        assignment_public_id,
        AssignmentApprovalCreate(role="release", decision="approve", comment="v2"),
        SECOND_ADMIN_ID,
    )

    plan_b = rollback_service.create_plan(
        {
            "target_type": "model",
            "current_active_version": version_1_public_id,
            "rollback_steps": ["rollback_execute"],
        },
        admin_id=ADMIN_ID,
    )
    rollback_service.validate_plan(plan_b["public_id"], admin_id=ADMIN_ID)
    activation_service.activate(
        approved_2["public_id"], assignment_public_id, plan_b["public_id"], admin_id=ADMIN_ID,
    )
    assert (
        repository.get_model_release_request(approved_2["public_id"])["status"] == "activated"
    )

    result = activation_service.rollback(
        approved_2["public_id"], assignment_public_id, plan_b["public_id"], admin_id=ADMIN_ID,
    )
    assert result["rolled_back"] is True
    assert result["current_version_public_id"] == version_1_public_id
    assert result["assignment"]["release_public_id"] == release_a["public_id"]

    request_2 = repository.get_model_release_request(approved_2["public_id"])
    assert request_2["status"] == "superseded"
    plan_b_after = rollback_service.get_plan(plan_b["public_id"])
    assert plan_b_after["status"] == "used"


# -- canary --------------------------------------------------------------------------------


def test_canary_start_execute_stop(settings: Settings) -> None:
    approved = _approved_release_request(settings)
    created_release = _create_release(
        settings, approved["model_release_candidate_public_id"], "0.1.0-canary",
    )

    assignment_service = _assignment_service(settings)
    profile_public_id = _profile(settings)
    canary_assignment = assignment_service.create_assignment(
        AssignmentCreate(
            scope="internal_canary",
            release_public_id=created_release["public_id"],
            runtime_profile_public_id=profile_public_id,
            context_policy={"acknowledge_missing_human_review": True},
        ),
        ADMIN_ID,
    )
    assignment_service.validate_assignment(canary_assignment["public_id"], ADMIN_ID)
    # GOV-31/GOV-32/GOV-26c (P0-1): same reasoning as above -- the creator
    # cannot self-approve by default, and 2 distinct approvers are required.
    assignment_service.approve_assignment(
        canary_assignment["public_id"],
        AssignmentApprovalCreate(role="release", decision="approve", comment="first reviewer"),
        SECOND_ADMIN_ID,
    )
    assignment_service.approve_assignment(
        canary_assignment["public_id"],
        AssignmentApprovalCreate(role="release", decision="approve", comment="second reviewer"),
        THIRD_ADMIN_ID,
    )
    assignment_service.activate_assignment(canary_assignment["public_id"], ADMIN_ID)

    canary_service = ProductionModelCanaryService(settings)
    started = canary_service.start(
        approved["public_id"], canary_assignment["public_id"], admin_id=ADMIN_ID,
        percentage=100, max_request_count=10,
    )
    assert started["run_status"] == "running"

    repository = ProductionReadinessRepository(settings.resolved_database_path)
    assert repository.get_model_release_request(approved["public_id"])["status"] == "canary"

    executed = canary_service.execute(
        approved["public_id"], canary_assignment["public_id"],
        [f"prompt {i}" for i in range(5)], admin_id=ADMIN_ID,
    )
    assert executed["requests_executed"] == 5

    stopped = canary_service.stop(
        approved["public_id"], canary_assignment["public_id"], admin_id=ADMIN_ID,
        reason="test_stop",
    )
    assert stopped["run_status"] == "stopped"
