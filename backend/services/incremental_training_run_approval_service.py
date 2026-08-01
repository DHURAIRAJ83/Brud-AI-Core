"""Phase 14 Step 13: Training Run approval, separate from dataset
promotion approval.

A run request binds to a *materialized* (`status='ready'`) dataset
promotion request and carries its own resource preview (Step 12,
hard-enforced). Requesting an approval snapshots the run request's
current dataset version / base checkpoint / tokenizer / strategy /
configuration checksum / resource preview checksum / replay plan /
split checksums into a separate `incremental_training_run_approvals`
row, bound by a target fingerprint the schema's own
immutable-once-approved trigger then protects. Any change to the run
request after that point produces a fingerprint mismatch that
`IncrementalTrainingExecutionService.start_run()` treats as stale --
this is the Step 13 "stale-rejected on any change" requirement. See
docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.training_resource_preview_service import TrainingResourcePreviewService
from core_model.training_incremental import EXECUTABLE_TRAINING_STRATEGIES, TRAINING_STRATEGIES

logger = logging.getLogger(__name__)


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=f"incremental_training_run_approval_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="incremental_training_run_request",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception(
            "incremental_training_run_approval_audit_write_failed", extra={"action": action}
        )


def run_request_fingerprint(run_request: dict[str, Any]) -> str:
    return hashlib.sha256(
        dumps_json(
            [
                run_request["dataset_version_public_id"],
                run_request["base_checkpoint_public_id"],
                run_request["tokenizer_version_public_id"],
                run_request["training_strategy"],
                run_request["configuration_checksum"],
                run_request["resource_preview_checksum"],
            ]
        ).encode()
    ).hexdigest()


class IncrementalTrainingRunApprovalService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)
        self._preview = TrainingResourcePreviewService(settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def create_run_request(
        self, promotion_public_id: str, values: dict[str, Any], *, admin_id: str
    ) -> dict[str, Any]:
        promotion = self._training.get_promotion_request(promotion_public_id)
        if promotion["status"] != "ready":
            raise ValidationError(
                "the dataset promotion request must be materialized (status=ready) before a "
                "training run can be requested"
            )
        training_strategy = values["training_strategy"]
        if training_strategy not in TRAINING_STRATEGIES:
            raise ValidationError(f"unknown training_strategy: {training_strategy!r}")

        configuration = values.get("configuration", {})
        resource_preview: dict[str, Any] = {}
        if training_strategy in EXECUTABLE_TRAINING_STRATEGIES:
            resource_preview = self._preview.build_preview(training_strategy, configuration)

        configuration_checksum = hashlib.sha256(dumps_json(configuration).encode()).hexdigest()
        resource_preview_checksum = hashlib.sha256(
            dumps_json(resource_preview).encode()
        ).hexdigest()

        request = self._training.create_run_request(
            promotion_public_id,
            {
                "dataset_version_public_id": promotion["dataset_version_public_id"],
                "base_checkpoint_public_id": values.get("base_checkpoint_public_id"),
                "tokenizer_version_public_id": values.get("tokenizer_version_public_id"),
                "training_strategy": training_strategy,
                "configuration": configuration,
                "configuration_checksum": configuration_checksum,
                "resource_preview": resource_preview,
                "resource_preview_checksum": resource_preview_checksum,
                "execution_target": values.get("execution_target", "local_cpu"),
                "requested_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="create_run_request", actor_reference=admin_id,
            resource_public_id=request["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"training_strategy": training_strategy},
        )
        return request

    def submit_for_approval(self, run_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        current = self._training.get_run_request(run_request_public_id)
        if current["status"] != "draft":
            raise ValidationError("only a draft run request can be submitted for approval")
        updated = self._training.update_run_request(
            run_request_public_id, {"status": "awaiting_approval"}
        )
        _audit(
            self._audit, action="submit_for_approval", actor_reference=admin_id,
            resource_public_id=run_request_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return updated

    def request_approval(self, run_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        run_request = self._training.get_run_request(run_request_public_id)
        if run_request["status"] not in ("draft", "awaiting_approval"):
            raise ValidationError(
                "an approval can only be requested for a draft or awaiting-approval run request"
            )
        promotion = self._training.get_promotion_request(run_request["promotion_request_public_id"])
        fingerprint = run_request_fingerprint(run_request)
        approval = self._training.create_run_approval(
            run_request_public_id,
            {
                "replay_plan_public_id": promotion["replay_plan_public_id"],
                "train_split_checksum": promotion["train_split_checksum"],
                "validation_split_checksum": promotion["validation_split_checksum"],
                "test_split_checksum": promotion["test_split_checksum"],
                "target_fingerprint": fingerprint,
                "conditions": {},
                "requested_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit, action="request_approval", actor_reference=admin_id,
            resource_public_id=approval["public_id"], outcome=AuditOutcome.SUCCESS,
        )
        return approval

    def approve(
        self, approval_public_id: str, *, admin_id: str, expires_at: str | None = None
    ) -> dict[str, Any]:
        approval = self._training.approve_run_approval(
            approval_public_id, approved_by_admin_id=admin_id, expires_at=expires_at
        )
        self._training.update_run_request(approval["run_request_public_id"], {"status": "approved"})
        _audit(
            self._audit, action="approve", actor_reference=admin_id,
            resource_public_id=approval_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return approval

    def reject(self, approval_public_id: str, *, admin_id: str) -> dict[str, Any]:
        approval = self._training.reject_run_approval(approval_public_id)
        self._training.update_run_request(approval["run_request_public_id"], {"status": "rejected"})
        _audit(
            self._audit, action="reject", actor_reference=admin_id,
            resource_public_id=approval_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return approval


__all__ = ["IncrementalTrainingRunApprovalService", "run_request_fingerprint"]
