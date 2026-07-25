"""Phase 18 feedback, human review, dataset-candidate, regression, and
improvement-report APIs.

Every mutation requires admin authentication and CSRF. There is no
public-facing route here -- the public chatbot route is untouched, and
no candidate is ever exported into a finalized dataset version by this
router (export hands off to the existing Phase 3 dataset pipeline).
"""

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.feedback import FeedbackRepository
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.models.feedback import (
    CandidateApprovalCreate,
    CorrectedResponseCreate,
    DatasetCandidateCreate,
    FeedbackClassificationCreate,
    FeedbackEventCreate,
    FeedbackPolicyCreate,
    FeedbackPolicyPatch,
    HumanReviewCreate,
    ImprovementReportCreate,
    RegressionFixtureCreate,
    RegressionRunCompareRequest,
    RegressionRunCreate,
    RegressionSuiteCreate,
    ReviewAssignmentCreate,
    ReviewQueueCreate,
)
from backend.services.feedback_dataset_service import FeedbackDatasetService
from backend.services.feedback_review_service import FeedbackReviewService
from backend.services.feedback_service import FeedbackService
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService
from backend.services.regression_evaluation_service import RegressionEvaluationService

router = APIRouter(
    prefix="/admin/feedback", tags=["admin-feedback"], dependencies=[Depends(require_admin)]
)


def _repository(settings) -> FeedbackRepository:
    return FeedbackRepository(settings.resolved_database_path)


def feedback_service(settings) -> FeedbackService:
    return FeedbackService(_repository(settings), settings)


def review_service(settings) -> FeedbackReviewService:
    return FeedbackReviewService(_repository(settings), settings)


def dataset_service(settings) -> FeedbackDatasetService:
    dataset_repository = DatasetAdminRepository(settings.resolved_database_path)
    return FeedbackDatasetService(_repository(settings), dataset_repository, settings)


def regression_service(settings) -> RegressionEvaluationService:
    inference_repository = InferenceRuntimeRepository(settings.resolved_database_path)
    release_repository = ModelReleaseRepository(settings.resolved_database_path)
    runtime_service = InferenceRuntimeService(inference_repository, release_repository, settings)
    assignment_service = ModelAssignmentService(
        inference_repository, release_repository, runtime_service, settings
    )
    return RegressionEvaluationService(
        _repository(settings), inference_repository, assignment_service, settings
    )


# --- policies -----------------------------------------------------


@router.get("/policies")
async def list_policies(settings: SettingsDependency):
    return feedback_service(settings).list_policies()


@router.post("/policies")
async def create_policy(
    payload: FeedbackPolicyCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return feedback_service(settings).create_policy(payload, admin.admin.public_id)


@router.get("/policies/{public_id}")
async def get_policy(public_id: str, settings: SettingsDependency):
    return feedback_service(settings).get_policy(public_id)


@router.patch("/policies/{public_id}")
async def patch_policy(
    public_id: str, payload: FeedbackPolicyPatch, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return feedback_service(settings).patch_policy(public_id, payload, admin.admin.public_id)


@router.post("/policies/{public_id}/validate")
async def validate_policy(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return feedback_service(settings).validate_policy(public_id, admin.admin.public_id)


@router.post("/policies/{public_id}/activate")
async def activate_policy(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return feedback_service(settings).activate_policy(public_id, admin.admin.public_id)


# --- feedback events -----------------------------------------------------


@router.get("/events")
async def list_events(settings: SettingsDependency, participant_scope_key: str | None = None):
    return feedback_service(settings).list_events(participant_scope_key=participant_scope_key)


@router.post("/events")
async def submit_event(
    payload: FeedbackEventCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return feedback_service(settings).submit_feedback(payload, admin.admin.public_id)


@router.get("/events/{public_id}")
async def get_event(public_id: str, settings: SettingsDependency):
    return feedback_service(settings).get_event(public_id)


@router.post("/events/{public_id}/triage")
async def triage_event(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return feedback_service(settings).triage(public_id, admin.admin.public_id)


@router.post("/events/{public_id}/delete")
async def delete_event(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return feedback_service(settings).delete_event(public_id, admin.admin.public_id)


@router.get("/events/{public_id}/classifications")
async def get_classifications(public_id: str, settings: SettingsDependency):
    return feedback_service(settings).get_classifications(public_id)


@router.post("/events/{public_id}/classifications")
async def add_classification(
    public_id: str, payload: FeedbackClassificationCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return feedback_service(settings).add_classification(
        public_id, payload.category, payload.severity, admin.admin.public_id
    )


@router.get("/events/{public_id}/findings")
async def get_findings(public_id: str, settings: SettingsDependency):
    return feedback_service(settings).get_findings(public_id)


# --- review queues -----------------------------------------------------


@router.get("/review-queues")
async def list_queues(settings: SettingsDependency):
    return review_service(settings).list_queues()


@router.post("/review-queues")
async def create_queue(
    payload: ReviewQueueCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return review_service(settings).create_queue(payload, admin.admin.public_id)


@router.get("/review-queues/{public_id}")
async def get_queue(public_id: str, settings: SettingsDependency):
    return review_service(settings).get_queue(public_id)


@router.post("/review-queues/{public_id}/assign")
async def assign_review(
    public_id: str, payload: ReviewAssignmentCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return review_service(settings).assign_review(public_id, payload, admin.admin.public_id)


@router.get("/review-queues/{public_id}/items")
async def get_queue_items(public_id: str, settings: SettingsDependency):
    return review_service(settings).get_queue_items(public_id)


# --- human reviews -----------------------------------------------------


@router.post("/events/{public_id}/reviews")
async def create_review(
    public_id: str, payload: HumanReviewCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return review_service(settings).create_review(public_id, payload, admin.admin.public_id)


@router.get("/events/{public_id}/reviews")
async def get_reviews(public_id: str, settings: SettingsDependency):
    return review_service(settings).get_reviews(public_id)


@router.get("/events/{public_id}/review-summary")
async def get_review_summary(public_id: str, settings: SettingsDependency):
    return review_service(settings).get_review_summary(public_id)


# --- corrected responses -----------------------------------------------------


@router.post("/events/{public_id}/corrected-responses")
async def create_corrected_response(
    public_id: str, payload: CorrectedResponseCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return review_service(settings).create_corrected_response(
        public_id, payload, admin.admin.public_id
    )


@router.get("/events/{public_id}/corrected-responses")
async def list_corrected_responses(public_id: str, settings: SettingsDependency):
    return review_service(settings).list_corrected_responses(public_id)


@router.get("/corrected-responses/{public_id}")
async def get_corrected_response(public_id: str, settings: SettingsDependency):
    return review_service(settings).get_corrected_response(public_id)


@router.post("/corrected-responses/{public_id}/validate")
async def validate_corrected_response(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return review_service(settings).validate_corrected_response(public_id, admin.admin.public_id)


@router.post("/corrected-responses/{public_id}/reject")
async def reject_corrected_response(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return review_service(settings).reject_corrected_response(public_id, admin.admin.public_id)


# --- dataset candidates -----------------------------------------------------


@router.get("/dataset-candidates")
async def list_candidates(settings: SettingsDependency):
    return dataset_service(settings).list_candidates()


@router.post("/events/{public_id}/dataset-candidates")
async def create_candidate(
    public_id: str, payload: DatasetCandidateCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return dataset_service(settings).create_candidate(public_id, payload, admin.admin.public_id)


@router.get("/dataset-candidates/{public_id}")
async def get_candidate(public_id: str, settings: SettingsDependency):
    return dataset_service(settings).get_candidate(public_id)


@router.post("/dataset-candidates/{public_id}/validate")
async def validate_candidate(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return dataset_service(settings).validate_candidate(public_id, admin.admin.public_id)


@router.post("/dataset-candidates/{public_id}/approve")
async def approve_candidate(
    public_id: str, payload: CandidateApprovalCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return dataset_service(settings).approve_candidate(
        public_id, "approve", payload, admin.admin.public_id
    )


@router.post("/dataset-candidates/{public_id}/reject")
async def reject_candidate(
    public_id: str, payload: CandidateApprovalCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return dataset_service(settings).approve_candidate(
        public_id, "reject", payload, admin.admin.public_id
    )


@router.post("/dataset-candidates/{public_id}/quarantine")
async def quarantine_candidate(
    public_id: str, payload: CandidateApprovalCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return dataset_service(settings).approve_candidate(
        public_id, "quarantine", payload, admin.admin.public_id
    )


@router.get("/dataset-candidates/{public_id}/versions")
async def get_candidate_versions(public_id: str, settings: SettingsDependency):
    return dataset_service(settings).get_versions(public_id)


@router.get("/dataset-candidates/{public_id}/issues")
async def get_candidate_issues(public_id: str, settings: SettingsDependency):
    return dataset_service(settings).get_issues(public_id)


@router.post("/dataset-candidates/{public_id}/export")
async def export_candidate(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return dataset_service(settings).export_candidate(public_id, admin.admin.public_id)


# --- regression suites -----------------------------------------------------


@router.get("/regression-suites")
async def list_regression_suites(settings: SettingsDependency):
    return regression_service(settings).list_suites()


@router.post("/regression-suites")
async def create_regression_suite(
    payload: RegressionSuiteCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return regression_service(settings).create_suite(payload, admin.admin.public_id)


@router.get("/regression-suites/{public_id}")
async def get_regression_suite(public_id: str, settings: SettingsDependency):
    return regression_service(settings).get_suite(public_id)


@router.post("/regression-suites/{public_id}/fixtures")
async def add_regression_fixture(
    public_id: str, payload: RegressionFixtureCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return regression_service(settings).add_fixture(public_id, payload, admin.admin.public_id)


@router.post("/regression-suites/{public_id}/validate")
async def validate_regression_suite(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return regression_service(settings).validate_suite(public_id, admin.admin.public_id)


@router.post("/regression-suites/{public_id}/activate")
async def activate_regression_suite(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return regression_service(settings).activate_suite(public_id, admin.admin.public_id)


# --- regression runs -----------------------------------------------------


@router.post("/regression-suites/{public_id}/runs")
async def create_regression_run(
    public_id: str, payload: RegressionRunCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return regression_service(settings).create_run(public_id, payload, admin.admin.public_id)


@router.post("/regression-runs/{public_id}/execute")
async def execute_regression_run(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return regression_service(settings).execute_run(public_id, admin.admin.public_id)


@router.get("/regression-runs/{public_id}")
async def get_regression_run(public_id: str, settings: SettingsDependency):
    return regression_service(settings).get_run(public_id)


@router.get("/regression-runs/{public_id}/results")
async def get_regression_results(public_id: str, settings: SettingsDependency):
    return regression_service(settings).get_results(public_id)


@router.get("/regression-runs/{public_id}/metrics")
async def get_regression_metrics(public_id: str, settings: SettingsDependency):
    return regression_service(settings).get_metrics(public_id)


# --- comparisons and reports -----------------------------------------------------


@router.post("/regression-runs/compare")
async def compare_regression_runs(
    payload: RegressionRunCompareRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return regression_service(settings).compare_runs(payload, admin.admin.public_id)


@router.get("/comparisons/{public_id}")
async def get_comparison(public_id: str, settings: SettingsDependency):
    return regression_service(settings).get_comparison(public_id)


@router.post("/improvement-reports")
async def create_improvement_report(
    payload: ImprovementReportCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return regression_service(settings).create_improvement_report(payload, admin.admin.public_id)


@router.get("/improvement-reports/{public_id}")
async def get_improvement_report(public_id: str, settings: SettingsDependency):
    return regression_service(settings).get_improvement_report(public_id)


# --- manifest -----------------------------------------------------


@router.get("/policies/{public_id}/manifest")
async def get_manifest(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return regression_service(settings).generate_manifest(public_id, admin.admin.public_id)


@router.post("/policies/{public_id}/manifest/verify")
async def verify_manifest(public_id: str, settings: SettingsDependency):
    return regression_service(settings).verify_manifest(public_id)
