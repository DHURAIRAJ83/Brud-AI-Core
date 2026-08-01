from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.phase2 import AdminApprovalRepository
from backend.models.domain import AdminApprovalCreate
from backend.services.admin_assistant_service import (
    PROPOSAL_PREVIEW_TTL_HOURS,
    AdminAssistantError,
    AdminAssistantService,
)
from core_model.admin_assistant.action_registry import ACTION_DEFINITIONS
from core_model.admin_assistant.lifecycle import derive_lifecycle_state

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
OTHER_ADMIN_ID = "00000000-0000-0000-0000-000000000002"


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "lifecycle.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


@pytest.fixture
def service(settings: Settings) -> AdminAssistantService:
    return AdminAssistantService(settings)


def test_action_executors_match_action_registry_exactly() -> None:
    from backend.services.admin_assistant_service import ACTION_EXECUTORS

    assert set(ACTION_EXECUTORS) == {action.action_type for action in ACTION_DEFINITIONS}


def test_propose_stamps_risk_level_preview_stale_check_and_expiry(
    service: AdminAssistantService,
) -> None:
    proposal = service.propose(
        action_type="governance_target_approval_override",
        target_type="governance_entity",
        target_public_id="dataset-record-lifecycle-1",
        request_payload={
            "entity_type": "dataset_record",
            "target_use": "rag",
            "decision": "allowed",
            "reason": "verified manually",
        },
        requested_by=ADMIN_ID,
        summary="Override rag eligibility",
    )
    assert proposal.risk_level == "high"
    assert proposal.preview["current_state"]["decision"] == "not_requested"
    assert proposal.preview["proposed_state"]["decision"] == "allowed"
    assert proposal.stale_check == {
        "decision": "not_requested",
        "decision_code": "NOT_REQUESTED",
        "is_override": False,
    }
    assert proposal.expires_at is not None
    delta = proposal.expires_at - datetime.now(UTC)
    assert timedelta(hours=PROPOSAL_PREVIEW_TTL_HOURS) - timedelta(minutes=1) < delta


def test_propose_requires_reason_for_actions_that_require_one(
    service: AdminAssistantService,
) -> None:
    with pytest.raises(AdminAssistantError):
        service.propose(
            action_type="governance_target_approval_override",
            target_type="governance_entity",
            target_public_id="dataset-record-lifecycle-2",
            request_payload={
                "entity_type": "dataset_record",
                "target_use": "rag",
                "decision": "allowed",
                "reason": "   ",
            },
            requested_by=ADMIN_ID,
            summary="Missing reason",
        )


def test_review_rejects_stale_proposal_when_target_changed_between_propose_and_confirm(
    service: AdminAssistantService,
) -> None:
    target_public_id = "dataset-record-lifecycle-3"
    proposal = service.propose(
        action_type="governance_target_approval_override",
        target_type="governance_entity",
        target_public_id=target_public_id,
        request_payload={
            "entity_type": "dataset_record",
            "target_use": "rag",
            "decision": "allowed",
            "reason": "initial review",
        },
        requested_by=ADMIN_ID,
        summary="Override rag eligibility",
    )

    # Simulate the target changing underneath the proposal: another admin
    # records a real governance decision for the same entity/target_use
    # via the real service, independent of this proposal.
    from backend.services.governance_service import GovernanceApprovalService

    GovernanceApprovalService(service.settings).override(
        "dataset_record",
        target_public_id,
        "rag",
        "blocked",
        reason="found a licensing problem",
        admin_id=OTHER_ADMIN_ID,
    )

    with pytest.raises(AdminAssistantError, match="changed since this proposal"):
        service.review(
            proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None
        )

    # The proposal must remain pending -- rejected-for-staleness never
    # silently consumes the pending state.
    reloaded = service.get_proposal(proposal.public_id)
    assert reloaded.status == "pending"


def test_review_succeeds_when_target_unchanged(service: AdminAssistantService) -> None:
    target_public_id = "dataset-record-lifecycle-4"
    proposal = service.propose(
        action_type="governance_target_approval_override",
        target_type="governance_entity",
        target_public_id=target_public_id,
        request_payload={
            "entity_type": "dataset_record",
            "target_use": "rag",
            "decision": "allowed",
            "reason": "verified",
        },
        requested_by=ADMIN_ID,
        summary="Override rag eligibility",
    )
    reviewed = service.review(
        proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment="agreed"
    )
    assert reviewed.status == "approved"
    assert reviewed.execution_status == "pending"


def test_execute_records_verified_post_execution_state_in_audit(
    service: AdminAssistantService,
) -> None:
    target_public_id = "dataset-record-lifecycle-5"
    proposal = service.propose(
        action_type="governance_target_approval_override",
        target_type="governance_entity",
        target_public_id=target_public_id,
        request_payload={
            "entity_type": "dataset_record",
            "target_use": "rag",
            "decision": "allowed",
            "reason": "verified",
        },
        requested_by=ADMIN_ID,
        summary="Override rag eligibility",
    )
    service.review(proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)
    executed = service.execute(proposal.public_id, executor_public_id=ADMIN_ID)
    assert executed.execution_status == "succeeded"
    assert executed.execution_result["decision"] == "allowed"

    from backend.database.repositories import AuditLogRepository

    events = AuditLogRepository(service.database_path).recent(limit=50)
    executed_event = next(
        event
        for event in events
        if event.event_type == "admin_assistant_proposal_executed"
        and event.resource_public_id == proposal.public_id
    )
    assert executed_event.metadata["verified_state"]["decision"] == "allowed"
    assert bool(executed_event.metadata["verified_state"]["is_override"]) is True


def test_cancel_withdraws_a_pending_proposal(service: AdminAssistantService) -> None:
    proposal = service.propose(
        action_type="dataset_source_update",
        target_type="dataset_source",
        target_public_id="does-not-exist-yet",
        request_payload={"name": "New Name"},
        requested_by=ADMIN_ID,
        summary="Rename source",
    )
    cancelled = service.cancel(proposal.public_id, cancelled_by=ADMIN_ID, reason="changed my mind")
    assert cancelled.status == "cancelled"

    with pytest.raises(AdminAssistantError):
        service.review(proposal.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)


def test_cancel_a_non_pending_proposal_fails(service: AdminAssistantService) -> None:
    proposal = service.propose(
        action_type="dataset_source_update",
        target_type="dataset_source",
        target_public_id="does-not-exist-yet-2",
        request_payload={"name": "New Name"},
        requested_by=ADMIN_ID,
        summary="Rename source",
    )
    service.review(proposal.public_id, decision="rejected", reviewed_by=ADMIN_ID, comment=None)
    with pytest.raises(Exception):  # noqa: B017 -- either NotFoundError or ValidationError bubbles up
        service.cancel(proposal.public_id, cancelled_by=ADMIN_ID, reason="too late")


def test_pending_proposal_past_expiry_is_lazily_expired_on_read(settings: Settings) -> None:
    repository = AdminApprovalRepository(settings.resolved_database_path)
    created = repository.create(
        AdminApprovalCreate(
            action_type="dataset_source_update",
            target_type="dataset_source",
            target_public_id="src-expiry-test",
            request_payload={"name": "X"},
            requested_by=ADMIN_ID,
            summary="",
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    reloaded = repository.get_by_public_id(created.public_id)
    assert reloaded.status == "expired"


def test_expired_proposal_cannot_be_approved(settings: Settings) -> None:
    repository = AdminApprovalRepository(settings.resolved_database_path)
    created = repository.create(
        AdminApprovalCreate(
            action_type="dataset_source_update",
            target_type="dataset_source",
            target_public_id="src-expiry-test-2",
            request_payload={"name": "X"},
            requested_by=ADMIN_ID,
            summary="",
            expires_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    service = AdminAssistantService(settings)
    with pytest.raises(AdminAssistantError):
        service.review(created.public_id, decision="approved", reviewed_by=ADMIN_ID, comment=None)


@pytest.mark.parametrize(
    ("status", "execution_status", "expired", "expected"),
    [
        ("pending", "not_applicable", False, "awaiting_confirmation"),
        ("pending", "not_applicable", True, "expired"),
        ("approved", "not_applicable", False, "confirmed"),
        ("approved", "pending", False, "executing"),
        ("approved", "succeeded", False, "completed"),
        ("approved", "failed", False, "failed"),
        ("rejected", "not_applicable", False, "rejected"),
        ("cancelled", "not_applicable", False, "cancelled"),
        ("expired", "not_applicable", False, "expired"),
    ],
)
def test_derive_lifecycle_state(status, execution_status, expired, expected) -> None:
    now = datetime.now(UTC)
    expires_at = (now - timedelta(minutes=1)) if expired else (now + timedelta(hours=1))
    assert (
        derive_lifecycle_state(
            status=status, execution_status=execution_status, expires_at=expires_at, now=now
        )
        == expected
    )
