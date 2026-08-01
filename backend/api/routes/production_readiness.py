"""Phase 15 Final Text/NLP Production Readiness API.

Admin-only, CSRF-protected, under `/api/admin/production-readiness`.
Every mutating endpoint here is a thin wrapper around one of the
Phase 15 governance services -- production RAG promotion/activation,
model release/canary/activation, artifact security, API-abuse and
secret-scan readiness, backup/restore/deployment readiness, system
health, regression, and the final readiness report/acceptance
review. No endpoint here returns a raw model checkpoint, tokenizer,
dataset file, or RAG payload -- every response is a governance/status
JSON object, never a file. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import AdminDependency, CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import DomainModel
from backend.database.repositories.base import NotFoundError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.services.production_api_abuse_readiness_service import (
    ProductionApiAbuseReadinessService,
)
from backend.services.production_artifact_security_service import ProductionArtifactSecurityService
from backend.services.production_backup_restore_readiness_service import (
    ProductionBackupEncryptionAssessmentService,
    ProductionBackupEncryptionService,
    ProductionBackupReadinessService,
    ProductionRestoreReadinessService,
)
from backend.services.production_deployment_readiness_service import (
    ProductionDeploymentReadinessService,
    ProductionSystemHealthService,
)
from backend.services.production_model_activation_service import ProductionModelActivationService
from backend.services.production_model_canary_service import ProductionModelCanaryService
from backend.services.production_model_release_approval_service import (
    ProductionModelReleaseApprovalService,
)
from backend.services.production_model_release_request_service import (
    ProductionModelReleaseEligibilityService,
    ProductionModelReleaseRequestService,
)
from backend.services.production_model_release_validation_service import (
    ProductionModelReleaseValidationService,
)
from backend.services.production_rag_activation_service import ProductionRagActivationService
from backend.services.production_rag_candidate_service import ProductionRagCandidateService
from backend.services.production_rag_eligibility_service import ProductionRagEligibilityService
from backend.services.production_rag_promotion_service import ProductionRagPromotionService
from backend.services.production_rag_validation_service import ProductionRagValidationService
from backend.services.production_readiness_report_service import (
    ProductionAcceptanceReviewService,
    ProductionReadinessReportService,
)
from backend.services.production_regression_service import ProductionRegressionService
from backend.services.production_rollback_service import ProductionRollbackPlanService
from backend.services.production_secret_scan_service import ProductionSecretScanService

router = APIRouter(
    prefix="/admin/production-readiness",
    tags=["production-readiness"],
    dependencies=[Depends(require_admin)],
)


def repository(settings: SettingsDependency) -> ProductionReadinessRepository:
    return ProductionReadinessRepository(settings.resolved_database_path)


# -- request models --------------------------------------------------------------------


class ExpiryRequest(DomainModel):
    expires_at: str | None = None


class RagPromotionRequestCreate(DomainModel):
    rag_sandbox_experiment_public_id: str
    knowledge_space_public_id: str
    selected_record_ids: list[str] = []
    chunking_configuration: dict[str, Any] = {}
    embedding_assignment_key: str | None = None
    retrieval_configuration: dict[str, Any] = {}
    generation_assignment_key: str | None = None
    citation_policy_version: str = "v1"
    grounding_policy_version: str = "v1"
    injection_policy_version: str = "v1"
    commercial_use_context: str = "unknown"
    resource_preview: dict[str, Any] = {}


class ModelReleaseRequestCreate(DomainModel):
    incremental_training_checkpoint_public_id: str
    model_release_family_public_id: str | None = None
    dataset_version_public_id: str | None = None
    label: str | None = None
    notes: str = ""
    release_type: str = "experimental"
    target_assignment_keys: list[str] = []
    canary_requested: bool = True
    canary_percentage_or_scope: str = "admin_diagnostic"


class CanaryStartBody(DomainModel):
    assignment_public_id: str
    percentage: int = 0
    max_request_count: int = 10


class CanaryExecuteBody(DomainModel):
    assignment_public_id: str
    fixture_prompts: list[str]


class CanaryStopBody(DomainModel):
    assignment_public_id: str
    reason: str = "admin_stop"


class ModelActivationRequest(DomainModel):
    assignment_public_id: str
    rollback_plan_public_id: str
    explicit_activation_confirmed: bool = False


class ModelRollbackRequest(DomainModel):
    assignment_public_id: str
    rollback_plan_public_id: str
    reason: str = "admin-initiated rollback"


class RollbackPlanCreate(DomainModel):
    target_type: str
    current_active_version: str | None = None
    candidate_version: str | None = None
    backup_reference: str | None = None
    rollback_steps: list[str] = []
    validation_steps: list[str] = []
    maximum_recovery_time_target_seconds: int = 900


class BackupReadinessCheckRequest(DomainModel):
    max_age_seconds: int | None = None


class RegressionRunCreate(DomainModel):
    batch_plan: list[dict[str, Any]]


class RegressionBatchRequest(DomainModel):
    batch_name: str
    test_paths: list[str]
    timeout_seconds: int = 120


class AcceptanceReviewRequest(DomainModel):
    decision: str
    reason: str
    conditions: dict[str, Any] = {}


# -- overview ----------------------------------------------------------------------------


@router.get("/overview")
async def overview(settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).overview_counts()


# -- production RAG: eligibility / promotion / candidate build --------------------------


@router.get("/rag/eligibility/{rag_sandbox_experiment_id}")
async def rag_eligibility(
    rag_sandbox_experiment_id: str,
    settings: SettingsDependency,
    commercial_use_context: str = Query(default="unknown"),
) -> dict[str, Any]:
    return ProductionRagEligibilityService(settings).check_eligibility(
        rag_sandbox_experiment_id,
        commercial_use_context=commercial_use_context,
    )


@router.post("/rag/promotion-requests")
async def create_rag_promotion_request(
    payload: RagPromotionRequestCreate, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRagPromotionService(settings).create_request(
        payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.get("/rag/promotion-requests")
async def list_rag_promotion_requests(
    settings: SettingsDependency,
    status: str | None = Query(default=None),
) -> dict[str, Any]:
    return {"items": repository(settings).list_rag_promotion_requests(status=status)}


@router.get("/rag/promotion-requests/{promotion_id}")
async def get_rag_promotion_request(
    promotion_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return repository(settings).get_rag_promotion_request(promotion_id)


@router.post("/rag/promotion-requests/{promotion_id}/submit")
async def submit_rag_promotion_request(
    promotion_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRagPromotionService(settings).submit_for_review(
        promotion_id, admin_id=admin.admin.public_id
    )


@router.post("/rag/promotion-requests/{promotion_id}/approval/request")
async def request_rag_promotion_approval(
    promotion_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRagPromotionService(settings).request_approval(
        promotion_id, admin_id=admin.admin.public_id
    )


@router.post("/rag/promotion-approvals/{approval_id}/approve")
async def approve_rag_promotion(
    approval_id: str, payload: ExpiryRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRagPromotionService(settings).approve(
        approval_id, admin_id=admin.admin.public_id, expires_at=payload.expires_at
    )


@router.post("/rag/promotion-requests/{promotion_id}/candidates")
async def build_rag_release_candidate(
    promotion_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRagCandidateService(settings).build_candidate(
        promotion_id, admin_id=admin.admin.public_id
    )


@router.get("/rag/promotion-requests/{promotion_id}/candidates")
async def list_rag_release_candidates(
    promotion_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return {"items": repository(settings).list_rag_release_candidates(promotion_id)}


@router.get("/rag/candidates/{candidate_id}")
async def get_rag_release_candidate(
    candidate_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return repository(settings).get_rag_release_candidate(candidate_id)


@router.post("/rag/candidates/{candidate_id}/validate")
async def validate_rag_release_candidate(
    candidate_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRagValidationService(settings).run_validation(
        candidate_id, admin_id=admin.admin.public_id
    )


@router.get("/rag/candidates/{candidate_id}/validation-results")
async def list_rag_validation_results(
    candidate_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return {"items": repository(settings).list_rag_validation_results(candidate_id)}


@router.post("/rag/candidates/{candidate_id}/activate")
async def activate_rag_release_candidate(
    candidate_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRagActivationService(settings).activate(
        candidate_id, admin_id=admin.admin.public_id
    )


@router.post("/rag/candidates/{candidate_id}/rollback")
async def rollback_rag_release_candidate(
    candidate_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRagActivationService(settings).rollback(
        candidate_id, admin_id=admin.admin.public_id
    )


@router.get("/rag/candidates/{candidate_id}/activation-events")
async def list_rag_activation_events(
    candidate_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return {"items": repository(settings).list_rag_activation_events(candidate_id)}


# -- model release: eligibility / request / validation / approval -----------------------


@router.get("/model/eligibility/{checkpoint_id}")
async def model_release_eligibility(
    checkpoint_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return ProductionModelReleaseEligibilityService(settings).check_eligibility(checkpoint_id)


@router.post("/model/release-requests")
async def create_model_release_request(
    payload: ModelReleaseRequestCreate, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionModelReleaseRequestService(settings).create_request(
        payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.get("/model/release-requests")
async def list_model_release_requests(
    settings: SettingsDependency,
    status: str | None = Query(default=None),
) -> dict[str, Any]:
    return {"items": repository(settings).list_model_release_requests(status=status)}


@router.get("/model/release-requests/{release_request_id}")
async def get_model_release_request(
    release_request_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return repository(settings).get_model_release_request(release_request_id)


@router.post("/model/release-requests/{release_request_id}/submit")
async def submit_model_release_request(
    release_request_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionModelReleaseRequestService(settings).submit_for_review(
        release_request_id, admin_id=admin.admin.public_id
    )


@router.post("/model/release-requests/{release_request_id}/validate")
async def validate_model_release_request(
    release_request_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionModelReleaseValidationService(settings).run_validation(
        release_request_id, admin_id=admin.admin.public_id
    )


@router.post("/model/release-requests/{release_request_id}/approval/request")
async def request_model_release_approval(
    release_request_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionModelReleaseApprovalService(settings).request_approval(
        release_request_id, admin_id=admin.admin.public_id
    )


@router.post("/model/release-approvals/{approval_id}/approve")
async def approve_model_release(
    approval_id: str, payload: ExpiryRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionModelReleaseApprovalService(settings).approve(
        approval_id, admin_id=admin.admin.public_id, expires_at=payload.expires_at
    )


@router.post("/model/release-requests/{release_request_id}/reject")
async def reject_model_release_request(
    release_request_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionModelReleaseApprovalService(settings).reject(
        release_request_id, admin_id=admin.admin.public_id
    )


# -- model release: canary / activation / rollback ---------------------------------------


@router.post("/model/release-requests/{release_request_id}/canary/start")
async def start_model_canary(
    release_request_id: str,
    payload: CanaryStartBody,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return ProductionModelCanaryService(settings).start(
        release_request_id,
        payload.assignment_public_id,
        admin_id=admin.admin.public_id,
        percentage=payload.percentage,
        max_request_count=payload.max_request_count,
    )


@router.post("/model/release-requests/{release_request_id}/canary/execute")
async def execute_model_canary(
    release_request_id: str,
    payload: CanaryExecuteBody,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return ProductionModelCanaryService(settings).execute(
        release_request_id,
        payload.assignment_public_id,
        payload.fixture_prompts,
        admin_id=admin.admin.public_id,
    )


@router.post("/model/release-requests/{release_request_id}/canary/stop")
async def stop_model_canary(
    release_request_id: str,
    payload: CanaryStopBody,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return ProductionModelCanaryService(settings).stop(
        release_request_id,
        payload.assignment_public_id,
        admin_id=admin.admin.public_id,
        reason=payload.reason,
    )


@router.post("/model/release-requests/{release_request_id}/activate")
async def activate_model_release(
    release_request_id: str,
    payload: ModelActivationRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return ProductionModelActivationService(settings).activate(
        release_request_id,
        payload.assignment_public_id,
        payload.rollback_plan_public_id,
        admin_id=admin.admin.public_id,
        explicit_activation_confirmed=payload.explicit_activation_confirmed,
    )


@router.post("/model/release-requests/{release_request_id}/rollback")
async def rollback_model_release(
    release_request_id: str,
    payload: ModelRollbackRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return ProductionModelActivationService(settings).rollback(
        release_request_id,
        payload.assignment_public_id,
        payload.rollback_plan_public_id,
        admin_id=admin.admin.public_id,
        reason=payload.reason,
    )


@router.get("/model/release-requests/{release_request_id}/activation-events")
async def list_model_activation_events(
    release_request_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return {"items": repository(settings).list_model_activation_events(release_request_id)}


@router.get("/model/release-requests/{release_request_id}/post-activation-checks")
async def list_model_post_activation_checks(
    release_request_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return {"items": repository(settings).list_model_post_activation_checks(release_request_id)}


# -- rollback plans (shared RAG/model) ----------------------------------------------------


@router.post("/rollback-plans")
async def create_rollback_plan(
    payload: RollbackPlanCreate, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRollbackPlanService(settings).create_plan(
        payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.post("/rollback-plans/{plan_id}/validate")
async def validate_rollback_plan(
    plan_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRollbackPlanService(settings).validate_plan(
        plan_id, admin_id=admin.admin.public_id
    )


@router.get("/rollback-plans/{plan_id}")
async def get_rollback_plan(plan_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return ProductionRollbackPlanService(settings).get_plan(plan_id)


@router.get("/rollback-plans")
async def list_rollback_plans(
    settings: SettingsDependency,
    target_type: str | None = Query(default=None),
) -> dict[str, Any]:
    return {"items": ProductionRollbackPlanService(settings).list_plans(target_type=target_type)}


# -- artifact security ---------------------------------------------------------------------


@router.post("/artifact-security/release-candidates/{candidate_id}/check")
async def check_release_candidate_artifacts(
    candidate_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return {
        "items": ProductionArtifactSecurityService(settings).check_release_candidate_artifacts(
            candidate_id, admin_id=admin.admin.public_id
        )
    }


@router.post("/artifact-security/backup/check")
async def check_backup_artifact_security(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionArtifactSecurityService(settings).check_backup_artifact(
        admin_id=admin.admin.public_id
    )


@router.post("/artifact-security/rag-candidates/{candidate_id}/check")
async def check_rag_candidate_artifact_security(
    candidate_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionArtifactSecurityService(settings).check_rag_release_candidate_artifact(
        candidate_id, admin_id=admin.admin.public_id
    )


@router.get("/artifact-security/checks")
async def list_artifact_security_checks(
    settings: SettingsDependency,
    artifact_type: str | None = Query(default=None),
) -> dict[str, Any]:
    return {
        "items": repository(settings).list_artifact_security_checks(artifact_type=artifact_type)
    }


# -- API-abuse readiness / secret scan ------------------------------------------------------


@router.post("/api-abuse-readiness/assess")
async def assess_api_abuse_readiness(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionApiAbuseReadinessService(settings).assess(admin_id=admin.admin.public_id)


@router.post("/secret-scan/verify-redaction")
async def verify_secret_redaction(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionSecretScanService(settings).verify_redaction_mechanism(
        admin_id=admin.admin.public_id
    )


@router.post("/secret-scan/frontend-bundle")
async def scan_frontend_bundle(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionSecretScanService(settings).scan_frontend_bundle(
        admin_id=admin.admin.public_id
    )


@router.post("/secret-scan/domain-model-fields")
async def scan_domain_model_fields(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionSecretScanService(settings).scan_domain_model_field_names(
        admin_id=admin.admin.public_id
    )


@router.post("/secret-scan/backup-sidecar-files")
async def scan_backup_sidecar_files(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionSecretScanService(settings).scan_backup_sidecar_files(
        admin_id=admin.admin.public_id
    )


# -- backup / restore / deployment readiness / system health --------------------------------


@router.post("/backup-readiness/check")
async def check_backup_readiness(
    payload: BackupReadinessCheckRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionBackupReadinessService(settings).check_backup_readiness(
        admin_id=admin.admin.public_id, max_age_seconds=payload.max_age_seconds
    )


@router.post("/restore-readiness/check")
async def check_restore_readiness(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRestoreReadinessService(settings).check_restore_readiness(
        admin_id=admin.admin.public_id
    )


@router.post("/backup-readiness/assess-encryption")
async def assess_backup_encryption(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionBackupEncryptionAssessmentService(settings).assess(
        admin_id=admin.admin.public_id
    )


@router.post("/backup-readiness/encrypt")
async def encrypt_latest_backup(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionBackupEncryptionService(settings).encrypt_latest_backup(
        admin_id=admin.admin.public_id
    )


@router.post("/backup-readiness/verify-encrypted-restore")
async def verify_encrypted_restore(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionBackupEncryptionService(settings).verify_encrypted_restore(
        admin_id=admin.admin.public_id
    )


@router.get("/backup-readiness/checks")
async def list_backup_readiness_checks(
    settings: SettingsDependency,
    check_type: str | None = Query(default=None),
) -> dict[str, Any]:
    return {"items": repository(settings).list_backup_readiness_checks(check_type=check_type)}


@router.post("/deployment-readiness/assess")
async def assess_deployment_readiness(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionDeploymentReadinessService(settings).assess(admin_id=admin.admin.public_id)


@router.get("/deployment-readiness/latest")
async def latest_deployment_readiness(settings: SettingsDependency) -> dict[str, Any] | None:
    return repository(settings).get_latest_deployment_readiness_check()


@router.get("/system-health")
async def system_health(settings: SettingsDependency, admin: AdminDependency) -> dict[str, Any]:
    return ProductionSystemHealthService(settings).snapshot(admin_id=admin.admin.public_id)


# -- regression -----------------------------------------------------------------------------


@router.post("/regression/runs")
async def create_regression_run(
    payload: RegressionRunCreate, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRegressionService(settings).create_run(
        payload.batch_plan, admin_id=admin.admin.public_id
    )


@router.post("/regression/runs/{run_id}/batches")
async def execute_regression_batch(
    run_id: str,
    payload: RegressionBatchRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return ProductionRegressionService(settings).execute_batch(
        run_id,
        payload.batch_name,
        payload.test_paths,
        admin_id=admin.admin.public_id,
        timeout_seconds=payload.timeout_seconds,
    )


@router.post("/regression/runs/{run_id}/finalize")
async def finalize_regression_run(
    run_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRegressionService(settings).finalize_run(
        run_id, admin_id=admin.admin.public_id
    )


@router.get("/regression/runs")
async def list_regression_runs(settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_regression_runs()}


@router.get("/regression/runs/{run_id}")
async def get_regression_run(run_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_regression_run(run_id)


@router.get("/regression/runs/{run_id}/results")
async def list_regression_results(run_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_regression_results(run_id)}


# -- canonical regression manifest (Phase 15A) -----------------------------------------------


@router.get("/regression-manifest")
async def get_regression_manifest(settings: SettingsDependency) -> dict[str, Any]:
    return ProductionRegressionService(settings).load_manifest()


@router.get("/regression-manifest/batches")
async def list_regression_manifest_batches(settings: SettingsDependency) -> dict[str, Any]:
    return {"items": ProductionRegressionService(settings).list_registered_batches()}


@router.post("/regression-runs")
async def create_manifest_regression_run(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRegressionService(settings).create_manifest_run(
        admin_id=admin.admin.public_id
    )


@router.post("/regression-runs/{run_id}/execute/{batch_id}")
async def execute_manifest_regression_batch(
    run_id: str, batch_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRegressionService(settings).execute_registered_batch(
        run_id, batch_id, admin_id=admin.admin.public_id
    )


@router.get("/regression-runs/{run_id}/batches")
async def list_manifest_regression_run_results(
    run_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    return {"items": repository(settings).list_regression_results(run_id)}


@router.get("/regression-runs/{run_id}/batches/{batch_id}")
async def get_manifest_regression_run_batch_result(
    run_id: str, batch_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    results = repository(settings).list_regression_results(run_id)
    for result in results:
        if result["batch_name"].endswith(f":{batch_id}"):
            return result
    raise NotFoundError(f"no result recorded yet for batch_id {batch_id!r} on this run")


@router.post("/regression-runs/{run_id}/finalize")
async def finalize_manifest_regression_run(
    run_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionRegressionService(settings).finalize_manifest_run(
        run_id, admin_id=admin.admin.public_id
    )


# -- readiness report / acceptance review ----------------------------------------------------


@router.post("/readiness-reports")
async def compile_readiness_report(
    settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return ProductionReadinessReportService(settings).compile_report(admin_id=admin.admin.public_id)


@router.get("/readiness-reports")
async def list_readiness_reports(settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_readiness_reports()}


@router.get("/readiness-reports/latest")
async def latest_readiness_report(settings: SettingsDependency) -> dict[str, Any] | None:
    return repository(settings).get_latest_readiness_report()


@router.get("/readiness-reports/{report_id}")
async def get_readiness_report(report_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_readiness_report(report_id)


@router.post("/readiness-reports/{report_id}/acceptance-review")
async def submit_acceptance_review(
    report_id: str,
    payload: AcceptanceReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return ProductionAcceptanceReviewService(settings).submit_review(
        report_id,
        payload.decision,
        payload.reason,
        admin_id=admin.admin.public_id,
        conditions=payload.conditions,
    )


@router.get("/readiness-reports/{report_id}/acceptance-reviews")
async def list_acceptance_reviews(report_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_acceptance_reviews(report_id)}
