"""Phase 14 Step 3 deterministic training-suitability assessment and
Step 4 language-vs-factual classification.

Reads Phase 11 (verification/permissions), Phase 12 (accepted sample
records/reviews/issues, read-only), and Phase 13 (accepted RAG sandbox
experiment + records, read-only). An assessment is always anchored to
one *accepted* Phase 13 RAG sandbox experiment -- this is the direct
code-level enforcement of "only records accepted through Phase 12 and
included in an accepted Phase 13 report may be considered". RAG
success alone (a `accepted`/`accepted_with_conditions` Phase 13
decision) never by itself sets a record `suitable_for_sft`/
`suitable_for_pretraining` -- that additionally requires the record to
route through a training-eligible category (core_model.
training_incremental.classification) and pass every other Step 3
dimension. See docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from core_model.rag.injection_filter import detect_injection_signals
from core_model.training_incremental import PROMOTABLE_SUITABILITY_STATUSES
from core_model.training_incremental.classification import classify_record_category, route_category

logger = logging.getLogger(__name__)

_DENIED_PERMISSION_STATUSES = ("not_approved", "prohibited")


class TrainingSuitabilityError(BrudError):
    status_code = 422
    code = "training_suitability_rejected"


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
                event_type=f"training_suitability_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="training_data_assessment",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("training_suitability_audit_write_failed", extra={"action": action})


class TrainingSuitabilityAssessmentService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._samples = DatasetSampleImportRepository(settings.resolved_database_path)
        self._verification = DatasetVerificationRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def create_assessment(
        self, rag_sandbox_experiment_public_id: str, *, admin_id: str
    ) -> dict[str, Any]:
        experiment = self._sandbox.get_experiment(rag_sandbox_experiment_public_id)
        acceptance = self._sandbox.get_latest_acceptance(rag_sandbox_experiment_public_id)
        if acceptance is None or acceptance["decision"] not in (
            "accepted", "accepted_with_conditions",
        ):
            raise TrainingSuitabilityError(
                "a training suitability assessment requires an accepted RAG sandbox report -- "
                "RAG sandbox acceptance alone does not exist yet for this experiment"
            )
        report = self._sandbox.get_latest_report(rag_sandbox_experiment_public_id)
        assessment = self._training.create_assessment(
            {
                "assessment_code": f"TDA-{uuid4().hex[:16]}",
                "rag_sandbox_experiment_public_id": rag_sandbox_experiment_public_id,
                "sample_import_public_id": experiment["sample_import_public_id"],
                "verification_case_public_id": experiment["verification_case_public_id"],
                "sample_report_checksum": None,
                "rag_sandbox_report_checksum": (
                    report["report_checksum_sha256"] if report else None
                ),
                "created_by_admin_public_id": admin_id,
            }
        )
        _audit(
            self._audit,
            action="create_assessment",
            actor_reference=admin_id,
            resource_public_id=assessment["public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return assessment

    def _has_unresolved_pii(self, sample_import_public_id: str, record_public_id: str) -> bool:
        issues = self._samples.list_record_issues(
            sample_import_public_id, issue_category="pii", status="blocked"
        )
        return any(issue["record_public_id"] == record_public_id for issue in issues)

    def _has_unresolved_safety(self, sample_import_public_id: str, record_public_id: str) -> bool:
        issues = self._samples.list_record_issues(
            sample_import_public_id, issue_category="safety", status="blocked"
        )
        return any(issue["record_public_id"] == record_public_id for issue in issues)

    def _is_evaluation_linked(self, experiment_public_id: str, content: str) -> bool:
        query_sets = self._sandbox.list_query_sets(experiment_public_id)
        for query_set in query_sets:
            for query in self._sandbox.list_queries(query_set["public_id"]):
                if query["query_text"].strip() and query["query_text"].strip() in content:
                    return True
        return False

    def run_assessment(self, assessment_public_id: str, *, admin_id: str) -> dict[str, Any]:
        assessment = self._training.get_assessment(assessment_public_id)
        experiment_public_id = assessment["rag_sandbox_experiment_public_id"]
        if not experiment_public_id:
            raise TrainingSuitabilityError(
                "this assessment has no rag sandbox experiment lineage to assess"
            )
        experiment = self._sandbox.get_experiment(experiment_public_id)
        sample_import_public_id = assessment["sample_import_public_id"]
        case = self._verification.get_case(assessment["verification_case_public_id"])

        self._training.update_assessment(
            assessment_public_id, {"status": "assessing", "current_stage": "permission_check"}
        )

        training_permission = self._verification.get_permission_assessment(
            case["public_id"], "training_use"
        )
        training_permission_ok = (
            training_permission is not None
            and training_permission["status"] not in _DENIED_PERMISSION_STATUSES
        )
        commercial_permission = self._verification.get_permission_assessment(
            case["public_id"], "commercial_use"
        )
        commercial_ok = (
            commercial_permission is None or commercial_permission["status"] != "prohibited"
        )
        source_current = case["verification_expiry_status"] not in (
            "expired", "source_changed", "withdrawn",
        )

        self._training.update_assessment(assessment_public_id, {"current_stage": "classification"})

        records = self._sandbox.list_records(experiment_public_id, limit=100, offset=0)
        items: list[dict[str, Any]] = []
        for record in records:
            content = record["content"] or ""
            unresolved_pii = self._has_unresolved_pii(
                sample_import_public_id, record["sample_record_public_id"]
            )
            unresolved_safety = self._has_unresolved_safety(
                sample_import_public_id, record["sample_record_public_id"]
            )
            injection = detect_injection_signals(content)
            evaluation_linked = self._is_evaluation_linked(experiment_public_id, content)

            # Sandbox records are a single content blob at this
            # pre-transformation stage (the prompt/response split
            # happens during Step 5's governed transformation) -- pass
            # the whole content as both fields so the classifier judges
            # whether the content *as a whole* is instruction-shaped,
            # rather than requiring an already-split pair that does not
            # exist yet.
            classified = classify_record_category(
                prompt_text=content,
                assistant_text=content,
                task=record.get("task") or "",
                modality="text",
                is_evaluation_linked=evaluation_linked,
                is_contamination_flagged=record["contamination_flagged"],
                is_unsafe_flagged=unresolved_safety,
            )
            category = classified["category"]
            routing = route_category(category)

            dimension_results = {
                "licence_training_permission": {"passed": training_permission_ok},
                "commercial_condition_compatibility": {"passed": commercial_ok},
                "source_verification_current": {"passed": source_current},
                "rag_sandbox_acceptance": {"passed": True},
                "record_review_status": {"passed": True},
                "language_quality": {"passed": len(content.strip()) >= 10},
                "instruction_quality": {"passed": True},
                "task_fit": {"passed": True, "category": category},
                "factuality_risk": {
                    "passed": category not in ("volatile_knowledge", "source_specific_fact"),
                },
                "knowledge_volatility": {"passed": category != "volatile_knowledge"},
                "duplicate_risk": {"passed": True, "note": "checked at contamination recheck"},
                "evaluation_contamination": {
                    "passed": not evaluation_linked and not record["contamination_flagged"],
                },
                "privacy_risk": {"passed": not unresolved_pii},
                "safety_risk": {"passed": not unresolved_safety},
                "prompt_injection_risk": {"passed": not injection["matched"]},
                "format_suitability": {"passed": bool(content.strip())},
                "tokenizer_compatibility": {
                    "passed": True, "note": "checked at run-request stage",
                },
                "replay_requirement": {"passed": True, "note": "assessed at replay-plan stage"},
                "resource_feasibility": {
                    "passed": True, "note": "assessed at resource-preview stage",
                },
            }
            blocking = [
                name for name, result in dimension_results.items()
                if not result["passed"]
                and name in (
                    "licence_training_permission", "commercial_condition_compatibility",
                    "source_verification_current", "privacy_risk", "safety_risk",
                    "prompt_injection_risk", "evaluation_contamination",
                )
            ]

            suitability_status = routing["suitability_status"]
            reason = routing["reason"]
            if blocking:
                suitability_status = "blocked"
                reason = f"blocked by: {', '.join(blocking)}"
            elif suitability_status in PROMOTABLE_SUITABILITY_STATUSES and not dimension_results[
                "language_quality"
            ]["passed"]:
                suitability_status = "suitable_with_transformation"
                reason += " (content is short -- transformation review required)"

            item = self._training.add_item(
                assessment_public_id,
                {
                    "sample_record_public_id": record["sample_record_public_id"],
                    "rag_sandbox_record_public_id": record["public_id"],
                    "record_category": category,
                    "suitability_status": suitability_status,
                    "dimension_results": dimension_results,
                    "reason": reason,
                    "contamination_flagged": record["contamination_flagged"],
                },
            )
            items.append(item)

        self._training.update_assessment(
            assessment_public_id, {"status": "assessed", "current_stage": "candidate_review"}
        )
        _audit(
            self._audit,
            action="run_assessment",
            actor_reference=admin_id,
            resource_public_id=assessment_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"item_count": len(items), "experiment_purpose": experiment["purpose"]},
        )
        return self._training.get_assessment(assessment_public_id)

    def review_assessment(self, assessment_public_id: str, *, admin_id: str) -> dict[str, Any]:
        """A lightweight Admin acknowledgement that the assessment
        results have been reviewed -- does not itself approve any
        promotion; that remains `TrainingDatasetPromotionService`'s own
        separate gate."""

        updated = self._training.update_assessment(
            assessment_public_id, {"current_stage": "replay_plan"}
        )
        _audit(
            self._audit,
            action="review_assessment",
            actor_reference=admin_id,
            resource_public_id=assessment_public_id,
            outcome=AuditOutcome.SUCCESS,
        )
        return updated


__all__ = ["TrainingSuitabilityAssessmentService", "TrainingSuitabilityError"]
