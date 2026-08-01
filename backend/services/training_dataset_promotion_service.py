"""Phase 14 Steps 6/10: contamination-gated dataset promotion and
immutable training dataset version creation.

A promotion request selects a set of *approved*
`training_example_candidates`, re-runs the contamination/leakage
recheck (Step 6 -- `TrainingContaminationService`), and -- only once
separately Admin-approved -- materializes those candidates as real,
approved `dataset_records` via the *existing, unmodified*
`DatasetService`, then hands them to the *existing, unmodified*
`DatasetVersioningService.create_build()` (scoped with
`selection_filters={"include_public_ids": [...]}`, the mechanism
`GovernedBuildService` already established) to produce one immutable
dataset version. Approving a promotion request never itself creates a
training run -- that is `IncrementalTrainingRunService`'s own,
separate gate. See docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.models.dataset_versions import BuildCreate, BuildRunRequest, SplitConfiguration
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.dataset_service import DatasetService
from backend.services.dataset_versioning import DatasetVersioningService
from backend.services.training_contamination_service import TrainingContaminationService
from backend.services.training_suitability_service import TrainingSuitabilityError

logger = logging.getLogger(__name__)

_VALID_LANGUAGES = {"ta", "en", "tgl", "mixed", "unknown"}

_RECORD_TYPE_BY_TRANSFORMATION = {
    "clean_language_sample": "pretrain",
    "question_answer_pair": "instruction",
    "summary_pair": "instruction",
    "correction_pair": "instruction",
    "instruction_response_pair": "instruction",
    "translation_pair": "translation",
    "tanglish_normalization_pair": "tanglish_pair",
    "conversation_turn_sequence": "chat",
}


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
                event_type=f"training_dataset_promotion_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="training_dataset_promotion_request",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("training_dataset_promotion_audit_write_failed", extra={"action": action})


def _fingerprint(candidate_public_ids: list[str]) -> str:
    return hashlib.sha256(dumps_json(sorted(candidate_public_ids)).encode()).hexdigest()


def _candidate_to_record_fields(candidate: dict[str, Any]) -> dict[str, Any]:
    transformation_type = candidate["transformation_type"]
    record_type = _RECORD_TYPE_BY_TRANSFORMATION.get(transformation_type, "instruction")
    prompt = candidate["prompt_text"] or ""
    assistant = candidate["assistant_text"] or ""
    language = candidate["language"] if candidate["language"] in _VALID_LANGUAGES else "unknown"

    if record_type == "pretrain":
        text = " ".join(part for part in (prompt, assistant) if part)
        return {
            "record_type": record_type, "language": language,
            "instruction": None, "input_text": None, "output_text": text, "metadata": {},
        }
    if record_type == "tanglish_pair":
        return {
            "record_type": record_type, "language": language,
            "instruction": None, "input_text": prompt, "output_text": assistant,
            "normalized_input": assistant, "metadata": {},
        }
    if record_type == "translation":
        source_lang, _, target_lang = candidate["task"].partition("->")
        metadata = {
            "source_language": source_lang.strip() or "unknown",
            "target_language": target_lang.strip() or language,
        }
        return {
            "record_type": record_type, "language": language,
            "instruction": None, "input_text": prompt, "output_text": assistant,
            "metadata": metadata,
        }
    if record_type == "chat":
        return {
            "record_type": record_type, "language": language,
            "instruction": None, "input_text": prompt, "output_text": assistant, "metadata": {},
        }
    return {
        "record_type": record_type, "language": language,
        "instruction": prompt, "input_text": None, "output_text": assistant, "metadata": {},
    }


class TrainingDatasetPromotionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)
        self._dataset_admin_repository = DatasetAdminRepository(settings.resolved_database_path)
        self._dataset = DatasetService(self._dataset_admin_repository)
        self._quality_repository = DatasetQualityRepository(settings.resolved_database_path)
        self._versioning = DatasetVersioningService(self._quality_repository, settings)
        self._contamination = TrainingContaminationService(settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def create_request(
        self, assessment_public_id: str, values: dict[str, Any], *, admin_id: str
    ) -> dict[str, Any]:
        self._training.get_assessment(assessment_public_id)
        candidate_public_ids: list[str] = values.get("candidate_public_ids") or []
        if not candidate_public_ids:
            raise ValidationError(
                "at least one approved training example candidate is required for promotion"
            )
        candidates = [self._training.get_candidate(cid) for cid in candidate_public_ids]
        not_approved = [c["public_id"] for c in candidates if c["review_status"] != "approved"]
        if not_approved:
            raise TrainingSuitabilityError(
                f"only human-approved candidates may be promoted, not: {not_approved}"
            )

        recheck = self._contamination.recheck_candidates(candidate_public_ids)
        if recheck["blocking_candidate_ids"]:
            raise TrainingSuitabilityError(
                "contamination recheck confirmed overlap for candidates: "
                f"{recheck['blocking_candidate_ids']} -- confirmed overlap always blocks "
                "training eligibility"
            )

        request = self._training.create_promotion_request(
            assessment_public_id,
            {
                "selected_candidate_ids": candidate_public_ids,
                "replay_plan_public_id": values.get("replay_plan_public_id"),
                "requested_by_admin_public_id": admin_id,
            },
        )
        manifest = {
            "contamination_recheck": recheck,
            "candidate_checksums": {c["public_id"]: c["candidate_checksum"] for c in candidates},
        }
        self._training.update_promotion_request(
            request["public_id"], {"lineage_manifest_json": dumps_json(manifest)}
        )
        _audit(
            self._audit, action="create_request", actor_reference=admin_id,
            resource_public_id=request["public_id"], outcome=AuditOutcome.SUCCESS,
            metadata={"candidate_count": len(candidate_public_ids)},
        )
        return self._training.get_promotion_request(request["public_id"])

    def submit_for_approval(self, promotion_public_id: str, *, admin_id: str) -> dict[str, Any]:
        current = self._training.get_promotion_request(promotion_public_id)
        if current["status"] != "draft":
            raise ValidationError("only a draft promotion request can be submitted for approval")
        updated = self._training.update_promotion_request(
            promotion_public_id, {"status": "awaiting_approval"}
        )
        _audit(
            self._audit, action="submit_for_approval", actor_reference=admin_id,
            resource_public_id=promotion_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return updated

    def approve(
        self, promotion_public_id: str, *, admin_id: str, expires_at: str | None = None
    ) -> dict[str, Any]:
        current = self._training.get_promotion_request(promotion_public_id)
        if current["status"] not in ("draft", "awaiting_approval"):
            raise ValidationError("only a draft or awaiting-approval request may be approved")
        fingerprint = _fingerprint(current["selected_candidate_ids"])
        updated = self._training.approve_promotion_request(
            promotion_public_id, approved_by_admin_id=admin_id, expires_at=expires_at,
            target_fingerprint=fingerprint,
        )
        _audit(
            self._audit, action="approve", actor_reference=admin_id,
            resource_public_id=promotion_public_id, outcome=AuditOutcome.SUCCESS,
        )
        return updated

    def materialize(self, promotion_public_id: str, *, admin_id: str) -> dict[str, Any]:
        request = self._training.get_promotion_request(promotion_public_id)
        if request["status"] != "approved":
            raise ValidationError("only an approved promotion request can be materialized")
        if request["expires_at"] and request["expires_at"] < datetime.now(UTC).isoformat():
            self._training.update_promotion_request(promotion_public_id, {"status": "expired"})
            raise TrainingSuitabilityError(
                "this promotion request's approval has expired -- create and approve a new one"
            )
        fingerprint = _fingerprint(request["selected_candidate_ids"])
        if fingerprint != request["target_fingerprint"]:
            self._training.update_promotion_request(promotion_public_id, {"status": "superseded"})
            raise TrainingSuitabilityError(
                "the selected candidates changed since approval -- this request is stale"
            )

        source = self._dataset.create_source(
            ManualSourceCreate(
                name=f"phase14-incremental-training-promotion-{promotion_public_id[:8]}",
                description="Phase 14 governed training-example promotion",
                language="unknown",
                licence_status="approved",
            ),
            admin_id,
        )

        new_record_public_ids: list[str] = []
        for candidate_public_id in request["selected_candidate_ids"]:
            candidate = self._training.get_candidate(candidate_public_id)
            fields = _candidate_to_record_fields(candidate)
            record = self._dataset.create_record(
                RecordCreate(
                    source_public_id=source["public_id"],
                    record_type=fields["record_type"],
                    language=fields["language"],
                    instruction=fields.get("instruction"),
                    input_text=fields.get("input_text"),
                    output_text=fields.get("output_text"),
                    normalized_input=fields.get("normalized_input"),
                    metadata={
                        **fields.get("metadata", {}),
                        "phase14_candidate_public_id": candidate_public_id,
                        "phase14_promotion_public_id": promotion_public_id,
                    },
                ),
                admin_id,
            )
            self._dataset.transition(record["public_id"], "pending_review", "edit", None, admin_id)
            self._dataset.transition(record["public_id"], "approved", "approve", None, admin_id)
            with self._training.transaction() as connection:
                row = connection.execute(
                    "SELECT id FROM dataset_records WHERE public_id=?", (record["public_id"],)
                ).fetchone()
            self._training.link_dataset_record(candidate_public_id, row["id"])
            new_record_public_ids.append(record["public_id"])

        replay_record_public_ids: list[str] = []
        if request["replay_plan_public_id"]:
            replay_plan = self._training.get_replay_plan(request["replay_plan_public_id"])
            replay_record_public_ids = list(replay_plan["replay_record_ids"])

        all_public_ids = new_record_public_ids + replay_record_public_ids
        build = self._versioning.create_build(
            BuildCreate(
                dataset_name=f"phase14-incremental-{promotion_public_id[:8]}",
                dataset_version="v1",
                description="Phase 14 incremental training dataset promotion",
                selection_filters={"include_public_ids": all_public_ids},
                split_configuration=SplitConfiguration(),
            ),
            admin_id,
        )
        self._versioning.validate_build(build["public_id"], admin_id)
        completed_build = self._versioning.run_build(
            build["public_id"], BuildRunRequest(confirm=True, allow_warnings=False), admin_id
        )
        dataset_version_public_id = completed_build["dataset_version_public_id"]

        with self._training.transaction() as connection:
            version_row = connection.execute(
                "SELECT id FROM dataset_versions WHERE public_id=?", (dataset_version_public_id,)
            ).fetchone()
            version_id = version_row["id"]
            split_checksums = {}
            for split_name in ("train", "validation", "test"):
                rows = connection.execute(
                    """SELECT r.content_hash FROM dataset_version_items i
                    JOIN dataset_records r ON r.id = i.dataset_record_id
                    WHERE i.dataset_version_id=? AND i.split=? ORDER BY r.content_hash""",
                    (version_id, split_name),
                ).fetchall()
                split_checksums[split_name] = hashlib.sha256(
                    "".join(row["content_hash"] for row in rows).encode()
                ).hexdigest()

        manifest = dict(request["lineage_manifest"])
        manifest["new_dataset_record_public_ids"] = new_record_public_ids
        manifest["replay_dataset_record_public_ids"] = replay_record_public_ids
        manifest["dataset_version_public_id"] = dataset_version_public_id
        self._training.update_promotion_request(
            promotion_public_id,
            {
                "status": "ready",
                "dataset_version_id": version_id,
                "train_split_checksum": split_checksums["train"],
                "validation_split_checksum": split_checksums["validation"],
                "test_split_checksum": split_checksums["test"],
                "lineage_manifest_json": dumps_json(manifest),
            },
        )
        _audit(
            self._audit, action="materialize", actor_reference=admin_id,
            resource_public_id=promotion_public_id, outcome=AuditOutcome.SUCCESS,
            metadata={
                "dataset_version_public_id": dataset_version_public_id,
                "new_record_count": len(new_record_public_ids),
                "replay_record_count": len(replay_record_public_ids),
            },
        )
        return self._training.get_promotion_request(promotion_public_id)


__all__ = ["TrainingDatasetPromotionService"]
