"""Phase 18 dataset-candidate creation, quality assessment, approval,
and export.

A dataset candidate may be created only from validated feedback plus a
completed human review plus a validated corrected response -- never
directly from raw feedback. No candidate enters a real dataset version
here: ``export_candidate`` hands an approved candidate to the existing
Phase 3 dataset-record pipeline (``DatasetService.create_record``),
which creates a ``draft`` ``dataset_records`` row subject to the same
quality/duplicate review every other record goes through. This service
never writes into a finalized ``dataset_versions`` row.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.feedback import FeedbackRepository, public_row
from backend.models.datasets import RecordCreate
from backend.models.feedback import CandidateApprovalCreate, DatasetCandidateCreate
from backend.services.dataset_service import DatasetService
from core_model.feedback import (
    BLOCKING_CONTAMINATION_STATUSES,
    CANDIDATE_TYPES,
    QUALITY_DIMENSIONS,
)
from core_model.feedback.candidate_builder import (
    build_candidate_version,
    infer_candidate_type,
    preconditions_met,
)
from core_model.feedback.contamination import check_contamination
from core_model.feedback.deduplication import (
    checksum_of,
    detect_duplicate,
    normalize_for_comparison,
)
from core_model.feedback.privacy_filter import assess_feedback_privacy
from core_model.feedback.provenance import assess_provenance
from core_model.feedback.quality_scoring import (
    assess_candidate_quality,
    overall_candidate_verdict,
)
from core_model.feedback.safety_filter import assess_feedback_safety

# Preference candidates store the rejected ("losing") output in the
# version's otherwise-unused ``input_text`` column -- reusing the
# existing schema rather than adding a preference-only column, since
# ``input_text`` is nullable and never populated for any other
# candidate type produced by this service.
_PREFERENCE_REJECTED_OUTPUT_FIELD = "input_text"


class FeedbackDatasetService:
    def __init__(
        self,
        repository: FeedbackRepository,
        dataset_repository: DatasetAdminRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.dataset_service = DatasetService(dataset_repository)
        self.settings = settings

    def create_candidate(
        self, event_public_id: str, payload: DatasetCandidateCreate, admin_id: str
    ) -> dict[str, Any]:
        if not self.settings.feedback_allow_dataset_candidates:
            raise ValidationError("dataset candidate creation is disabled by settings")

        with self.repository.transaction() as connection:
            event = self.repository.event(connection, event_public_id)
            subject = connection.execute(
                "SELECT * FROM feedback_subjects WHERE id=?", (event["subject_id"],)
            ).fetchone()
            reviews = [
                dict(row) for row in self.repository.reviews_for_event(connection, event["id"])
            ]
            latest_review = reviews[-1] if reviews else None

            correction = None
            if payload.corrected_response_public_id:
                correction = self.repository.corrected_response(
                    connection, payload.corrected_response_public_id
                )
                if correction["feedback_event_id"] != event["id"]:
                    raise ValidationError("corrected response does not belong to this event")

            ok, reason = preconditions_met(
                review_verdict=latest_review["verdict"] if latest_review else None,
                correction_validation_status=(
                    correction["validation_status"] if correction else None
                ),
                privacy_status=event["privacy_status"],
                safety_status=event["safety_status"],
            )
            if not ok:
                raise ValidationError(f"candidate preconditions not met: {reason}")

            prompt_privacy = assess_feedback_privacy(payload.prompt_text)
            if prompt_privacy["status"] == "blocked":
                raise ValidationError("prompt_text blocked by privacy scan")
            prompt_safety = assess_feedback_safety(payload.prompt_text)
            if prompt_safety["status"] == "blocked":
                raise ValidationError("prompt_text blocked by safety scan")

            candidate_type = payload.candidate_type or infer_candidate_type(
                subject_type=subject["subject_type"],
                feedback_type=event["feedback_type"],
                is_preference_pair=payload.is_preference_pair,
            )
            if candidate_type not in CANDIDATE_TYPES:
                raise ValidationError("unsupported candidate_type")

            candidate_public_id = self.repository.create_candidate(
                connection,
                {
                    "source_feedback_event_id": event["id"],
                    "source_subject_id": subject["id"],
                    "source_corrected_response_id": correction["id"] if correction else None,
                    "candidate_type": candidate_type,
                    "failed_model_version_public_id": subject["model_version_public_id"],
                    "created_by_admin_public_id": admin_id,
                },
            )
            candidate = self.repository.candidate(connection, candidate_public_id)

            prompt_text = payload.prompt_text
            output_text = correction["corrected_response_text"] if correction else ""
            input_text = payload.rejected_output_text if payload.is_preference_pair else None
            version = build_candidate_version(
                prompt_text=prompt_text,
                input_text=input_text,
                output_text=output_text,
                language=correction["language"] if correction else "unknown",
                change_reason="initial_creation",
            )
            version["created_by_admin_public_id"] = admin_id
            version_public_id = self.repository.create_candidate_version(
                connection, candidate["id"], version
            )
            version_row = self.repository.candidate_version(connection, version_public_id)
            self.repository.update_candidate(
                connection, candidate["id"],
                {"current_version_id": version_row["id"], "status": "validating"},
            )
            self.repository.update_event(connection, event["id"], {"status": "candidate_created"})
            self._audit(connection, "feedback_candidate_created", admin_id, candidate_public_id)
            return public_row(self.repository.candidate(connection, candidate_public_id))

    def get_candidate(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.candidate(connection, public_id))

    def list_candidates(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_candidates(connection)
            return {"items": [public_row(row) for row in rows]}

    def get_versions(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            rows = self.repository.versions_for_candidate(connection, candidate["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_issues(self, candidate_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            rows = self.repository.issues_for_candidate(connection, candidate["id"])
            return {"items": [public_row(row) for row in rows]}

    def validate_candidate(self, candidate_public_id: str, admin_id: str) -> dict[str, Any]:
        """Runs privacy/safety/licence/deduplication/contamination checks
        and records the resulting dimension assessments, without
        approving the candidate -- approval is always a separate,
        explicit action."""

        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            version = connection.execute(
                "SELECT * FROM feedback_candidate_versions WHERE id=?",
                (candidate["current_version_id"],),
            ).fetchone()
            event = connection.execute(
                "SELECT * FROM feedback_events WHERE id=?",
                (candidate["source_feedback_event_id"],),
            ).fetchone()
            subject = connection.execute(
                "SELECT * FROM feedback_subjects WHERE id=?", (candidate["source_subject_id"],)
            ).fetchone()

            existing_records = self._existing_records_for_dedup(connection)
            dedup = detect_duplicate(
                prompt_text=version["prompt_text"],
                output_text=version["output_text"],
                existing_records=existing_records,
                near_duplicate_threshold=self.settings.feedback_near_duplicate_threshold,
            )

            evaluation_fixture_checksums = self._evaluation_fixture_checksums(connection)
            regression_fixture_checksums = frozenset(
                row["checksum_sha256"]
                for row in connection.execute(
                    "SELECT checksum_sha256 FROM feedback_regression_fixtures"
                ).fetchall()
            )
            test_checksums = self._dataset_split_checksums(connection, "test")
            validation_checksums = self._dataset_split_checksums(connection, "validation")
            training_checksums = self._dataset_split_checksums(connection, "train")

            contamination = check_contamination(
                prompt_text=version["prompt_text"],
                output_text=version["output_text"],
                training_checksums=training_checksums,
                validation_checksums=validation_checksums,
                test_checksums=test_checksums,
                evaluation_fixture_checksums=evaluation_fixture_checksums,
                regression_fixture_checksums=regression_fixture_checksums,
                subject_output_checksum=subject["output_checksum_sha256"],
            )

            provenance = assess_provenance(
                feedback_source_type=event["feedback_type"],
                content_creator_type="reviewer_corrected",
                consent_status="reviewed",
                declared_licence_status=(
                    "approved" if event["privacy_status"] == "safe" else "restricted"
                ),
                reviewer_attribution_public_id=admin_id,
                source_deleted=event["status"] == "deleted",
            )

            privacy_status = event["privacy_status"]
            safety_status = event["safety_status"]

            quality = assess_candidate_quality(
                privacy_status=privacy_status,
                safety_status=safety_status,
                licence_status=provenance["licence_status"],
                deduplication_status=dedup["status"],
                contamination_status=contamination["status"],
                has_reviewer_evidence=bool(
                    self.repository.reviews_for_event(connection, event["id"])
                ),
                has_source_provenance=provenance["provenance_complete"],
                correction_validation_status="validated",
                detected_language=version["language"],
                expected_language=event["expected_language"],
            )
            for dimension in QUALITY_DIMENSIONS:
                self.repository.record_quality_assessment(
                    connection, candidate_id=candidate["id"], dimension=dimension,
                    status=quality[dimension], details={},
                )
            verdict = overall_candidate_verdict(quality)

            if contamination["blocks_approval"]:
                for issue in contamination["issues"]:
                    if issue in BLOCKING_CONTAMINATION_STATUSES:
                        self.repository.record_candidate_issue(
                            connection, candidate_id=candidate["id"], issue_code=issue,
                            severity="critical", details={},
                        )

            new_status = "review_required"
            if privacy_status == "blocked" or safety_status == "blocked":
                new_status = "rejected"
            elif contamination["blocks_approval"]:
                new_status = "quarantined"
            elif provenance["blocks_approval"] and self.settings.feedback_require_known_licence:
                new_status = "rejected"
            elif verdict == "fail":
                new_status = "rejected"

            self.repository.update_candidate(
                connection, candidate["id"],
                {
                    "privacy_status": privacy_status,
                    "safety_status": safety_status,
                    "licence_status": provenance["licence_status"],
                    "deduplication_status": dedup["status"],
                    "contamination_status": contamination["status"],
                    "status": new_status,
                },
            )
            self._audit(
                connection, "feedback_candidate_validated", admin_id, candidate_public_id,
                status=new_status, verdict=verdict,
            )
            return public_row(self.repository.candidate(connection, candidate_public_id))

    def approve_candidate(
        self, candidate_public_id: str, decision: str, payload: CandidateApprovalCreate,
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            if candidate["status"] not in {"review_required", "approved", "approved_with_warnings"}:
                raise ValidationError(f"candidate cannot be {decision} from {candidate['status']}")
            if candidate["privacy_status"] == "blocked" or candidate["safety_status"] == "blocked":
                raise ValidationError("privacy- or safety-blocked candidates cannot be approved")
            if (
                candidate["contamination_status"] in BLOCKING_CONTAMINATION_STATUSES
                and decision in {"approve", "approve_with_warning"}
            ):
                raise ValidationError("contaminated candidates cannot be approved")
            if (
                candidate["licence_status"] in {"unknown", "blocked"}
                and self.settings.feedback_require_known_licence
                and decision in {"approve", "approve_with_warning"}
            ):
                raise ValidationError("unknown/blocked licence cannot be approved")

            status_map = {
                "approve": "approved",
                "approve_with_warning": "approved_with_warnings",
                "reject": "rejected",
                "request_changes": "draft",
                "quarantine": "quarantined",
            }
            new_status = status_map[decision]
            self.repository.update_candidate(connection, candidate["id"], {"status": new_status})
            self.repository.record_candidate_approval(
                connection,
                {
                    "candidate_id": candidate["id"],
                    "candidate_version_id": candidate["current_version_id"],
                    "decision": decision,
                    "privacy_assessment": candidate["privacy_status"],
                    "safety_assessment": candidate["safety_status"],
                    "deduplication_result": candidate["deduplication_status"],
                    "contamination_result": candidate["contamination_status"],
                    "licence_result": candidate["licence_status"],
                    "admin_public_id": admin_id,
                    "comment": payload.comment,
                },
            )
            self._audit(
                connection, "feedback_candidate_approval_decision", admin_id, candidate_public_id,
                decision=decision,
            )
            return public_row(self.repository.candidate(connection, candidate_public_id))

    def export_candidate(self, candidate_public_id: str, admin_id: str) -> dict[str, Any]:
        """Reads and validates the candidate in its own transaction, then
        creates the dataset source/record as separate, self-committing
        calls (each opens its own transaction against a different
        repository) -- never nested inside this service's own open
        transaction, which would leave the new rows invisible to the
        other repository's connection until commit. Only after both
        complete does a final transaction mark the candidate exported."""

        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            if candidate["status"] not in {"approved", "approved_with_warnings"}:
                raise ValidationError("only approved candidates may be exported")
            if candidate["candidate_type"] == "evaluation_only":
                raise ValidationError(
                    "evaluation_only candidates are regression evidence and must never be "
                    "exported into the training dataset pipeline"
                )
            if candidate["candidate_type"] == "preference":
                raise ValidationError(
                    "preference candidates remain outside automatic SFT export until a "
                    "future preference-training phase is explicitly implemented"
                )
            latest_approval = connection.execute(
                """SELECT * FROM feedback_candidate_approvals WHERE candidate_id=?
                ORDER BY created_at DESC, id DESC LIMIT 1""",
                (candidate["id"],),
            ).fetchone()
            if (
                self.settings.feedback_require_current_approval_checksum
                and latest_approval
                and latest_approval["candidate_version_id"] != candidate["current_version_id"]
            ):
                raise ValidationError(
                    "approval is stale -- candidate content changed since the last approval"
                )
            version = dict(
                connection.execute(
                    "SELECT * FROM feedback_candidate_versions WHERE id=?",
                    (candidate["current_version_id"],),
                ).fetchone()
            )
            candidate_type = candidate["candidate_type"]

        source_public_id = self._find_or_create_feedback_source(version["language"])
        record_type_map = {
            "instruction": "instruction", "chat": "chat", "translation": "translation",
            "tanglish_pair": "tanglish_pair", "safety": "safety",
        }
        record_type = record_type_map.get(candidate_type, "instruction")
        record = self.dataset_service.create_record(
            RecordCreate(
                source_public_id=source_public_id,
                record_type=record_type,
                language=version["language"] if version["language"] != "unknown" else "en",
                instruction=version["prompt_text"],
                input_text=version["input_text"],
                output_text=version["output_text"],
                metadata={"feedback_candidate_public_id": candidate_public_id},
            ),
            admin_id,
        )

        with self.repository.transaction() as connection:
            candidate = self.repository.candidate(connection, candidate_public_id)
            self.repository.update_candidate(
                connection, candidate["id"],
                {
                    "status": "exported",
                    "exported_dataset_record_public_id": record["public_id"],
                },
            )
            self._audit(
                connection, "feedback_candidate_exported", admin_id, candidate_public_id,
                dataset_record=record["public_id"],
            )
            return public_row(self.repository.candidate(connection, candidate_public_id))

    def _find_or_create_feedback_source(self, language: str) -> str:
        with self.dataset_service.repository.transaction() as connection:
            existing = connection.execute(
                "SELECT public_id FROM dataset_sources WHERE source_type='chat_feedback' LIMIT 1"
            ).fetchone()
            if existing:
                return existing["public_id"]
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO dataset_sources(name,source_type,status,public_id,language,
                licence_status,metadata_json) VALUES (?,?,?,?,?,?,?)""",
                (
                    "Feedback-Derived Candidates", "chat_feedback", "ready", public_id,
                    language if language != "unknown" else "en", "approved", "{}",
                ),
            )
            return public_id

    def _existing_records_for_dedup(self, connection) -> list[dict[str, str]]:
        rows = connection.execute(
            """SELECT public_id, COALESCE(instruction,'') AS prompt_text,
            COALESCE(output_text,'') AS output_text FROM dataset_records LIMIT 5000"""
        ).fetchall()
        return [
            {
                "prompt_text": row["prompt_text"],
                "output_text": row["output_text"],
                "reference": row["public_id"],
            }
            for row in rows
        ]

    def _dataset_split_checksums(self, connection, split: str) -> frozenset[str]:
        rows = connection.execute(
            """SELECT r.instruction, r.output_text FROM dataset_records r
            JOIN dataset_version_items dvi ON dvi.dataset_record_id = r.id
            WHERE dvi.split = ?""",
            (split,),
        ).fetchall()
        return frozenset(
            checksum_of(
                normalize_for_comparison(f"{row['instruction'] or ''}\n{row['output_text'] or ''}")
            )
            for row in rows
        )

    def _evaluation_fixture_checksums(self, connection) -> frozenset[str]:
        rows = connection.execute(
            "SELECT prompt, reference_answer FROM model_evaluation_fixtures"
        ).fetchall()
        return frozenset(
            checksum_of(
                normalize_for_comparison(
                    f"{row['prompt'] or ''}\n{row['reference_answer'] or ''}"
                )
            )
            for row in rows
        )

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event, "admin", "{}", str(uuid4()), event, "admin", admin_id,
                "feedback", resource_id, "success", dumps_json(metadata),
            ),
        )
