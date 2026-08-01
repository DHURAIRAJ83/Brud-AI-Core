"""Governed Admin Assistant.

The assistant is read-only by default: it summarizes dashboard state and
drafts proposals. It never mutates anything itself. A mutation only
happens when an admin reviews a pending proposal through Admin Review and
approves it, and even then execution is dispatched through an allowlisted
existing service call -- never a bespoke write path -- so every mutation
still passes through the same validation, transitions, and audit hooks it
would if an admin had performed it by hand in the dashboard.

Every step (proposal created, reviewed, executed, failed) is written to
the audit log via AuditLogRepository so the whole lifecycle is traceable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.database.connection import database_connection
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.phase2 import AdminApprovalRepository
from backend.models.datasets import SourcePatch
from backend.models.domain import (
    AdminApprovalCreate,
    AdminApprovalPublic,
    AuditEventCreate,
    AuditOutcome,
    ReviewDecision,
)
from backend.services.dataset_service import DatasetService
from core_model.admin_assistant.action_registry import (
    BLOCKED_ACTION_SUBSTRINGS,
    get_action_definition,
    is_known_action_type,
)

logger = logging.getLogger(__name__)

# How long a generated preview/stale-check snapshot remains valid before a
# `pending` proposal is lazily transitioned to `expired` on next read/
# review (see AdminApprovalRepository._expire_if_due). Chosen to be long
# enough for a normal Admin Review turnaround, short enough that a stale
# snapshot cannot silently authorize a mutation against long-changed state.
PROPOSAL_PREVIEW_TTL_HOURS = 24


# Action types the assistant is allowed to propose. Each maps to a callable
# that performs the mutation through an existing, already-secured admin
# service -- the assistant never talks to the database directly for writes.
# Anything not in this map cannot be proposed or executed, which is also
# what keeps training out of reach: there is no "start_training" entry and
# there never should be one added here. Keys here must exactly match
# `core_model.admin_assistant.action_registry.ACTION_DEFINITIONS` (a
# dedicated test asserts this) -- that module is the pure metadata (risk
# level, payload shape, confirmation copy), this map is the impure wiring.
ActionExecutor = Callable[[Settings, str, dict[str, Any], str], dict[str, Any]]
# A fingerprint function reads the target entity's *current* state and
# returns a small, comparable dict -- used both to detect concurrent
# mutation between propose and confirm (Flow N) and, called again after
# execution, to verify the mutation actually took effect.
FingerprintFunction = Callable[[Settings, str, dict[str, Any]], dict[str, Any]]
# A preview generator reads current state and describes, in bilingual
# summary form, what the action would change -- generated once at
# propose time and never silently regenerated at confirm time.
PreviewGenerator = Callable[[Settings, str, dict[str, Any]], dict[str, Any]]


def _execute_dataset_record_review(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
    decision = ReviewDecision(payload["decision"])
    comments = payload.get("comments")
    return service.review(target_public_id, decision, comments, admin_id)


def _execute_dataset_source_update(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
    patch = SourcePatch.model_validate(payload)
    return service.update_source(target_public_id, patch, admin_id)


def _execute_governance_target_approval_override(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.governance_service import GovernanceApprovalService

    service = GovernanceApprovalService(settings)
    return service.override(
        payload["entity_type"],
        target_public_id,
        payload["target_use"],
        payload["decision"],
        reason=payload["reason"],
        admin_id=admin_id,
    )


def _execute_register_external_data_provider(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.external_data_provider_service import ExternalDataProviderService

    service = ExternalDataProviderService(settings)
    create_payload = {key: value for key, value in payload.items() if key != "reason"}
    create_payload.setdefault("provider_code", target_public_id)
    return service.register_provider(create_payload, admin_id)


def _execute_verify_external_data_provider(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.external_data_provider_service import (
        ExternalDataProviderVerificationService,
    )

    return ExternalDataProviderVerificationService(settings).evaluate_provider(
        target_public_id, admin_id
    )


def _execute_test_external_data_provider_connection(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.external_data_provider_service import (
        ExternalDataProviderConnectionService,
    )

    service = ExternalDataProviderConnectionService(settings)
    use_credential = bool(payload.get("use_credential", False))
    return service.test_connection(
        target_public_id, admin_id=admin_id, use_credential=use_credential
    )


def _execute_enable_external_data_provider(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.external_data_provider_service import ExternalDataProviderService

    return ExternalDataProviderService(settings).transition_lifecycle(
        target_public_id, "enable", admin_id
    )


def _execute_disable_external_data_provider(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.external_data_provider_service import ExternalDataProviderService

    return ExternalDataProviderService(settings).transition_lifecycle(
        target_public_id, "disable", admin_id
    )


def _execute_configure_provider_credential_reference(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.external_data_provider_service import (
        ExternalDataProviderCredentialService,
    )

    service = ExternalDataProviderCredentialService(settings)
    return service.configure_credential_reference(
        target_public_id,
        credential_type=payload["credential_type"],
        reference_key=payload["reference_key"],
        admin_id=admin_id,
    )


def _execute_run_dataset_search(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.external_dataset_search_service import (
        ExternalDatasetSearchExecutionService,
    )

    return ExternalDatasetSearchExecutionService(settings).run_search(
        target_public_id, admin_id=admin_id
    )


def _execute_exclude_dataset_candidate(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.external_dataset_search_service import ExternalDatasetCandidateService

    return ExternalDatasetCandidateService(settings).exclude_candidate(
        target_public_id, admin_id=admin_id
    )


def _execute_create_dataset_verification_case(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.dataset_verification_case_service import (
        ExternalDatasetVerificationService,
    )

    return ExternalDatasetVerificationService(settings).create_case(
        candidate_public_id=target_public_id,
        verification_scope=payload.get("verification_scope", ""),
        admin_id=admin_id,
    )


def _execute_collect_dataset_licence_evidence(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.dataset_verification_evidence_service import (
        ExternalDatasetEvidenceService,
    )

    return ExternalDatasetEvidenceService(settings).collect_evidence(
        target_public_id,
        evidence_type=payload["evidence_type"],
        source_url=payload["source_url"],
        provider_public_id=payload.get("provider_public_id"),
        authority_level=payload.get("authority_level"),
        admin_public_id=admin_id,
    )


def _execute_add_manual_dataset_evidence(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.dataset_verification_evidence_service import (
        ExternalDatasetEvidenceService,
    )

    return ExternalDatasetEvidenceService(settings).add_manual_evidence(
        target_public_id,
        evidence_type=payload["evidence_type"],
        content_text=payload["content_text"],
        source_url=payload.get("source_url"),
        authority_level=payload.get("authority_level", "manual_unverified"),
        ocr_derived=bool(payload.get("ocr_derived", False)),
        admin_public_id=admin_id,
    )


def _execute_assess_dataset_permissions(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.dataset_verification_permission_service import (
        ExternalDatasetPermissionAssessmentService,
    )

    results = ExternalDatasetPermissionAssessmentService(settings).assess(
        target_public_id, admin_public_id=admin_id
    )
    return {"items": results}


def _execute_review_dataset_permission(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.dataset_verification_permission_service import (
        ExternalDatasetPermissionAssessmentService,
    )

    return ExternalDatasetPermissionAssessmentService(settings).review(
        target_public_id,
        payload["permission_type"],
        status=payload["status"],
        reviewed_by=admin_id,
        reason=payload["reason"],
        conditions=payload.get("conditions"),
    )


def _execute_resolve_dataset_verification_conflict(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.dataset_verification_report_service import (
        ExternalDatasetConflictService,
    )

    return ExternalDatasetConflictService(settings).resolve(
        target_public_id,
        payload["conflict_public_id"],
        resolution_status=payload["resolution_status"],
        resolution_reason=payload["resolution_reason"],
        admin_public_id=admin_id,
    )


def _execute_finalize_dataset_verification_report(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.dataset_verification_report_service import (
        ExternalDatasetVerificationReportService,
    )

    return ExternalDatasetVerificationReportService(settings).finalize(
        target_public_id, admin_public_id=admin_id
    )


def _execute_reverify_dataset_evidence(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.dataset_verification_report_service import (
        ExternalDatasetReverificationService,
    )

    return ExternalDatasetReverificationService(settings).check(
        target_public_id, admin_public_id=admin_id
    )


def _execute_record_dataset_withdrawal_notice(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.dataset_verification_report_service import (
        ExternalDatasetWithdrawalService,
    )

    values = {key: value for key, value in payload.items() if key != "reason"}
    return ExternalDatasetWithdrawalService(settings).record_notice(
        target_public_id, values, admin_public_id=admin_id
    )


def _execute_link_dataset_verification_rights(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.database.repositories.data_sources import DataSourceRepository
    from backend.models.data_sources import SourceRightsUpsert
    from backend.services.data_source_service import SourceRightsService

    values = {key: value for key, value in payload.items() if key != "reason"}
    service = SourceRightsService(DataSourceRepository(settings.resolved_database_path), settings)
    return service.upsert(target_public_id, SourceRightsUpsert.model_validate(values), admin_id)


# -- Phase 12: Approved Sample Import, Quarantine, File Safety, PII & Quality -----------


def _execute_create_sample_import(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.database.repositories.dataset_verification import (
        DatasetVerificationRepository,
    )
    from backend.services.dataset_sample_eligibility_service import (
        ExternalDatasetSampleEligibilityService,
    )

    case = DatasetVerificationRepository(settings.resolved_database_path).get_case(
        target_public_id
    )
    values = dict(payload)
    values["candidate_public_id"] = case["candidate_public_id"]
    values["requested_by_admin_public_id"] = admin_id
    return ExternalDatasetSampleEligibilityService(settings).create_sample_import(
        target_public_id, values
    )


def _execute_request_sample_import_approval(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.dataset_sample_eligibility_service import (
        ExternalDatasetSampleApprovalService,
    )

    return ExternalDatasetSampleApprovalService(settings).request_approval(
        target_public_id, payload, admin_id=admin_id
    )


def _execute_approve_sample_import(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )
    from backend.services.dataset_sample_eligibility_service import (
        ExternalDatasetSampleApprovalService,
    )

    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    approval = repository.get_latest_approval(target_public_id)
    if approval is None:
        raise NotFoundError("no approval request exists for this sample import")
    return ExternalDatasetSampleApprovalService(settings).approve(
        approval["public_id"],
        admin_id=admin_id,
        approved_record_limit=payload["approved_record_limit"],
        approved_byte_limit=payload["approved_byte_limit"],
        expires_at=payload["expires_at"],
        approval_reason=payload.get("approval_reason"),
        conditions=payload.get("conditions"),
    )


def _execute_download_approved_sample(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.dataset_sample_download_service import (
        ExternalDatasetSampleDownloadService,
    )

    return ExternalDatasetSampleDownloadService(settings).download_file(
        target_public_id,
        source_url=payload["source_url"],
        allowed_domains=set(payload["allowed_domains"]),
        admin_id=admin_id,
        original_filename=payload.get("original_filename"),
    )


def _execute_validate_sample_files(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.dataset_sample_pipeline_service import (
        ExternalDatasetSamplePipelineService,
    )

    items = ExternalDatasetSamplePipelineService(settings).validate_files(
        target_public_id, admin_id=admin_id
    )
    return {"items": items}


def _execute_extract_sample_archive(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.dataset_sample_pipeline_service import (
        ExternalDatasetSamplePipelineService,
    )

    items = ExternalDatasetSamplePipelineService(settings).extract_archives(
        target_public_id, admin_id=admin_id
    )
    return {"items": items}


def _execute_scan_sample(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.dataset_sample_pipeline_service import (
        ExternalDatasetSamplePipelineService,
    )

    items = ExternalDatasetSamplePipelineService(settings).scan_files(
        target_public_id, admin_id=admin_id
    )
    return {"items": items}


def _execute_parse_sample(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.dataset_sample_pipeline_service import (
        ExternalDatasetSamplePipelineService,
    )

    items = ExternalDatasetSamplePipelineService(settings).parse_files(
        target_public_id, admin_id=admin_id
    )
    return {"items": items}


def _execute_run_sample_quality_checks(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.dataset_sample_pipeline_service import (
        ExternalDatasetSamplePipelineService,
    )

    items = ExternalDatasetSamplePipelineService(settings).run_quality_checks(
        target_public_id, admin_id=admin_id
    )
    return {"items": items}


def _execute_run_sample_duplicate_checks(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.dataset_sample_pipeline_service import (
        ExternalDatasetSamplePipelineService,
    )

    items = ExternalDatasetSamplePipelineService(settings).run_duplicate_checks(
        target_public_id, admin_id=admin_id
    )
    return {"items": items}


def _execute_run_sample_contamination_checks(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.dataset_sample_pipeline_service import (
        ExternalDatasetSamplePipelineService,
    )

    items = ExternalDatasetSamplePipelineService(settings).run_contamination_checks(
        target_public_id, admin_id=admin_id
    )
    return {"items": items}


def _execute_review_sample_issue(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.dataset_sample_review_service import ExternalDatasetSampleReviewService

    return ExternalDatasetSampleReviewService(settings).review_target(
        target_public_id,
        target_type="issue",
        target_id=payload["issue_public_id"],
        decision=payload["decision"],
        reason=payload["reason"],
        reviewer_admin_public_id=admin_id,
        derived_content_text=payload.get("derived_content_text"),
        conditions=payload.get("conditions"),
    )


def _execute_finalize_sample_validation_report(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.dataset_sample_report_service import ExternalDatasetSampleReportService

    return ExternalDatasetSampleReportService(settings).finalize(
        target_public_id, admin_id=admin_id
    )


def _execute_request_sample_deletion(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.dataset_sample_deletion_service import (
        ExternalDatasetSampleDeletionService,
    )

    return ExternalDatasetSampleDeletionService(settings).request_deletion(
        target_public_id, admin_id=admin_id, reason=payload["reason"]
    )


def _execute_execute_sample_deletion(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )
    from backend.services.dataset_sample_deletion_service import (
        ExternalDatasetSampleDeletionService,
    )

    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    latest = repository.get_latest_deletion_request(target_public_id)
    if latest is None:
        raise NotFoundError("no deletion request exists for this sample import")
    service = ExternalDatasetSampleDeletionService(settings)
    service.confirm_deletion(latest["deletion_request_code"], admin_id=admin_id)
    return service.execute_deletion(latest["deletion_request_code"], admin_id=admin_id)


# -- Phase 13: Isolated RAG Sandbox, Retrieval Evaluation, Grounded Answer Testing -------


def _execute_create_rag_sandbox_experiment(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.rag_sandbox_eligibility_service import RagSandboxEligibilityService

    values = dict(payload)
    values["created_by_admin_public_id"] = admin_id
    return RagSandboxEligibilityService(settings).create_experiment(target_public_id, values)


def _execute_request_rag_sandbox_approval(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.rag_sandbox_eligibility_service import RagSandboxApprovalService

    return RagSandboxApprovalService(settings).request_approval(
        target_public_id, payload, admin_id=admin_id
    )


def _execute_approve_rag_sandbox_experiment(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.database.repositories.rag_sandbox import RagSandboxRepository
    from backend.services.rag_sandbox_eligibility_service import RagSandboxApprovalService

    repository = RagSandboxRepository(settings.resolved_database_path)
    approval = repository.get_latest_approval(target_public_id)
    if approval is None:
        raise NotFoundError("no approval request exists for this rag sandbox experiment")
    return RagSandboxApprovalService(settings).approve(
        approval["public_id"], admin_id=admin_id, expires_at=payload.get("expires_at")
    )


def _execute_prepare_rag_sandbox_corpus(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.rag_sandbox_corpus_service import RagSandboxCorpusService

    return RagSandboxCorpusService(settings).prepare_corpus(target_public_id, admin_id=admin_id)


def _execute_build_rag_sandbox_index(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.rag_sandbox_index_service import RagSandboxIndexService

    return RagSandboxIndexService(settings).build_index(
        target_public_id, admin_id=admin_id, **payload
    )


def _execute_create_rag_sandbox_query_set(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.rag_sandbox_query_set_service import RagSandboxQuerySetService

    return RagSandboxQuerySetService(settings).create_query_set(
        target_public_id, name=payload["name"], admin_id=admin_id
    )


def _execute_finalize_rag_sandbox_query_set(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id
    from backend.services.rag_sandbox_query_set_service import RagSandboxQuerySetService

    return RagSandboxQuerySetService(settings).finalize_query_set(
        payload["query_set_public_id"], admin_id=admin_id
    )


def _execute_run_rag_sandbox_retrieval(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.rag_sandbox_retrieval_service import RagSandboxRetrievalService

    return RagSandboxRetrievalService(settings).run_retrieval(
        target_public_id,
        index_public_id=payload["index_public_id"],
        query_set_public_id=payload["query_set_public_id"],
        admin_id=admin_id,
    )


def _execute_run_rag_sandbox_generation(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.rag_sandbox_answer_service import RagSandboxAnswerService

    return RagSandboxAnswerService(settings).run_generation(
        target_public_id,
        retrieval_run_public_id=payload["retrieval_run_public_id"],
        generation_assignment_public_id=payload["generation_assignment_public_id"],
        admin_id=admin_id,
    )


def _execute_run_rag_sandbox_evaluation(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.rag_sandbox_evaluation_service import RagSandboxEvaluationService

    evaluations = RagSandboxEvaluationService(settings).run_evaluation(
        target_public_id, payload["answer_run_public_id"], admin_id=admin_id
    )
    return {"items": evaluations}


def _execute_review_rag_sandbox_query(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.rag_sandbox_human_review_service import RagSandboxHumanReviewService

    values = {key: value for key, value in payload.items() if key != "query_public_id"}
    return RagSandboxHumanReviewService(settings).review_query(
        target_public_id, payload["query_public_id"], values, admin_id=admin_id
    )


def _execute_finalize_rag_sandbox_report(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.rag_sandbox_report_service import RagSandboxReportService

    return RagSandboxReportService(settings).finalize(target_public_id, admin_id=admin_id)


def _execute_accept_rag_sandbox(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.rag_sandbox_acceptance_service import RagSandboxAcceptanceService

    return RagSandboxAcceptanceService(settings).decide(
        target_public_id,
        decision=payload["decision"],
        reason=payload["reason"],
        report_public_id=payload["report_public_id"],
        conditions=payload.get("conditions"),
        admin_id=admin_id,
    )


def _execute_reject_rag_sandbox(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.rag_sandbox_acceptance_service import RagSandboxAcceptanceService

    return RagSandboxAcceptanceService(settings).decide(
        target_public_id,
        decision="rejected",
        reason=payload["reason"],
        report_public_id=payload["report_public_id"],
        conditions=payload.get("conditions"),
        admin_id=admin_id,
    )


def _execute_request_rag_sandbox_deletion(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.rag_sandbox_deletion_service import RagSandboxDeletionService

    return RagSandboxDeletionService(settings).request_deletion(
        target_public_id, reason=payload["reason"], admin_id=admin_id
    )


def _execute_execute_rag_sandbox_deletion(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.rag_sandbox import RagSandboxRepository
    from backend.services.rag_sandbox_deletion_service import RagSandboxDeletionService

    repository = RagSandboxRepository(settings.resolved_database_path)
    latest = repository.get_latest_deletion_request(target_public_id)
    if latest is None:
        raise NotFoundError("no deletion request exists for this rag sandbox experiment")
    return RagSandboxDeletionService(settings).execute_deletion(
        latest["deletion_request_code"], admin_id=admin_id
    )


# -- Phase 14: Training Dataset Promotion, Incremental Language Training,
# Checkpoint Evaluation & Admin Approval -------------------------------------------
# Deliberately stops at "submit this dataset promotion request for Admin
# approval" -- there is no executor here for approving/materializing a
# promotion, creating/approving a training run request, starting or
# resuming a run, evaluating or accepting a checkpoint, or registering a
# model candidate. Those remain direct, non-assistant Admin actions.


def _execute_assess_language_sample_suitability(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.training_suitability_service import TrainingSuitabilityAssessmentService

    return TrainingSuitabilityAssessmentService(settings).create_assessment(
        target_public_id, admin_id=admin_id
    )


def _execute_run_language_sample_suitability_check(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.training_suitability_service import TrainingSuitabilityAssessmentService

    return TrainingSuitabilityAssessmentService(settings).run_assessment(
        target_public_id, admin_id=admin_id
    )


def _execute_acknowledge_language_sample_assessment(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.training_suitability_service import TrainingSuitabilityAssessmentService

    return TrainingSuitabilityAssessmentService(settings).review_assessment(
        target_public_id, admin_id=admin_id
    )


def _execute_transform_language_sample_candidate(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.training_example_transformation_service import (
        TrainingExampleTransformationService,
    )

    return TrainingExampleTransformationService(settings).transform(
        target_public_id, payload, admin_id=admin_id
    )


def _execute_review_language_sample_candidate(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.training_example_transformation_service import (
        TrainingExampleTransformationService,
    )

    return TrainingExampleTransformationService(settings).review_candidate(
        target_public_id, payload, admin_id=admin_id
    )


def _execute_create_replay_data_plan(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.training_replay_plan_service import TrainingReplayPlanService

    return TrainingReplayPlanService(settings).create_plan(
        target_public_id, payload, admin_id=admin_id
    )


def _execute_create_dataset_promotion_request(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.training_dataset_promotion_service import (
        TrainingDatasetPromotionService,
    )

    return TrainingDatasetPromotionService(settings).create_request(
        target_public_id, payload, admin_id=admin_id
    )


def _execute_submit_dataset_promotion_request(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.training_dataset_promotion_service import (
        TrainingDatasetPromotionService,
    )

    return TrainingDatasetPromotionService(settings).submit_for_approval(
        target_public_id, admin_id=admin_id
    )


# -- Phase 15: Final Text/NLP Integration, Production RAG Proposal, Model
# Release Governance, Secure Deployment Readiness & Full Regression
# Verification ----------------------------------------------------------------------
# Deliberately stops at "submit this request for Admin approval" or "run a
# read-verify-only safety check" -- there is no executor here for approving
# a promotion or release, building/validating a RAG candidate, starting a
# canary, activating or rolling back anything, or submitting the final
# production-acceptance review. Those remain direct, non-assistant Admin
# actions in the Production Readiness dashboard/API.


def _execute_create_production_rag_promotion_request(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.production_rag_promotion_service import ProductionRagPromotionService

    return ProductionRagPromotionService(settings).create_request(
        {**payload, "rag_sandbox_experiment_public_id": target_public_id}, admin_id=admin_id
    )


def _execute_submit_production_rag_promotion_request(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.production_rag_promotion_service import ProductionRagPromotionService

    return ProductionRagPromotionService(settings).submit_for_review(
        target_public_id, admin_id=admin_id
    )


def _execute_create_production_model_release_request(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.production_model_release_request_service import (
        ProductionModelReleaseRequestService,
    )

    return ProductionModelReleaseRequestService(settings).create_request(
        {**payload, "incremental_training_checkpoint_public_id": target_public_id},
        admin_id=admin_id,
    )


def _execute_submit_production_model_release_request(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.production_model_release_request_service import (
        ProductionModelReleaseRequestService,
    )

    return ProductionModelReleaseRequestService(settings).submit_for_review(
        target_public_id, admin_id=admin_id
    )


def _execute_check_production_release_candidate_artifact_security(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.production_artifact_security_service import (
        ProductionArtifactSecurityService,
    )

    return {
        "items": ProductionArtifactSecurityService(settings).check_release_candidate_artifacts(
            target_public_id, admin_id=admin_id
        )
    }


def _execute_create_knowledge_gap_research_note(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.knowledge_gap_research_service import KnowledgeGapResearchService

    service = KnowledgeGapResearchService(settings)
    return service.add_note(
        target_public_id,
        note_type=payload["note_type"],
        note_text=payload["note_text"],
        source_reference=payload.get("source_reference"),
        author_admin_id=admin_id,
    )


def _execute_propose_gap_priority_update(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload, admin_id
    from datetime import UTC, datetime

    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
    from backend.services.knowledge_gap_priority_service import (
        KnowledgeGapPriorityService,
        PriorityInput,
    )

    repository = KnowledgeGapRepository(settings.resolved_database_path)
    case = repository.get_case(target_public_id)
    result = KnowledgeGapPriorityService().score(
        PriorityInput(
            event_type=case["event_type"],
            reason_codes=tuple(case["reason_codes"]),
            frequency=case["frequency"],
            last_seen_at=datetime.now(UTC),
            privacy_risk=case["content_unavailable_for_review"],
        )
    )
    return repository.update_case_priority(
        target_public_id,
        priority_score=result.priority_score,
        priority_band=result.priority_band,
        priority_reason_codes=list(result.priority_reason_codes),
    )


def _execute_propose_duplicate_gap_merge(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id
    from backend.services.knowledge_gap_merge_service import KnowledgeGapMergeService

    service = KnowledgeGapMergeService(settings)
    # The generic propose/confirm framework already verified this
    # matches the fingerprint captured at propose time before this
    # executor runs -- recomputing it fresh here is safe and avoids
    # duplicating `KnowledgeGapMergeService`'s own fingerprint logic.
    fresh = service.propose_merge(payload["case_public_ids"])
    return service.confirm_merge(
        case_public_ids=payload["case_public_ids"],
        stale_check_fingerprint=fresh["stale_check_fingerprint"],
        admin_public_id=admin_id,
        canonical_question=payload["canonical_question"],
        primary_language=payload["primary_language"],
    )


def _execute_generate_daily_knowledge_gap_report(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id, payload, admin_id
    from backend.services.knowledge_gap_daily_report_service import (
        KnowledgeGapDailyReportService,
    )

    return KnowledgeGapDailyReportService(settings).generate()


def _execute_propose_knowledge_gap_classification(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.knowledge_gap_review_service import KnowledgeGapReviewService

    service = KnowledgeGapReviewService(settings)
    return service.review(
        target_public_id, decision="reclassify", comment=payload.get("comment"),
        reviewed_by_admin_public_id=admin_id,
    )


def _execute_propose_gap_resolution(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.knowledge_gap_resolution_service import KnowledgeGapResolutionService

    service = KnowledgeGapResolutionService(settings)
    return service.resolve(
        target_public_id, resolution_type=payload["resolution_type"],
        notes=payload.get("notes"), resolved_by_admin_public_id=admin_id,
    )


def _execute_knowledge_gap_handoff_assessment(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload, admin_id
    from backend.services.knowledge_gap_handoff_assessment_service import (
        KnowledgeGapHandoffAssessmentService,
    )

    return KnowledgeGapHandoffAssessmentService(settings).assess(target_public_id)


def _execute_run_production_api_abuse_readiness_check(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id, payload
    from backend.services.production_api_abuse_readiness_service import (
        ProductionApiAbuseReadinessService,
    )

    return ProductionApiAbuseReadinessService(settings).assess(admin_id=admin_id)


def _execute_run_production_secret_redaction_check(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id, payload
    from backend.services.production_secret_scan_service import ProductionSecretScanService

    return ProductionSecretScanService(settings).verify_redaction_mechanism(admin_id=admin_id)


def _execute_compile_production_readiness_report(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id, payload
    from backend.services.production_readiness_report_service import (
        ProductionReadinessReportService,
    )

    return ProductionReadinessReportService(settings).compile_report(admin_id=admin_id)


def _execute_run_production_backup_readiness_check(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id, payload
    from backend.services.production_backup_restore_readiness_service import (
        ProductionBackupReadinessService,
    )

    return ProductionBackupReadinessService(settings).check_backup_readiness(admin_id=admin_id)


def _execute_run_production_restore_readiness_check(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id, payload
    from backend.services.production_backup_restore_readiness_service import (
        ProductionRestoreReadinessService,
    )

    return ProductionRestoreReadinessService(settings).check_restore_readiness(admin_id=admin_id)


def _execute_assess_production_backup_encryption(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id, payload
    from backend.services.production_backup_restore_readiness_service import (
        ProductionBackupEncryptionAssessmentService,
    )

    return ProductionBackupEncryptionAssessmentService(settings).assess(admin_id=admin_id)


def _execute_encrypt_production_backup(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id, payload
    from backend.services.production_backup_restore_readiness_service import (
        ProductionBackupEncryptionService,
    )

    return ProductionBackupEncryptionService(settings).encrypt_latest_backup(admin_id=admin_id)


def _execute_verify_production_encrypted_restore(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id, payload
    from backend.services.production_backup_restore_readiness_service import (
        ProductionBackupEncryptionService,
    )

    return ProductionBackupEncryptionService(settings).verify_encrypted_restore(admin_id=admin_id)


def _execute_propose_trusted_web_policy_issue(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id
    from backend.database.repositories.trusted_web_tool_gateway import (
        TrustedWebToolGatewayRepository,
    )

    repo = TrustedWebToolGatewayRepository(settings.resolved_database_path)
    return repo.record_policy_event(
        {"event_type": "issue_flagged", "admin_public_id": admin_id, "detail": payload["comment"]}
    )


def _execute_propose_source_block(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id
    from backend.database.repositories.trusted_web_tool_gateway import (
        TrustedWebToolGatewayRepository,
    )

    repo = TrustedWebToolGatewayRepository(settings.resolved_database_path)
    detail = f"domain={payload['domain']}; comment={payload['comment']}"
    return repo.record_policy_event(
        {"event_type": "source_block_proposed", "admin_public_id": admin_id, "detail": detail}
    )


def _execute_propose_source_allowlist_review(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del target_public_id
    from backend.database.repositories.trusted_web_tool_gateway import (
        TrustedWebToolGatewayRepository,
    )

    repo = TrustedWebToolGatewayRepository(settings.resolved_database_path)
    detail = f"domain={payload['domain']}; comment={payload['comment']}"
    return repo.record_policy_event(
        {
            "event_type": "allowlist_review_proposed", "admin_public_id": admin_id,
            "detail": detail,
        }
    )


def _execute_propose_tool_enablement_review(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    """No dedicated tool-policy table exists (tool enablement is a
    fixed code-level constant in `deterministic_tool_registry.py`, not
    a DB row -- Phase 22's own scope, not this phase's) -- the
    permanent record of this proposal is the action's own audit-logged
    `admin_assistant_actions` row, which the calling pipeline already
    writes for every action regardless of executor."""

    del target_public_id
    return {
        "recorded": True, "tool_name": payload["tool_name"], "comment": payload["comment"],
        "reviewed_by_admin_public_id": admin_id,
    }


def _execute_propose_tool_permission_issue(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del settings, target_public_id
    return {
        "recorded": True, "tool_name": payload["tool_name"], "comment": payload["comment"],
        "flagged_by_admin_public_id": admin_id,
    }


# -- Document SFT workflow -------------------------------------------------
# target_public_id is the document for every document-level action; where a
# sub-entity (page, Tamil issue, SFT candidate) is mutated, its identifier
# travels in payload so `document_public_id` stays the stable fingerprint
# anchor. All executors call the existing, already-secured Phase 4/5/043
# services below -- nothing here re-implements page/chunk/candidate mutation.


def _execute_propose_document_page_correction(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.document_workspace_service import DocumentPageRevisionService

    service = DocumentPageRevisionService(settings)
    return service.save_draft(
        target_public_id,
        int(payload["page_number"]),
        payload["cleaned_text"],
        admin_id,
        change_summary=payload.get("change_summary", ""),
        correction_types=payload.get("correction_types") or [],
    )


def _execute_propose_document_ocr_rerun(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.document_workspace_service import DocumentPageReviewService

    service = DocumentPageReviewService(settings)
    return service.request_ocr_rerun(
        target_public_id, int(payload["page_number"]), admin_id, payload.get("ocr_language")
    )


def _execute_propose_bulk_cleanup(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.document_workspace_service import DocumentCleanupService

    service = DocumentCleanupService(settings)
    return service.review_repeated_element(
        target_public_id,
        payload["element_public_id"],
        payload["action"],
        admin_id,
        confirm=True,
        target_pages=payload.get("target_pages"),
    )


def _execute_propose_tamil_corrections(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.models.documents import TamilQualityReviewAction
    from backend.services.document_tamil_quality_service import DocumentTamilQualityService

    service = DocumentTamilQualityService(settings)
    review_action = TamilQualityReviewAction(
        action=payload["action"],
        edited_text=payload.get("edited_text"),
        apply_to_exact_duplicates_only=bool(payload.get("apply_to_exact_duplicates_only", False)),
        notes=payload.get("notes", ""),
    )
    return service.review(target_public_id, payload["issue_public_id"], review_action, admin_id)


def _execute_propose_chunk_generation(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.semantic_chunk_service import SemanticChunkService

    return SemanticChunkService(settings).generate(target_public_id, admin_id)


def _execute_propose_sft_candidate_generation(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.models.documents import SftCandidateGenerationRequest
    from backend.services.document_sft_candidate_service import (
        DocumentSftCandidateGenerationService,
    )

    service = DocumentSftCandidateGenerationService(settings)
    request = SftCandidateGenerationRequest(
        chunk_public_ids=payload.get("chunk_public_ids"),
        max_candidates=payload.get("max_candidates"),
    )
    return service.generate(target_public_id, request, admin_id)


def _execute_propose_candidate_status_change(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.models.documents import SftCandidateReviewAction
    from backend.services.document_sft_candidate_service import (
        DocumentSftCandidateGenerationService,
    )

    service = DocumentSftCandidateGenerationService(settings)
    review_action = SftCandidateReviewAction(
        action=payload["action"],
        edited_instruction=payload.get("edited_instruction"),
        edited_context=payload.get("edited_context"),
        edited_response=payload.get("edited_response"),
        notes=payload.get("notes", ""),
    )
    return service.review(
        payload["document_public_id"], target_public_id, review_action, admin_id
    )


def _execute_propose_sft_export(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.document_sft_export_service import DocumentSftExportService

    return DocumentSftExportService(settings).export(target_public_id, admin_id)


def _execute_propose_dataset_version_handoff(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    """Records a governed readiness note pointing at an existing SFT
    export -- does not itself create a dataset version. Ingesting
    approved document SFT candidates into the generic corpus/dataset
    record pool so the existing `DatasetVersioningService` can select
    them is disclosed as deferred (see
    docs/data_studio/document_sft_workflow_completion_plan.md section 5);
    this action gives the admin a real, audited pointer to act on via
    the existing Datasets page rather than fabricating an automatic
    handoff that was not actually built."""

    from backend.services.document_sft_export_service import DocumentSftExportService

    export = DocumentSftExportService(settings).get_export(payload["export_public_id"])
    return {
        "recorded": True,
        "document_public_id": target_public_id,
        "export_public_id": export["public_id"],
        "record_count": export["record_count"],
        "checksum_sha256": export["checksum_sha256"],
        "next_action": "create a dataset version from this export via the Datasets page",
        "acknowledged_by_admin_public_id": admin_id,
    }


# -- Document SFT workflow finalization -------------------------------------
# target_public_id is document_public_id for every action here except
# propose_document_tamil_rule_entry, whose target is the created rule's own
# public_id (there is no document to anchor a global correction rule to).


def _execute_propose_sft_export_validation(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del admin_id
    from backend.services.document_sft_export_service import DocumentSftExportService

    return DocumentSftExportService(settings).validate_export(payload["export_public_id"])


def _execute_propose_sft_dataset_ingestion(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.document_sft_dataset_handoff_service import (
        DocumentSftDatasetHandoffService,
    )

    del target_public_id
    return DocumentSftDatasetHandoffService(settings).ingest(payload["export_public_id"], admin_id)


def _execute_propose_sft_dataset_version_build(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    """Creates the dataset-version *build proposal* only (a draft record) --
    never calls `run_build()`. Building/finalizing the version is a separate,
    direct Admin action on the Datasets page; the Admin Assistant must never
    approve a final dataset version (rule 23)."""

    from backend.services.document_sft_dataset_handoff_service import (
        DocumentSftDatasetHandoffService,
    )

    del target_public_id
    return DocumentSftDatasetHandoffService(settings).propose_dataset_version(
        payload["handoff_public_id"], payload["dataset_name"], payload["dataset_version"], admin_id
    )


def _execute_propose_sft_task_generation(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.models.documents import SftCandidateGenerationRequest
    from backend.services.document_sft_candidate_service import (
        DocumentSftCandidateGenerationService,
    )

    request = SftCandidateGenerationRequest(
        chunk_public_ids=payload.get("chunk_public_ids"),
        max_candidates=payload.get("max_candidates"),
    )
    return DocumentSftCandidateGenerationService(settings).generate(
        target_public_id, request, admin_id
    )


def _execute_propose_document_cleanup_scan(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload, admin_id
    from backend.services.document_workspace_service import DocumentCleanupService

    return DocumentCleanupService(settings).detect_repeated_elements(target_public_id)


def _execute_propose_document_tamil_rule_entry(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    """Always creates in `draft` status -- the Admin Assistant can propose a
    rule entry but can never activate one (rule 23). Created under
    `target_public_id` itself (the proposal's own target identifier) so the
    stale-check/verify fingerprint can find the real row afterward."""

    from backend.services.document_tamil_correction_registry_service import (
        DocumentTamilCorrectionRegistryService,
    )

    service = DocumentTamilCorrectionRegistryService(settings)
    return service.create_rule(
        public_id=target_public_id,
        incorrect_form=payload["incorrect_form"],
        approved_correction=payload["approved_correction"],
        issue_category=payload["issue_category"],
        evidence=payload.get("evidence", ""),
        confidence_band=payload.get("confidence_band", "medium"),
        meaning_change_risk=payload["meaning_change_risk"],
        admin_id=admin_id,
    )


def _execute_propose_document_security_review(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    del payload
    from backend.services.document_security_review_service import DocumentSecurityReviewService

    return DocumentSecurityReviewService(settings).scan_document(target_public_id, admin_id)


def _execute_propose_document_pii_exclusion(
    settings: Settings, target_public_id: str, payload: dict[str, Any], admin_id: str
) -> dict[str, Any]:
    from backend.services.document_security_review_service import DocumentSecurityReviewService

    service = DocumentSecurityReviewService(settings)
    return service.review(
        target_public_id, payload["finding_public_id"], payload.get("action", "reviewed"), admin_id
    )


ACTION_EXECUTORS: dict[str, ActionExecutor] = {
    "dataset_record_review": _execute_dataset_record_review,
    "dataset_source_update": _execute_dataset_source_update,
    "governance_target_approval_override": _execute_governance_target_approval_override,
    "register_external_data_provider": _execute_register_external_data_provider,
    "verify_external_data_provider": _execute_verify_external_data_provider,
    "test_external_data_provider_connection": _execute_test_external_data_provider_connection,
    "enable_external_data_provider": _execute_enable_external_data_provider,
    "disable_external_data_provider": _execute_disable_external_data_provider,
    "configure_provider_credential_reference": _execute_configure_provider_credential_reference,
    "run_dataset_search": _execute_run_dataset_search,
    "exclude_dataset_candidate": _execute_exclude_dataset_candidate,
    "create_dataset_verification_case": _execute_create_dataset_verification_case,
    "collect_dataset_licence_evidence": _execute_collect_dataset_licence_evidence,
    "add_manual_dataset_evidence": _execute_add_manual_dataset_evidence,
    "assess_dataset_permissions": _execute_assess_dataset_permissions,
    "review_dataset_permission": _execute_review_dataset_permission,
    "resolve_dataset_verification_conflict": _execute_resolve_dataset_verification_conflict,
    "finalize_dataset_verification_report": _execute_finalize_dataset_verification_report,
    "reverify_dataset_evidence": _execute_reverify_dataset_evidence,
    "record_dataset_withdrawal_notice": _execute_record_dataset_withdrawal_notice,
    "link_dataset_verification_rights": _execute_link_dataset_verification_rights,
    "create_sample_import": _execute_create_sample_import,
    "request_sample_import_approval": _execute_request_sample_import_approval,
    "approve_sample_import": _execute_approve_sample_import,
    "download_approved_sample": _execute_download_approved_sample,
    "validate_sample_files": _execute_validate_sample_files,
    "extract_sample_archive": _execute_extract_sample_archive,
    "scan_sample": _execute_scan_sample,
    "parse_sample": _execute_parse_sample,
    "run_sample_quality_checks": _execute_run_sample_quality_checks,
    "run_sample_duplicate_checks": _execute_run_sample_duplicate_checks,
    "run_sample_contamination_checks": _execute_run_sample_contamination_checks,
    "review_sample_issue": _execute_review_sample_issue,
    "finalize_sample_validation_report": _execute_finalize_sample_validation_report,
    "request_sample_deletion": _execute_request_sample_deletion,
    "execute_sample_deletion": _execute_execute_sample_deletion,
    "create_rag_sandbox_experiment": _execute_create_rag_sandbox_experiment,
    "request_rag_sandbox_approval": _execute_request_rag_sandbox_approval,
    "approve_rag_sandbox_experiment": _execute_approve_rag_sandbox_experiment,
    "prepare_rag_sandbox_corpus": _execute_prepare_rag_sandbox_corpus,
    "build_rag_sandbox_index": _execute_build_rag_sandbox_index,
    "create_rag_sandbox_query_set": _execute_create_rag_sandbox_query_set,
    "finalize_rag_sandbox_query_set": _execute_finalize_rag_sandbox_query_set,
    "run_rag_sandbox_retrieval": _execute_run_rag_sandbox_retrieval,
    "run_rag_sandbox_generation": _execute_run_rag_sandbox_generation,
    "run_rag_sandbox_evaluation": _execute_run_rag_sandbox_evaluation,
    "review_rag_sandbox_query": _execute_review_rag_sandbox_query,
    "finalize_rag_sandbox_report": _execute_finalize_rag_sandbox_report,
    "accept_rag_sandbox": _execute_accept_rag_sandbox,
    "reject_rag_sandbox": _execute_reject_rag_sandbox,
    "request_rag_sandbox_deletion": _execute_request_rag_sandbox_deletion,
    "execute_rag_sandbox_deletion": _execute_execute_rag_sandbox_deletion,
    "assess_language_sample_suitability": _execute_assess_language_sample_suitability,
    "run_language_sample_suitability_check": _execute_run_language_sample_suitability_check,
    "acknowledge_language_sample_assessment": _execute_acknowledge_language_sample_assessment,
    "transform_language_sample_candidate": _execute_transform_language_sample_candidate,
    "review_language_sample_candidate": _execute_review_language_sample_candidate,
    "create_replay_data_plan": _execute_create_replay_data_plan,
    "create_dataset_promotion_request": _execute_create_dataset_promotion_request,
    "submit_dataset_promotion_request": _execute_submit_dataset_promotion_request,
    "create_production_rag_promotion_request": _execute_create_production_rag_promotion_request,
    "submit_production_rag_promotion_request": _execute_submit_production_rag_promotion_request,
    "create_production_model_release_request": (
        _execute_create_production_model_release_request
    ),
    "submit_production_model_release_request": (
        _execute_submit_production_model_release_request
    ),
    "check_production_release_candidate_artifact_security": (
        _execute_check_production_release_candidate_artifact_security
    ),
    "run_production_api_abuse_readiness_check": _execute_run_production_api_abuse_readiness_check,
    "run_production_secret_redaction_check": _execute_run_production_secret_redaction_check,
    "compile_production_readiness_report": _execute_compile_production_readiness_report,
    "run_production_backup_readiness_check": _execute_run_production_backup_readiness_check,
    "run_production_restore_readiness_check": _execute_run_production_restore_readiness_check,
    "assess_production_backup_encryption": _execute_assess_production_backup_encryption,
    "encrypt_production_backup": _execute_encrypt_production_backup,
    "verify_production_encrypted_restore": _execute_verify_production_encrypted_restore,
    "create_knowledge_gap_research_note": _execute_create_knowledge_gap_research_note,
    "propose_gap_priority_update": _execute_propose_gap_priority_update,
    "propose_duplicate_gap_merge": _execute_propose_duplicate_gap_merge,
    "generate_daily_knowledge_gap_report": _execute_generate_daily_knowledge_gap_report,
    "propose_knowledge_gap_classification": _execute_propose_knowledge_gap_classification,
    "propose_gap_resolution": _execute_propose_gap_resolution,
    "propose_rag_research_handoff": _execute_knowledge_gap_handoff_assessment,
    "propose_capability_assessment_handoff": _execute_knowledge_gap_handoff_assessment,
    "propose_trusted_web_policy_issue": _execute_propose_trusted_web_policy_issue,
    "propose_source_block": _execute_propose_source_block,
    "propose_source_allowlist_review": _execute_propose_source_allowlist_review,
    "propose_tool_enablement_review": _execute_propose_tool_enablement_review,
    "propose_tool_permission_issue": _execute_propose_tool_permission_issue,
    "propose_document_page_correction": _execute_propose_document_page_correction,
    "propose_document_ocr_rerun": _execute_propose_document_ocr_rerun,
    "propose_bulk_cleanup": _execute_propose_bulk_cleanup,
    "propose_tamil_corrections": _execute_propose_tamil_corrections,
    "propose_chunk_generation": _execute_propose_chunk_generation,
    "propose_sft_candidate_generation": _execute_propose_sft_candidate_generation,
    "propose_candidate_status_change": _execute_propose_candidate_status_change,
    "propose_sft_export": _execute_propose_sft_export,
    "propose_dataset_version_handoff": _execute_propose_dataset_version_handoff,
    "propose_sft_export_validation": _execute_propose_sft_export_validation,
    "propose_sft_dataset_ingestion": _execute_propose_sft_dataset_ingestion,
    "propose_sft_dataset_version_build": _execute_propose_sft_dataset_version_build,
    "propose_sft_task_generation": _execute_propose_sft_task_generation,
    "propose_document_cleanup_scan": _execute_propose_document_cleanup_scan,
    "propose_document_tamil_rule_entry": _execute_propose_document_tamil_rule_entry,
    "propose_document_security_review": _execute_propose_document_security_review,
    "propose_document_pii_exclusion": _execute_propose_document_pii_exclusion,
}

# Defense in depth: even if a future action executor is registered above,
# refuse to run anything whose name suggests it starts or resumes a
# training run. The Admin Assistant must never start model training.
_BLOCKED_ACTION_SUBSTRINGS = BLOCKED_ACTION_SUBSTRINGS


def _fingerprint_dataset_record_review(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
    try:
        record = service.get_record(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "status": record.get("status"), "updated_at": record.get("updated_at")}


def _fingerprint_dataset_source_update(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
    try:
        source = service.get_source(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "updated_at": source.get("updated_at"), "name": source.get("name")}


def _fingerprint_governance_target_approval_override(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.governance_service import GovernanceApprovalService

    entity_type = payload.get("entity_type", "")
    target_use = payload.get("target_use", "")
    status = GovernanceApprovalService(settings).status(entity_type, target_public_id)
    target = status.get("targets", {}).get(target_use, {})
    return {
        "decision": target.get("decision"),
        "decision_code": target.get("decision_code"),
        "is_override": target.get("is_override", False),
    }


def _fingerprint_register_external_data_provider(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.services.external_data_provider_service import ExternalDataProviderService

    existing = ExternalDataProviderService(settings).repository.get_provider_by_code(
        target_public_id
    )
    return {"exists": existing is not None}


def _fingerprint_external_data_provider_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.services.external_data_provider_service import ExternalDataProviderService

    try:
        provider = ExternalDataProviderService(settings).get_provider(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {
        "exists": True,
        "trust_status": provider["trust_status"],
        "lifecycle_status": provider["lifecycle_status"],
        "enabled": provider["enabled"],
    }


def _fingerprint_provider_credential_reference(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.external_data_provider_service import (
        ExternalDataProviderCredentialService,
    )

    credential_type = payload.get("credential_type")
    statuses = ExternalDataProviderCredentialService(settings).get_credential_status(
        target_public_id
    )
    match = next((s for s in statuses if s["credential_type"] == credential_type), None)
    return {"credential_status": match["status"] if match else "not_configured"}


def _fingerprint_dataset_search_session_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.external_dataset_discovery import (
        ExternalDatasetDiscoveryRepository,
    )

    repository = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    try:
        session = repository.get_session(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "status": session["status"], "current_stage": session["current_stage"]}


def _fingerprint_dataset_candidate_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.external_dataset_discovery import (
        ExternalDatasetDiscoveryRepository,
    )

    repository = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    try:
        candidate = repository.get_candidate(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {
        "exists": True,
        "excluded": candidate["excluded"],
        "canonical_name": candidate["canonical_name"],
    }


def _fingerprint_dataset_verification_case_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.dataset_verification import (
        DatasetVerificationRepository,
    )

    repository = DatasetVerificationRepository(settings.resolved_database_path)
    try:
        case = repository.get_case(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "status": case["status"], "locked_at": case["locked_at"]}


def _fingerprint_dataset_permission_review(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.dataset_verification import (
        DatasetVerificationRepository,
    )

    repository = DatasetVerificationRepository(settings.resolved_database_path)
    try:
        case = repository.get_case(target_public_id)
    except NotFoundError:
        return {"exists": False}
    assessment = repository.get_permission_assessment(target_public_id, payload["permission_type"])
    return {
        "exists": True,
        "case_locked_at": case["locked_at"],
        "current_status": assessment["status"] if assessment else None,
    }


def _fingerprint_dataset_verification_conflict(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.dataset_verification import (
        DatasetVerificationRepository,
    )

    repository = DatasetVerificationRepository(settings.resolved_database_path)
    try:
        case = repository.get_case(target_public_id)
        event = repository.get_event(payload["conflict_public_id"])
    except NotFoundError:
        return {"exists": False}
    return {
        "exists": True,
        "case_locked_at": case["locked_at"],
        "event_type": event["event_type"],
        "resolution_status": event["resolution_status"],
    }


def _fingerprint_dataset_source_rights_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.data_sources import DataSourceRepository, public_row
    from backend.services.data_source_service import SourceRightsService

    repository = DataSourceRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            source = public_row(repository.source(connection, target_public_id))
    except NotFoundError:
        return {"exists": False}
    rights = SourceRightsService(repository, settings).get(target_public_id)
    return {
        "exists": True,
        "source_status": source.get("status"),
        "rights_status": rights.get("rights_status") if rights else None,
    }


def _fingerprint_sample_import_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )

    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    try:
        sample_import = repository.get_sample_import(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {
        "exists": True,
        "status": sample_import["status"],
        "locked_at": sample_import["locked_at"],
    }


def _fingerprint_rag_sandbox_experiment_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.rag_sandbox import RagSandboxRepository

    repository = RagSandboxRepository(settings.resolved_database_path)
    try:
        experiment = repository.get_experiment(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {
        "exists": True,
        "status": experiment["status"],
        "current_stage": experiment["current_stage"],
        "accepted_record_checksum_set_hash": experiment["accepted_record_checksum_set_hash"],
    }


def _fingerprint_training_data_assessment_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.training_incremental import TrainingIncrementalRepository

    repository = TrainingIncrementalRepository(settings.resolved_database_path)
    try:
        assessment = repository.get_assessment(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {
        "exists": True,
        "status": assessment["status"],
        "current_stage": assessment["current_stage"],
    }


def _fingerprint_training_data_assessment_item_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.training_incremental import TrainingIncrementalRepository

    repository = TrainingIncrementalRepository(settings.resolved_database_path)
    try:
        item = repository.get_item(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "suitability_status": item["suitability_status"]}


def _fingerprint_training_example_candidate_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.training_incremental import TrainingIncrementalRepository

    repository = TrainingIncrementalRepository(settings.resolved_database_path)
    try:
        candidate = repository.get_candidate(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {
        "exists": True,
        "review_status": candidate["review_status"],
        "candidate_checksum": candidate["candidate_checksum"],
    }


def _fingerprint_training_dataset_promotion_request_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.training_incremental import TrainingIncrementalRepository

    repository = TrainingIncrementalRepository(settings.resolved_database_path)
    try:
        request = repository.get_promotion_request(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "status": request["status"]}


def _fingerprint_incremental_training_checkpoint_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.training_incremental import TrainingIncrementalRepository

    repository = TrainingIncrementalRepository(settings.resolved_database_path)
    try:
        checkpoint = repository.get_checkpoint(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "status": checkpoint["status"]}


def _fingerprint_production_rag_promotion_request_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.production_readiness import ProductionReadinessRepository

    repository = ProductionReadinessRepository(settings.resolved_database_path)
    try:
        request = repository.get_rag_promotion_request(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "status": request["status"]}


def _fingerprint_production_model_release_request_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.production_readiness import ProductionReadinessRepository

    repository = ProductionReadinessRepository(settings.resolved_database_path)
    try:
        request = repository.get_model_release_request(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "status": request["status"]}


def _fingerprint_model_release_candidate_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.model_release import ModelReleaseRepository

    repository = ModelReleaseRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            candidate = repository.candidate(connection, target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "status": candidate["status"]}


def _fingerprint_production_readiness_system_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    # A system-wide safety check has no per-entity state to go stale --
    # this always "exists" so the propose/confirm pipeline's stale-check
    # is a documented no-op rather than a fabricated per-entity lookup.
    del settings, target_public_id, payload
    return {"exists": True}


def _fingerprint_knowledge_gap_case(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository

    try:
        case = KnowledgeGapRepository(settings.resolved_database_path).get_case(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "status": case["status"], "updated_at": case["updated_at"]}


def _fingerprint_propose_duplicate_gap_merge(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del target_public_id
    from backend.services.knowledge_gap_merge_service import KnowledgeGapMergeService

    proposal = KnowledgeGapMergeService(settings).propose_merge(payload["case_public_ids"])
    return {"exists": True, "stale_check_fingerprint": proposal["stale_check_fingerprint"]}


def _fingerprint_document_page_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.documents import DocumentRepository

    repository = DocumentRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            document = repository.document(connection, target_public_id)
            page = repository.page(connection, document["id"], int(payload["page_number"]))
    except NotFoundError:
        return {"exists": False}
    return {
        "exists": True,
        "review_status": page["review_status"],
        "extraction_status": page["extraction_status"],
        "updated_at": page["updated_at"],
    }


def _fingerprint_document_repeated_element(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.documents import DocumentRepository

    repository = DocumentRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            document = repository.document(connection, target_public_id)
            element = connection.execute(
                "SELECT review_status FROM document_repeated_elements "
                "WHERE document_source_id=? AND public_id=?",
                (document["id"], payload["element_public_id"]),
            ).fetchone()
    except NotFoundError:
        return {"exists": False}
    if element is None:
        return {"exists": False}
    return {"exists": True, "review_status": element["review_status"]}


def _fingerprint_document_tamil_quality_issue(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.documents import DocumentRepository

    repository = DocumentRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            document = repository.document(connection, target_public_id)
            issue = repository.tamil_quality_issue(
                connection, document["id"], payload["issue_public_id"]
            )
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "review_status": issue["review_status"]}


def _fingerprint_document_chunk_count(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.documents import DocumentRepository

    repository = DocumentRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            document = repository.document(connection, target_public_id)
            count = connection.execute(
                "SELECT COUNT(*) FROM semantic_chunks WHERE document_source_id=?",
                (document["id"],),
            ).fetchone()[0]
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "chunk_count": count}


def _fingerprint_document_sft_candidate_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.documents import DocumentRepository

    repository = DocumentRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            document = repository.document(connection, target_public_id)
            rows = connection.execute(
                "SELECT quality_status,COUNT(*) count FROM document_sft_candidates "
                "WHERE document_source_id=? GROUP BY quality_status",
                (document["id"],),
            ).fetchall()
    except NotFoundError:
        return {"exists": False}
    by_quality_status = {row["quality_status"]: row["count"] for row in rows}
    return {"exists": True, "by_quality_status": by_quality_status}


def _fingerprint_document_sft_candidate_by_public_id(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.documents import DocumentRepository

    repository = DocumentRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            document = repository.document(connection, payload["document_public_id"])
            candidate = repository.sft_candidate(connection, document["id"], target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "quality_status": candidate["quality_status"]}


def _fingerprint_document_sft_export(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.document_sft_export_service import DocumentSftExportService

    if "export_public_id" not in payload:
        return {"document_public_id": target_public_id}
    try:
        export = DocumentSftExportService(settings).get_export(payload["export_public_id"])
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "record_count": export["record_count"]}


def _fingerprint_document_sft_handoff(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    export_public_id = payload.get("export_public_id")
    if not export_public_id:
        return {"document_public_id": target_public_id}
    from backend.database.repositories.documents import DocumentRepository

    repository = DocumentRepository(settings.resolved_database_path)
    with repository.transaction() as connection:
        row = connection.execute(
            "SELECT status,export_checksum_sha256 FROM document_sft_dataset_handoffs "
            "WHERE export_public_id=?",
            (export_public_id,),
        ).fetchone()
    if row is None:
        return {"exists": False}
    return {"exists": True, "status": row["status"], "checksum": row["export_checksum_sha256"]}


def _fingerprint_document_sft_generator_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.documents import DocumentRepository

    repository = DocumentRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            document = repository.document(connection, target_public_id)
            count = connection.execute(
                "SELECT COUNT(*) FROM document_sft_candidates WHERE document_source_id=?",
                (document["id"],),
            ).fetchone()[0]
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "candidate_count": count}


def _fingerprint_document_repeated_element_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.documents import DocumentRepository

    repository = DocumentRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            document = repository.document(connection, target_public_id)
            count = connection.execute(
                "SELECT COUNT(*) FROM document_repeated_elements WHERE document_source_id=?",
                (document["id"],),
            ).fetchone()[0]
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "repeated_element_count": count}


def _fingerprint_document_tamil_rule(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.database.repositories.base import NotFoundError as _NotFoundError
    from backend.services.document_tamil_correction_registry_service import (
        DocumentTamilCorrectionRegistryService,
    )

    try:
        rule = DocumentTamilCorrectionRegistryService(settings).get_rule(target_public_id)
    except _NotFoundError:
        return {"exists": False}
    return {"exists": True, "status": rule["status"]}


def _fingerprint_document_security_findings(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del payload
    from backend.services.document_security_review_service import DocumentSecurityReviewService

    try:
        summary = DocumentSecurityReviewService(settings).summary(target_public_id)
    except NotFoundError:
        return {"exists": False}
    return {"exists": True, "total_findings": summary["total_findings"]}


STALE_CHECK_FINGERPRINTS: dict[str, FingerprintFunction] = {
    "dataset_record_review": _fingerprint_dataset_record_review,
    "dataset_source_update": _fingerprint_dataset_source_update,
    "governance_target_approval_override": _fingerprint_governance_target_approval_override,
    "register_external_data_provider": _fingerprint_register_external_data_provider,
    "verify_external_data_provider": _fingerprint_external_data_provider_state,
    "test_external_data_provider_connection": _fingerprint_external_data_provider_state,
    "enable_external_data_provider": _fingerprint_external_data_provider_state,
    "disable_external_data_provider": _fingerprint_external_data_provider_state,
    "configure_provider_credential_reference": _fingerprint_provider_credential_reference,
    "run_dataset_search": _fingerprint_dataset_search_session_state,
    "exclude_dataset_candidate": _fingerprint_dataset_candidate_state,
    "create_dataset_verification_case": _fingerprint_dataset_candidate_state,
    "collect_dataset_licence_evidence": _fingerprint_dataset_verification_case_state,
    "add_manual_dataset_evidence": _fingerprint_dataset_verification_case_state,
    "assess_dataset_permissions": _fingerprint_dataset_verification_case_state,
    "review_dataset_permission": _fingerprint_dataset_permission_review,
    "resolve_dataset_verification_conflict": _fingerprint_dataset_verification_conflict,
    "finalize_dataset_verification_report": _fingerprint_dataset_verification_case_state,
    "reverify_dataset_evidence": _fingerprint_dataset_verification_case_state,
    "record_dataset_withdrawal_notice": _fingerprint_dataset_verification_case_state,
    "link_dataset_verification_rights": _fingerprint_dataset_source_rights_state,
    "create_sample_import": _fingerprint_dataset_verification_case_state,
    "request_sample_import_approval": _fingerprint_sample_import_state,
    "approve_sample_import": _fingerprint_sample_import_state,
    "download_approved_sample": _fingerprint_sample_import_state,
    "validate_sample_files": _fingerprint_sample_import_state,
    "extract_sample_archive": _fingerprint_sample_import_state,
    "scan_sample": _fingerprint_sample_import_state,
    "parse_sample": _fingerprint_sample_import_state,
    "run_sample_quality_checks": _fingerprint_sample_import_state,
    "run_sample_duplicate_checks": _fingerprint_sample_import_state,
    "run_sample_contamination_checks": _fingerprint_sample_import_state,
    "review_sample_issue": _fingerprint_sample_import_state,
    "finalize_sample_validation_report": _fingerprint_sample_import_state,
    "request_sample_deletion": _fingerprint_sample_import_state,
    "execute_sample_deletion": _fingerprint_sample_import_state,
    "create_rag_sandbox_experiment": _fingerprint_sample_import_state,
    "request_rag_sandbox_approval": _fingerprint_rag_sandbox_experiment_state,
    "approve_rag_sandbox_experiment": _fingerprint_rag_sandbox_experiment_state,
    "prepare_rag_sandbox_corpus": _fingerprint_rag_sandbox_experiment_state,
    "build_rag_sandbox_index": _fingerprint_rag_sandbox_experiment_state,
    "create_rag_sandbox_query_set": _fingerprint_rag_sandbox_experiment_state,
    "finalize_rag_sandbox_query_set": _fingerprint_rag_sandbox_experiment_state,
    "run_rag_sandbox_retrieval": _fingerprint_rag_sandbox_experiment_state,
    "run_rag_sandbox_generation": _fingerprint_rag_sandbox_experiment_state,
    "run_rag_sandbox_evaluation": _fingerprint_rag_sandbox_experiment_state,
    "review_rag_sandbox_query": _fingerprint_rag_sandbox_experiment_state,
    "finalize_rag_sandbox_report": _fingerprint_rag_sandbox_experiment_state,
    "accept_rag_sandbox": _fingerprint_rag_sandbox_experiment_state,
    "reject_rag_sandbox": _fingerprint_rag_sandbox_experiment_state,
    "request_rag_sandbox_deletion": _fingerprint_rag_sandbox_experiment_state,
    "execute_rag_sandbox_deletion": _fingerprint_rag_sandbox_experiment_state,
    "assess_language_sample_suitability": _fingerprint_rag_sandbox_experiment_state,
    "run_language_sample_suitability_check": _fingerprint_training_data_assessment_state,
    "acknowledge_language_sample_assessment": _fingerprint_training_data_assessment_state,
    "transform_language_sample_candidate": _fingerprint_training_data_assessment_item_state,
    "review_language_sample_candidate": _fingerprint_training_example_candidate_state,
    "create_replay_data_plan": _fingerprint_training_data_assessment_state,
    "create_dataset_promotion_request": _fingerprint_training_data_assessment_state,
    "submit_dataset_promotion_request": _fingerprint_training_dataset_promotion_request_state,
    "create_production_rag_promotion_request": _fingerprint_rag_sandbox_experiment_state,
    "submit_production_rag_promotion_request": (
        _fingerprint_production_rag_promotion_request_state
    ),
    "create_production_model_release_request": (
        _fingerprint_incremental_training_checkpoint_state
    ),
    "submit_production_model_release_request": (
        _fingerprint_production_model_release_request_state
    ),
    "check_production_release_candidate_artifact_security": (
        _fingerprint_model_release_candidate_state
    ),
    "run_production_api_abuse_readiness_check": _fingerprint_production_readiness_system_state,
    "run_production_secret_redaction_check": _fingerprint_production_readiness_system_state,
    "compile_production_readiness_report": _fingerprint_production_readiness_system_state,
    "run_production_backup_readiness_check": _fingerprint_production_readiness_system_state,
    "run_production_restore_readiness_check": _fingerprint_production_readiness_system_state,
    "assess_production_backup_encryption": _fingerprint_production_readiness_system_state,
    "encrypt_production_backup": _fingerprint_production_readiness_system_state,
    "verify_production_encrypted_restore": _fingerprint_production_readiness_system_state,
    "create_knowledge_gap_research_note": _fingerprint_knowledge_gap_case,
    "propose_gap_priority_update": _fingerprint_knowledge_gap_case,
    "propose_duplicate_gap_merge": _fingerprint_propose_duplicate_gap_merge,
    "generate_daily_knowledge_gap_report": _fingerprint_production_readiness_system_state,
    "propose_knowledge_gap_classification": _fingerprint_knowledge_gap_case,
    "propose_gap_resolution": _fingerprint_knowledge_gap_case,
    "propose_rag_research_handoff": _fingerprint_knowledge_gap_case,
    "propose_capability_assessment_handoff": _fingerprint_knowledge_gap_case,
    "propose_trusted_web_policy_issue": _fingerprint_production_readiness_system_state,
    "propose_source_block": _fingerprint_production_readiness_system_state,
    "propose_source_allowlist_review": _fingerprint_production_readiness_system_state,
    "propose_tool_enablement_review": _fingerprint_production_readiness_system_state,
    "propose_tool_permission_issue": _fingerprint_production_readiness_system_state,
    "propose_document_page_correction": _fingerprint_document_page_state,
    "propose_document_ocr_rerun": _fingerprint_document_page_state,
    "propose_bulk_cleanup": _fingerprint_document_repeated_element,
    "propose_tamil_corrections": _fingerprint_document_tamil_quality_issue,
    "propose_chunk_generation": _fingerprint_document_chunk_count,
    "propose_sft_candidate_generation": _fingerprint_document_sft_candidate_state,
    "propose_candidate_status_change": _fingerprint_document_sft_candidate_by_public_id,
    "propose_sft_export": _fingerprint_document_sft_candidate_state,
    "propose_dataset_version_handoff": _fingerprint_document_sft_export,
    "propose_sft_export_validation": _fingerprint_document_sft_export,
    "propose_sft_dataset_ingestion": _fingerprint_document_sft_handoff,
    "propose_sft_dataset_version_build": _fingerprint_document_sft_handoff,
    "propose_sft_task_generation": _fingerprint_document_sft_generator_state,
    "propose_document_cleanup_scan": _fingerprint_document_repeated_element_state,
    "propose_document_tamil_rule_entry": _fingerprint_document_tamil_rule,
    "propose_document_security_review": _fingerprint_document_security_findings,
    "propose_document_pii_exclusion": _fingerprint_document_security_findings,
}


def _preview_dataset_record_review(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_dataset_record_review(settings, target_public_id, payload)
    return {
        "current_state": current,
        "proposed_state": {"decision": payload.get("decision")},
    }


def _preview_dataset_source_update(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_dataset_source_update(settings, target_public_id, payload)
    return {"current_state": current, "proposed_state": payload}


def _preview_governance_target_approval_override(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_governance_target_approval_override(settings, target_public_id, payload)
    warnings = []
    if not current.get("decision") or current.get("decision") == "not_requested":
        warnings.append("no prior governance decision exists for this target use yet")
    return {
        "current_state": current,
        "proposed_state": {
            "target_use": payload.get("target_use"),
            "decision": payload.get("decision"),
            "reason": payload.get("reason"),
        },
        "warnings": warnings,
    }


def _preview_register_external_data_provider(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_register_external_data_provider(settings, target_public_id, payload)
    warnings = []
    if current["exists"]:
        warnings.append("a provider with this provider_code already exists")
    return {
        "current_state": current,
        "proposed_state": {
            "provider_code": target_public_id,
            "name": payload.get("name"),
            "provider_type": payload.get("provider_type"),
            "access_mode": payload.get("access_mode"),
        },
        "warnings": warnings,
    }


def _preview_external_data_provider_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_external_data_provider_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["provider not found"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_provider_credential_reference(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_provider_credential_reference(settings, target_public_id, payload)
    return {
        "current_state": current,
        "proposed_state": {
            "credential_type": payload.get("credential_type"),
            "reference_key": payload.get("reference_key"),
        },
        "warnings": [],
    }


def _preview_run_dataset_search(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_dataset_search_session_state(settings, target_public_id, payload)
    warnings = []
    if not current.get("exists"):
        warnings.append("search session not found")
    elif current.get("status") not in ("draft", "ready"):
        warnings.append(
            f"session status is '{current.get('status')}' -- a search can only run "
            "from draft/ready"
        )
    return {"current_state": current, "proposed_state": {"status": "running"}, "warnings": warnings}


def _preview_exclude_dataset_candidate(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_dataset_candidate_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["candidate not found"]
    return {"current_state": current, "proposed_state": {"excluded": True}, "warnings": warnings}


def _preview_create_dataset_verification_case(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_dataset_candidate_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["candidate not found"]
    return {
        "current_state": current,
        "proposed_state": {"verification_scope": payload.get("verification_scope", "")},
        "warnings": warnings,
    }


def _preview_dataset_verification_case_action(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_dataset_verification_case_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["verification case not found"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_review_dataset_permission(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_dataset_permission_review(settings, target_public_id, payload)
    warnings = []
    if not current.get("exists"):
        warnings.append("verification case not found")
    elif current.get("case_locked_at"):
        warnings.append("case is already finalized and locked")
    return {
        "current_state": current,
        "proposed_state": {
            "permission_type": payload.get("permission_type"),
            "status": payload.get("status"),
        },
        "warnings": warnings,
    }


def _preview_resolve_dataset_verification_conflict(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_dataset_verification_conflict(settings, target_public_id, payload)
    warnings = []
    if not current.get("exists"):
        warnings.append("conflict event not found")
    elif current.get("resolution_status") == "resolved":
        warnings.append("this conflict already has a recorded resolution")
    return {
        "current_state": current,
        "proposed_state": {"resolution_status": payload.get("resolution_status")},
        "warnings": warnings,
    }


def _preview_link_dataset_verification_rights(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_dataset_source_rights_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["data source not found"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_create_sample_import(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_dataset_verification_case_state(settings, target_public_id, payload)
    warnings = []
    if not current.get("exists"):
        warnings.append("verification case not found")
    elif current.get("locked_at") is None:
        warnings.append("verification case is not yet finalized -- sample import is not eligible")
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_sample_import_action(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_sample_import_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["sample import not found"]
    if current.get("exists") and current.get("locked_at") is not None:
        warnings.append("this sample import is already finalized")
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_create_rag_sandbox_experiment(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_sample_import_state(settings, target_public_id, payload)
    warnings = []
    if not current.get("exists"):
        warnings.append("sample import not found")
    elif current.get("locked_at") is None:
        warnings.append(
            "Phase 12 sample import is not yet finalized -- rag sandbox is not eligible"
        )
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_rag_sandbox_action(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_rag_sandbox_experiment_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["rag sandbox experiment not found"]
    if current.get("exists") and current.get("status") in (
        "rejected", "failed", "cancelled", "expired", "withdrawn", "deleted",
    ):
        warnings.append(f"this experiment is already '{current.get('status')}'")
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_assess_language_sample_suitability(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_rag_sandbox_experiment_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["rag sandbox experiment not found"]
    if current.get("exists") and current.get("status") not in (
        "accepted", "accepted_with_conditions",
    ):
        warnings.append(
            "this experiment has no accepted RAG sandbox report -- an assessment can still be "
            "created, but only accepted reports satisfy Phase 14's eligibility gate"
        )
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_training_data_assessment_action(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_training_data_assessment_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["training data assessment not found"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_transform_language_sample_candidate(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_training_data_assessment_item_state(
        settings, target_public_id, payload
    )
    warnings = [] if current.get("exists") else ["assessment item not found"]
    if current.get("exists") and current.get("suitability_status") in (
        "evaluation_only", "rag_only", "not_suitable", "blocked", "not_assessed",
    ):
        warnings.append(
            f"item suitability_status is '{current.get('suitability_status')}' -- transformation "
            "will be rejected"
        )
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_review_language_sample_candidate(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_training_example_candidate_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["training example candidate not found"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_submit_dataset_promotion_request(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_training_dataset_promotion_request_state(
        settings, target_public_id, payload
    )
    warnings = [] if current.get("exists") else ["dataset promotion request not found"]
    if current.get("exists") and current.get("status") != "draft":
        warnings.append(f"this request is already '{current.get('status')}', not 'draft'")
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_create_production_rag_promotion_request(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_rag_sandbox_experiment_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["rag sandbox experiment not found"]
    if current.get("exists") and current.get("status") not in (
        "accepted", "accepted_with_conditions",
    ):
        warnings.append(
            "this experiment has no accepted RAG sandbox report -- production RAG eligibility "
            "will fail"
        )
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_submit_production_rag_promotion_request(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_production_rag_promotion_request_state(
        settings, target_public_id, payload
    )
    warnings = [] if current.get("exists") else ["production rag promotion request not found"]
    if current.get("exists") and current.get("status") != "draft":
        warnings.append(f"this request is already '{current.get('status')}', not 'draft'")
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_create_production_model_release_request(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_incremental_training_checkpoint_state(
        settings, target_public_id, payload
    )
    warnings = [] if current.get("exists") else ["incremental training checkpoint not found"]
    if current.get("exists") and current.get("status") != "accepted_candidate":
        warnings.append(
            f"this checkpoint's status is '{current.get('status')}', not 'accepted_candidate' "
            "-- eligibility will fail"
        )
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_submit_production_model_release_request(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_production_model_release_request_state(
        settings, target_public_id, payload
    )
    warnings = [] if current.get("exists") else ["production model release request not found"]
    if current.get("exists") and current.get("status") != "draft":
        warnings.append(f"this request is already '{current.get('status')}', not 'draft'")
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_check_production_release_candidate_artifact_security(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_model_release_candidate_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["model release candidate not found"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_production_readiness_system_action(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_production_readiness_system_state(settings, target_public_id, payload)
    return {"current_state": current, "proposed_state": payload, "warnings": []}


def _preview_knowledge_gap_case_action(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_knowledge_gap_case(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["knowledge-gap case not found"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_propose_duplicate_gap_merge(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del target_public_id
    from backend.services.knowledge_gap_merge_service import KnowledgeGapMergeService

    proposal = KnowledgeGapMergeService(settings).propose_merge(payload["case_public_ids"])
    warnings = (
        []
        if proposal["decisions"]
        else ["no automatic duplicate match found -- review manually before confirming"]
    )
    return {"current_state": proposal, "proposed_state": payload, "warnings": warnings}


def _preview_document_page_state(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_page_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["document page not found"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_document_repeated_element(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_repeated_element(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["repeated-element suggestion not found"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_document_tamil_quality_issue(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_tamil_quality_issue(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["Tamil quality issue not found"]
    if current.get("review_status") not in (None, "pending"):
        warnings.append("this issue has already been reviewed")
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_document_chunk_generation(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_chunk_count(settings, target_public_id, payload)
    warnings = []
    if current.get("chunk_count"):
        warnings.append(
            "chunks already exist for this document -- regeneration behavior depends on the "
            "existing chunk service's own rules"
        )
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_document_sft_candidate_generation(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_sft_candidate_state(settings, target_public_id, payload)
    return {"current_state": current, "proposed_state": payload, "warnings": []}


def _preview_document_candidate_status_change(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_sft_candidate_by_public_id(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["SFT candidate not found"]
    if current.get("quality_status") in ("approved", "rejected"):
        warnings.append("this candidate has already reached a final review decision")
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_document_sft_export(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_sft_candidate_state(settings, target_public_id, payload)
    approved = current.get("by_quality_status", {}).get("approved", 0)
    warnings = [] if approved else ["no approved SFT candidates are available to export"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_document_dataset_version_handoff(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_sft_export(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["referenced SFT export not found"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_document_sft_handoff(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_sft_handoff(settings, target_public_id, payload)
    warnings = []
    if current.get("exists") and current.get("status") == "version_built":
        warnings.append("this export has already reached a built dataset version")
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_document_sft_task_generation(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_sft_generator_state(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["document not found"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


def _preview_document_cleanup_scan(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_repeated_element_state(settings, target_public_id, payload)
    return {"current_state": current, "proposed_state": payload, "warnings": []}


def _preview_document_tamil_rule_entry(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    del target_public_id
    warnings = []
    if payload.get("meaning_change_risk") in ("meaning_sensitive", "ambiguous"):
        warnings.append(
            "meaning-sensitive/ambiguous rules always require mandatory human review before "
            "activation"
        )
    return {"current_state": {}, "proposed_state": payload, "warnings": warnings}


def _preview_document_security_review(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_security_findings(settings, target_public_id, payload)
    return {"current_state": current, "proposed_state": payload, "warnings": []}


def _preview_document_pii_exclusion(
    settings: Settings, target_public_id: str, payload: dict[str, Any]
) -> dict[str, Any]:
    current = _fingerprint_document_security_findings(settings, target_public_id, payload)
    warnings = [] if current.get("exists") else ["no security findings recorded for this document"]
    return {"current_state": current, "proposed_state": payload, "warnings": warnings}


PREVIEW_GENERATORS: dict[str, PreviewGenerator] = {
    "dataset_record_review": _preview_dataset_record_review,
    "dataset_source_update": _preview_dataset_source_update,
    "governance_target_approval_override": _preview_governance_target_approval_override,
    "register_external_data_provider": _preview_register_external_data_provider,
    "verify_external_data_provider": _preview_external_data_provider_state,
    "test_external_data_provider_connection": _preview_external_data_provider_state,
    "enable_external_data_provider": _preview_external_data_provider_state,
    "disable_external_data_provider": _preview_external_data_provider_state,
    "configure_provider_credential_reference": _preview_provider_credential_reference,
    "run_dataset_search": _preview_run_dataset_search,
    "exclude_dataset_candidate": _preview_exclude_dataset_candidate,
    "create_dataset_verification_case": _preview_create_dataset_verification_case,
    "collect_dataset_licence_evidence": _preview_dataset_verification_case_action,
    "add_manual_dataset_evidence": _preview_dataset_verification_case_action,
    "assess_dataset_permissions": _preview_dataset_verification_case_action,
    "review_dataset_permission": _preview_review_dataset_permission,
    "resolve_dataset_verification_conflict": _preview_resolve_dataset_verification_conflict,
    "finalize_dataset_verification_report": _preview_dataset_verification_case_action,
    "reverify_dataset_evidence": _preview_dataset_verification_case_action,
    "record_dataset_withdrawal_notice": _preview_dataset_verification_case_action,
    "link_dataset_verification_rights": _preview_link_dataset_verification_rights,
    "create_sample_import": _preview_create_sample_import,
    "request_sample_import_approval": _preview_sample_import_action,
    "approve_sample_import": _preview_sample_import_action,
    "download_approved_sample": _preview_sample_import_action,
    "validate_sample_files": _preview_sample_import_action,
    "extract_sample_archive": _preview_sample_import_action,
    "scan_sample": _preview_sample_import_action,
    "parse_sample": _preview_sample_import_action,
    "run_sample_quality_checks": _preview_sample_import_action,
    "run_sample_duplicate_checks": _preview_sample_import_action,
    "run_sample_contamination_checks": _preview_sample_import_action,
    "review_sample_issue": _preview_sample_import_action,
    "finalize_sample_validation_report": _preview_sample_import_action,
    "request_sample_deletion": _preview_sample_import_action,
    "execute_sample_deletion": _preview_sample_import_action,
    "create_rag_sandbox_experiment": _preview_create_rag_sandbox_experiment,
    "request_rag_sandbox_approval": _preview_rag_sandbox_action,
    "approve_rag_sandbox_experiment": _preview_rag_sandbox_action,
    "prepare_rag_sandbox_corpus": _preview_rag_sandbox_action,
    "build_rag_sandbox_index": _preview_rag_sandbox_action,
    "create_rag_sandbox_query_set": _preview_rag_sandbox_action,
    "finalize_rag_sandbox_query_set": _preview_rag_sandbox_action,
    "run_rag_sandbox_retrieval": _preview_rag_sandbox_action,
    "run_rag_sandbox_generation": _preview_rag_sandbox_action,
    "run_rag_sandbox_evaluation": _preview_rag_sandbox_action,
    "review_rag_sandbox_query": _preview_rag_sandbox_action,
    "finalize_rag_sandbox_report": _preview_rag_sandbox_action,
    "accept_rag_sandbox": _preview_rag_sandbox_action,
    "reject_rag_sandbox": _preview_rag_sandbox_action,
    "request_rag_sandbox_deletion": _preview_rag_sandbox_action,
    "execute_rag_sandbox_deletion": _preview_rag_sandbox_action,
    "assess_language_sample_suitability": _preview_assess_language_sample_suitability,
    "run_language_sample_suitability_check": _preview_training_data_assessment_action,
    "acknowledge_language_sample_assessment": _preview_training_data_assessment_action,
    "transform_language_sample_candidate": _preview_transform_language_sample_candidate,
    "review_language_sample_candidate": _preview_review_language_sample_candidate,
    "create_replay_data_plan": _preview_training_data_assessment_action,
    "create_dataset_promotion_request": _preview_training_data_assessment_action,
    "submit_dataset_promotion_request": _preview_submit_dataset_promotion_request,
    "create_production_rag_promotion_request": _preview_create_production_rag_promotion_request,
    "submit_production_rag_promotion_request": (
        _preview_submit_production_rag_promotion_request
    ),
    "create_production_model_release_request": (
        _preview_create_production_model_release_request
    ),
    "submit_production_model_release_request": (
        _preview_submit_production_model_release_request
    ),
    "check_production_release_candidate_artifact_security": (
        _preview_check_production_release_candidate_artifact_security
    ),
    "run_production_api_abuse_readiness_check": _preview_production_readiness_system_action,
    "run_production_secret_redaction_check": _preview_production_readiness_system_action,
    "compile_production_readiness_report": _preview_production_readiness_system_action,
    "run_production_backup_readiness_check": _preview_production_readiness_system_action,
    "run_production_restore_readiness_check": _preview_production_readiness_system_action,
    "assess_production_backup_encryption": _preview_production_readiness_system_action,
    "encrypt_production_backup": _preview_production_readiness_system_action,
    "verify_production_encrypted_restore": _preview_production_readiness_system_action,
    "create_knowledge_gap_research_note": _preview_knowledge_gap_case_action,
    "propose_gap_priority_update": _preview_knowledge_gap_case_action,
    "propose_duplicate_gap_merge": _preview_propose_duplicate_gap_merge,
    "generate_daily_knowledge_gap_report": _preview_production_readiness_system_action,
    "propose_knowledge_gap_classification": _preview_knowledge_gap_case_action,
    "propose_gap_resolution": _preview_knowledge_gap_case_action,
    "propose_rag_research_handoff": _preview_knowledge_gap_case_action,
    "propose_capability_assessment_handoff": _preview_knowledge_gap_case_action,
    "propose_trusted_web_policy_issue": _preview_production_readiness_system_action,
    "propose_source_block": _preview_production_readiness_system_action,
    "propose_source_allowlist_review": _preview_production_readiness_system_action,
    "propose_tool_enablement_review": _preview_production_readiness_system_action,
    "propose_tool_permission_issue": _preview_production_readiness_system_action,
    "propose_document_page_correction": _preview_document_page_state,
    "propose_document_ocr_rerun": _preview_document_page_state,
    "propose_bulk_cleanup": _preview_document_repeated_element,
    "propose_tamil_corrections": _preview_document_tamil_quality_issue,
    "propose_chunk_generation": _preview_document_chunk_generation,
    "propose_sft_candidate_generation": _preview_document_sft_candidate_generation,
    "propose_candidate_status_change": _preview_document_candidate_status_change,
    "propose_sft_export": _preview_document_sft_export,
    "propose_dataset_version_handoff": _preview_document_dataset_version_handoff,
    "propose_sft_export_validation": _preview_document_sft_export,
    "propose_sft_dataset_ingestion": _preview_document_sft_handoff,
    "propose_sft_dataset_version_build": _preview_document_sft_handoff,
    "propose_sft_task_generation": _preview_document_sft_task_generation,
    "propose_document_cleanup_scan": _preview_document_cleanup_scan,
    "propose_document_tamil_rule_entry": _preview_document_tamil_rule_entry,
    "propose_document_security_review": _preview_document_security_review,
    "propose_document_pii_exclusion": _preview_document_pii_exclusion,
}


class AdminAssistantError(BrudError):
    """Raised for governance violations (unknown/blocked action, bad state)."""

    status_code = 422
    code = "admin_assistant_rejected"


class AdminAssistantService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.database_path = settings.resolved_database_path
        self.approvals = AdminApprovalRepository(self.database_path)
        self._audit = (
            AuditLogRepository(self.database_path) if settings.audit_enabled else None
        )

    # -- audit -------------------------------------------------------

    def _record_audit(
        self,
        *,
        event_type: str,
        action: str,
        actor_reference: str | None,
        resource_public_id: str | None,
        outcome: AuditOutcome,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not self._audit:
            return
        try:
            self._audit.append(
                AuditEventCreate(
                    event_type=event_type,
                    actor_type="admin_assistant",
                    actor_reference=actor_reference,
                    action=action,
                    resource_type="admin_approval",
                    resource_public_id=resource_public_id,
                    outcome=outcome,
                    metadata=metadata or {},
                )
            )
        except Exception:
            logger.exception("admin_assistant_audit_write_failed", extra={"action": action})

    # -- dashboard understanding (read-only) --------------------------

    def dashboard_overview(self) -> dict[str, Any]:
        """Summarize the state of every governed area of the Admin Dashboard.

        Purely read-only: counts and status breakdowns the assistant uses
        to explain "what needs attention" and to guide the admin step by
        step. Never mutates anything.
        """

        with database_connection(self.database_path) as connection:

            def counts_by(table: str, column: str = "status") -> dict[str, int]:
                rows = connection.execute(
                    f"SELECT {column} AS bucket, COUNT(*) AS n FROM {table} GROUP BY {column}"
                ).fetchall()
                return {row["bucket"]: row["n"] for row in rows}

            def table_exists(table: str) -> bool:
                return bool(
                    connection.execute(
                        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                    ).fetchone()
                )

            overview: dict[str, Any] = {
                "dataset_sources": counts_by("dataset_sources"),
                "dataset_records": counts_by("dataset_records"),
                "training_jobs": counts_by("training_jobs"),
                "model_registry": counts_by("model_registry", "status"),
                "user_feedback": counts_by("user_feedback"),
                "admin_approvals": counts_by("admin_approvals"),
            }
            if table_exists("corpus_releases"):
                overview["corpus_releases"] = counts_by("corpus_releases")
            if table_exists("model_versions"):
                overview["model_versions"] = counts_by("model_versions", "lifecycle_status")

        pending_review = overview["dataset_records"].get("pending_review", 0)
        pending_approvals = overview["admin_approvals"].get("pending", 0)
        guidance: list[str] = []
        if pending_review:
            guidance.append(
                f"{pending_review} dataset record(s) are pending_review -- inspect and either "
                "propose approve/reject decisions."
            )
        if pending_approvals:
            guidance.append(
                f"{pending_approvals} Admin Assistant proposal(s) are awaiting Admin Review "
                "before they can execute."
            )
        if not guidance:
            guidance.append("No pending dataset reviews or proposals right now.")

        return {"summary": overview, "guidance": guidance}

    # -- proposals -----------------------------------------------------

    def propose(
        self,
        *,
        action_type: str,
        target_type: str,
        target_public_id: str,
        request_payload: dict[str, Any],
        requested_by: str,
        summary: str,
    ) -> AdminApprovalPublic:
        if action_type not in ACTION_EXECUTORS or not is_known_action_type(action_type):
            raise AdminAssistantError(f"unsupported action_type: {action_type}")
        if any(token in action_type.lower() for token in _BLOCKED_ACTION_SUBSTRINGS):
            raise AdminAssistantError(f"action_type is not permitted: {action_type}")
        definition = get_action_definition(action_type)
        risk_level = definition.risk_level if definition else "moderate"
        reason_given = str(request_payload.get("reason", "")).strip()
        if definition and definition.requires_reason and not reason_given:
            raise AdminAssistantError(
                f"action_type {action_type} requires a non-empty 'reason' in request_payload"
            )

        preview_generator = PREVIEW_GENERATORS.get(action_type)
        preview = (
            preview_generator(self.settings, target_public_id, request_payload)
            if preview_generator is not None
            else {}
        )
        fingerprint_fn = STALE_CHECK_FINGERPRINTS.get(action_type)
        stale_check = (
            fingerprint_fn(self.settings, target_public_id, request_payload)
            if fingerprint_fn is not None
            else {}
        )
        expires_at = datetime.now(UTC) + timedelta(hours=PROPOSAL_PREVIEW_TTL_HOURS)

        proposal = self.approvals.create(
            AdminApprovalCreate(
                action_type=action_type,
                target_type=target_type,
                target_public_id=target_public_id,
                request_payload=request_payload,
                requested_by=requested_by,
                summary=summary,
                risk_level=risk_level,
                preview=preview,
                stale_check=stale_check,
                expires_at=expires_at,
            )
        )
        self._record_audit(
            event_type="admin_assistant_proposal_created",
            action=action_type,
            actor_reference=requested_by,
            resource_public_id=proposal.public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "target_type": target_type,
                "target_public_id": target_public_id,
                "risk_level": risk_level,
            },
        )
        return proposal

    def list_proposals(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0
    ) -> list[AdminApprovalPublic]:
        return self.approvals.list(status=status, limit=limit, offset=offset)

    def get_proposal(self, public_id: str) -> AdminApprovalPublic:
        return self.approvals.get_by_public_id(public_id)

    # -- Admin Review: approve / reject --------------------------------

    def review(
        self,
        public_id: str,
        *,
        decision: str,
        reviewed_by: str,
        comment: str | None,
    ) -> AdminApprovalPublic:
        if decision not in {"approved", "rejected"}:
            raise AdminAssistantError(f"unsupported review decision: {decision}")
        if decision == "approved":
            # The existing `review(decision='approved')` call *is* Phase 8's
            # "confirm" step (see plan.md section 2). Before letting it
            # proceed, re-read the target's current fingerprint and compare
            # it against the one captured at propose time -- a mismatch
            # means the target changed underneath this proposal (Flow N),
            # and approval is refused rather than silently proceeding
            # against a stale preview.
            proposal = self.approvals.get_by_public_id(public_id)
            if proposal.status != "pending":
                raise AdminAssistantError(
                    f"admin approval already reviewed (status={proposal.status})"
                )
            fingerprint_fn = STALE_CHECK_FINGERPRINTS.get(proposal.action_type)
            if fingerprint_fn is not None:
                current = fingerprint_fn(
                    self.settings, proposal.target_public_id, proposal.request_payload
                )
                if current != proposal.stale_check:
                    self._record_audit(
                        event_type="admin_review_rejected_stale",
                        action="approved",
                        actor_reference=reviewed_by,
                        resource_public_id=public_id,
                        outcome=AuditOutcome.DENIED,
                        metadata={"expected": proposal.stale_check, "current": current},
                    )
                    raise AdminAssistantError(
                        "the target has changed since this proposal was created -- "
                        "cancel it and propose again against current state"
                    )
        try:
            result = self.approvals.update_review(
                public_id, status=decision, reviewed_by=reviewed_by, review_comment=comment
            )
        except (NotFoundError, ValidationError) as exc:
            self._record_audit(
                event_type="admin_review_decision_failed",
                action=decision,
                actor_reference=reviewed_by,
                resource_public_id=public_id,
                outcome=AuditOutcome.FAILURE,
                metadata={"error": str(exc)},
            )
            raise
        self._record_audit(
            event_type=f"admin_review_{decision}",
            action=decision,
            actor_reference=reviewed_by,
            resource_public_id=public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"comment": comment} if comment else {},
        )
        return result

    def cancel(
        self, public_id: str, *, cancelled_by: str, reason: str | None
    ) -> AdminApprovalPublic:
        """Withdraw a still-pending proposal -- distinct from `review(
        decision='rejected')`, which is a reviewer's considered "no" on
        someone else's proposal. Activates the long-unused `cancelled`
        status (see plan.md section 1.1)."""

        try:
            result = self.approvals.cancel(public_id, cancelled_by=cancelled_by, reason=reason)
        except (NotFoundError, ValidationError) as exc:
            self._record_audit(
                event_type="admin_assistant_proposal_cancel_failed",
                action="cancel",
                actor_reference=cancelled_by,
                resource_public_id=public_id,
                outcome=AuditOutcome.FAILURE,
                metadata={"error": str(exc)},
            )
            raise
        self._record_audit(
            event_type="admin_assistant_proposal_cancelled",
            action="cancel",
            actor_reference=cancelled_by,
            resource_public_id=public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"reason": reason} if reason else {},
        )
        return result

    # -- execution: approved proposals only, via existing services -----

    def execute(self, public_id: str, *, executor_public_id: str) -> AdminApprovalPublic:
        proposal = self.approvals.get_by_public_id(public_id)
        if proposal.status != "approved":
            raise AdminAssistantError(
                f"proposal must be approved before execution (status={proposal.status})"
            )
        executor = ACTION_EXECUTORS.get(proposal.action_type)
        if executor is None or any(
            token in proposal.action_type.lower() for token in _BLOCKED_ACTION_SUBSTRINGS
        ):
            self._fail_execution(proposal, executor_public_id, "action_type not permitted")
            raise AdminAssistantError(f"action_type not permitted: {proposal.action_type}")
        try:
            result = executor(
                self.settings,
                proposal.target_public_id,
                proposal.request_payload,
                executor_public_id,
            )
        except Exception as exc:
            self._fail_execution(proposal, executor_public_id, str(exc))
            raise
        updated = self.approvals.update_execution(
            public_id,
            execution_status="succeeded",
            execution_result=result,
            executor_public_id=executor_public_id,
        )
        # Post-execution verification (rule: never claim completion before
        # the backend confirms it): re-read the target's current state via
        # the same fingerprint function used for stale-checking, and record
        # what was actually observed rather than trusting the executor's
        # return value alone.
        fingerprint_fn = STALE_CHECK_FINGERPRINTS.get(proposal.action_type)
        verified_state = (
            fingerprint_fn(self.settings, proposal.target_public_id, proposal.request_payload)
            if fingerprint_fn is not None
            else {}
        )
        self._record_audit(
            event_type="admin_assistant_proposal_executed",
            action=proposal.action_type,
            actor_reference=executor_public_id,
            resource_public_id=public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={
                "target_public_id": proposal.target_public_id,
                "verified_state": verified_state,
            },
        )
        return updated

    def _fail_execution(
        self, proposal: AdminApprovalPublic, executor_public_id: str, error: str
    ) -> None:
        try:
            self.approvals.update_execution(
                proposal.public_id,
                execution_status="failed",
                execution_result={"error": error},
                executor_public_id=executor_public_id,
            )
        except (NotFoundError, ValidationError):
            logger.exception("admin_assistant_execution_failure_write_failed")
        self._record_audit(
            event_type="admin_assistant_proposal_execution_failed",
            action=proposal.action_type,
            actor_reference=executor_public_id,
            resource_public_id=proposal.public_id,
            outcome=AuditOutcome.FAILURE,
            metadata={"error": error, "target_public_id": proposal.target_public_id},
        )
