"""Phase 14 Training Dataset Promotion, Incremental Language Training,
Checkpoint Evaluation & Admin Approval API.

Admin-only, CSRF-protected, under `/api/admin/incremental-training`.
Every mutating endpoint here is a thin wrapper around one of the Phase
14 governance services -- no raw SQL, no shortcuts around the
propose/approve/materialize/execute/evaluate/accept gates those
services enforce. There is no production-activation endpoint and no
model-release endpoint anywhere in this router: the furthest any
endpoint here can go is registering an accepted checkpoint as a
`model_candidate` (`core_model_versions.lifecycle_status='staging'`)
via the existing registry. See
docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import DomainModel
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.services.incremental_training_checkpoint_acceptance_service import (
    IncrementalTrainingCheckpointAcceptanceService,
)
from backend.services.incremental_training_checkpoint_service import (
    IncrementalTrainingCheckpointService,
)
from backend.services.incremental_training_comparison_service import (
    IncrementalTrainingComparisonService,
)
from backend.services.incremental_training_execution_service import (
    IncrementalTrainingExecutionService,
)
from backend.services.incremental_training_human_review_service import (
    IncrementalTrainingHumanReviewService,
)
from backend.services.incremental_training_report_service import IncrementalTrainingReportService
from backend.services.incremental_training_run_approval_service import (
    IncrementalTrainingRunApprovalService,
)
from backend.services.training_contamination_service import TrainingContaminationService
from backend.services.training_dataset_promotion_service import TrainingDatasetPromotionService
from backend.services.training_example_transformation_service import (
    TrainingExampleTransformationService,
)
from backend.services.training_replay_plan_service import TrainingReplayPlanService
from backend.services.training_suitability_service import TrainingSuitabilityAssessmentService

router = APIRouter(
    prefix="/admin/incremental-training",
    tags=["incremental-training"],
    dependencies=[Depends(require_admin)],
)


def repository(settings: SettingsDependency) -> TrainingIncrementalRepository:
    return TrainingIncrementalRepository(settings.resolved_database_path)


# -- request models --------------------------------------------------------------------


class AssessmentCreateRequest(DomainModel):
    rag_sandbox_experiment_public_id: str


class TransformRequest(DomainModel):
    transformation_type: str
    prompt_text: str = ""
    assistant_text: str = ""
    language: str = "unknown"
    task: str = ""
    source_checksum: str
    source_sample_record_public_id: str | None = None
    source_rag_sandbox_record_public_id: str | None = None
    transformation_version: str = "v1"


class CandidateReviewRequest(DomainModel):
    decision: str
    reason: str
    revised_prompt_text: str | None = None
    revised_assistant_text: str | None = None
    conditions: dict[str, Any] = {}


class ReplayPlanCreateRequest(DomainModel):
    new_record_count: int
    new_data_ratio: float = 0.8
    selection_seed: int = 42


class PromotionRequestCreateRequest(DomainModel):
    candidate_public_ids: list[str]
    replay_plan_public_id: str | None = None


class RunRequestCreateRequest(DomainModel):
    training_strategy: str
    base_checkpoint_public_id: str | None = None
    tokenizer_version_public_id: str | None = None
    configuration: dict[str, Any] = {}
    execution_target: str = "local_cpu"


class ExpiryRequest(DomainModel):
    expires_at: str | None = None


class CompareRequest(DomainModel):
    baseline_checkpoint_public_id: str
    comparison_type: str = "general_comparison"


class HumanReviewCreateRequest(DomainModel):
    prompt_text: str
    decision: str
    notes: str = ""
    tamil_fluency: bool | None = None
    english_fluency: bool | None = None
    tanglish_readability: bool | None = None
    instruction_following: bool | None = None
    helpfulness: bool | None = None
    correct_refusal: bool | None = None
    hallucination_risk: bool | None = None
    repetition: bool | None = None
    formatting: bool | None = None
    regression: bool | None = None


class ReportFinalizeRequest(DomainModel):
    checkpoint_public_id: str


class AcceptanceDecisionRequest(DomainModel):
    report_public_id: str
    decision: str
    reason: str
    conditions: dict[str, Any] = {}
    override_comment: str | None = None


# -- overview ----------------------------------------------------------------------------


@router.get("/overview")
async def overview(settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).overview_counts()


# -- assessments -------------------------------------------------------------------------


@router.post("/assessments")
async def create_assessment(
    payload: AssessmentCreateRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return TrainingSuitabilityAssessmentService(settings).create_assessment(
        payload.rag_sandbox_experiment_public_id, admin_id=admin.admin.public_id
    )


@router.post("/assessments/{assessment_id}/run")
async def run_assessment(
    assessment_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return TrainingSuitabilityAssessmentService(settings).run_assessment(
        assessment_id, admin_id=admin.admin.public_id
    )


@router.post("/assessments/{assessment_id}/review")
async def review_assessment(
    assessment_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return TrainingSuitabilityAssessmentService(settings).review_assessment(
        assessment_id, admin_id=admin.admin.public_id
    )


@router.get("/assessments")
async def list_assessments(
    settings: SettingsDependency,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = repository(settings).list_assessments(status=status, limit=page_size, offset=offset)
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/assessments/{assessment_id}")
async def get_assessment(assessment_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_assessment(assessment_id)


@router.get("/assessments/{assessment_id}/items")
async def list_items(
    assessment_id: str,
    settings: SettingsDependency,
    suitability_status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = repository(settings).list_items(
        assessment_public_id=assessment_id, suitability_status=suitability_status,
        limit=page_size, offset=offset,
    )
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/assessments/{assessment_id}/candidates")
async def list_candidates_for_assessment(
    assessment_id: str,
    settings: SettingsDependency,
    review_status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = repository(settings).list_candidates(
        assessment_public_id=assessment_id, review_status=review_status,
        limit=page_size, offset=offset,
    )
    return {"items": items, "page": page, "page_size": page_size}


# -- transformation & candidate review ----------------------------------------------------


@router.post("/items/{item_id}/transform")
async def transform_item(
    item_id: str, payload: TransformRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return TrainingExampleTransformationService(settings).transform(
        item_id, payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.post("/candidates/{candidate_id}/review")
async def review_candidate(
    candidate_id: str, payload: CandidateReviewRequest, settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return TrainingExampleTransformationService(settings).review_candidate(
        candidate_id, payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.get("/candidates/{candidate_id}")
async def get_candidate(candidate_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_candidate(candidate_id)


@router.get("/candidates/{candidate_id}/revisions")
async def list_revisions(candidate_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_revisions(candidate_id)}


# -- contamination recheck (read-only preview) ---------------------------------------------


@router.get("/contamination-recheck")
async def contamination_recheck(
    settings: SettingsDependency, candidate_public_ids: Annotated[list[str], Query()]
) -> dict[str, Any]:
    return TrainingContaminationService(settings).recheck_candidates(candidate_public_ids)


# -- replay plans --------------------------------------------------------------------------


@router.post("/assessments/{assessment_id}/replay-plans")
async def create_replay_plan(
    assessment_id: str, payload: ReplayPlanCreateRequest, settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return TrainingReplayPlanService(settings).create_plan(
        assessment_id, payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.get("/assessments/{assessment_id}/replay-plans")
async def list_replay_plans(assessment_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": TrainingReplayPlanService(settings).list_plans(assessment_id)}


@router.get("/replay-plans/{replay_plan_id}")
async def get_replay_plan(replay_plan_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return TrainingReplayPlanService(settings).get_plan(replay_plan_id)


# -- dataset promotion requests -------------------------------------------------------------


@router.post("/assessments/{assessment_id}/promotion-requests")
async def create_promotion_request(
    assessment_id: str, payload: PromotionRequestCreateRequest, settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return TrainingDatasetPromotionService(settings).create_request(
        assessment_id, payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.post("/promotion-requests/{promotion_id}/submit")
async def submit_promotion_request(
    promotion_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return TrainingDatasetPromotionService(settings).submit_for_approval(
        promotion_id, admin_id=admin.admin.public_id
    )


@router.post("/promotion-requests/{promotion_id}/approve")
async def approve_promotion_request(
    promotion_id: str, payload: ExpiryRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return TrainingDatasetPromotionService(settings).approve(
        promotion_id, admin_id=admin.admin.public_id, expires_at=payload.expires_at
    )


@router.post("/promotion-requests/{promotion_id}/materialize")
async def materialize_promotion_request(
    promotion_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return TrainingDatasetPromotionService(settings).materialize(
        promotion_id, admin_id=admin.admin.public_id
    )


@router.get("/promotion-requests/{promotion_id}")
async def get_promotion_request(promotion_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_promotion_request(promotion_id)


# -- training run requests & approvals -------------------------------------------------------


@router.post("/promotion-requests/{promotion_id}/run-requests")
async def create_run_request(
    promotion_id: str, payload: RunRequestCreateRequest, settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return IncrementalTrainingRunApprovalService(settings).create_run_request(
        promotion_id, payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.post("/run-requests/{run_request_id}/submit")
async def submit_run_request(
    run_request_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return IncrementalTrainingRunApprovalService(settings).submit_for_approval(
        run_request_id, admin_id=admin.admin.public_id
    )


@router.post("/run-requests/{run_request_id}/request-approval")
async def request_run_approval(
    run_request_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return IncrementalTrainingRunApprovalService(settings).request_approval(
        run_request_id, admin_id=admin.admin.public_id
    )


@router.get("/run-requests/{run_request_id}")
async def get_run_request(run_request_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_run_request(run_request_id)


@router.post("/run-approvals/{approval_id}/approve")
async def approve_run_approval(
    approval_id: str, payload: ExpiryRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return IncrementalTrainingRunApprovalService(settings).approve(
        approval_id, admin_id=admin.admin.public_id, expires_at=payload.expires_at
    )


@router.post("/run-approvals/{approval_id}/reject")
async def reject_run_approval(
    approval_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return IncrementalTrainingRunApprovalService(settings).reject(
        approval_id, admin_id=admin.admin.public_id
    )


@router.get("/run-approvals/{approval_id}")
async def get_run_approval(approval_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_run_approval(approval_id)


# -- execution -------------------------------------------------------------------------------


@router.post("/run-approvals/{approval_id}/start")
async def start_run(
    approval_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return IncrementalTrainingExecutionService(settings).start_run(
        approval_id, admin_id=admin.admin.public_id
    )


@router.post("/run-approvals/{approval_id}/acknowledge-no-execution")
async def acknowledge_no_execution(
    approval_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return IncrementalTrainingExecutionService(settings).acknowledge_no_execution_strategy(
        approval_id, admin_id=admin.admin.public_id
    )


@router.get("/runs/{run_id}")
async def get_run(run_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_run(run_id)


@router.get("/runs")
async def list_runs(
    settings: SettingsDependency,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = repository(settings).list_runs(status=status, limit=page_size, offset=offset)
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/runs/{run_id}/events")
async def list_run_events(
    run_id: str, settings: SettingsDependency,
    page: int = Query(default=1, ge=1), page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = repository(settings).list_run_events(run_id, limit=page_size, offset=offset)
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/runs/{run_id}/checkpoints")
async def list_checkpoints(run_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_checkpoints(run_id)}


# -- checkpoint verification & evaluation -----------------------------------------------------


@router.post("/checkpoints/{checkpoint_id}/verify")
async def verify_checkpoint(
    checkpoint_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return IncrementalTrainingCheckpointService(settings).verify(
        checkpoint_id, admin_id=admin.admin.public_id
    )


@router.post("/checkpoints/{checkpoint_id}/evaluate")
async def evaluate_checkpoint(
    checkpoint_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return IncrementalTrainingCheckpointService(settings).evaluate(
        checkpoint_id, admin_id=admin.admin.public_id
    )


@router.get("/checkpoints/{checkpoint_id}")
async def get_checkpoint(checkpoint_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_checkpoint(checkpoint_id)


@router.get("/checkpoints/{checkpoint_id}/evaluations")
async def list_evaluations(checkpoint_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_evaluations(checkpoint_id)}


# -- comparisons -------------------------------------------------------------------------------


@router.post("/checkpoints/{checkpoint_id}/compare")
async def compare_checkpoint(
    checkpoint_id: str, payload: CompareRequest, settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return IncrementalTrainingComparisonService(settings).compare(
        checkpoint_id, payload.baseline_checkpoint_public_id,
        comparison_type=payload.comparison_type, admin_id=admin.admin.public_id,
    )


@router.get("/checkpoints/{checkpoint_id}/comparisons")
async def list_comparisons(checkpoint_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_comparisons(checkpoint_id)}


# -- human reviews -----------------------------------------------------------------------------


@router.post("/checkpoints/{checkpoint_id}/human-reviews")
async def add_human_review(
    checkpoint_id: str, payload: HumanReviewCreateRequest, settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return IncrementalTrainingHumanReviewService(settings).add_review(
        checkpoint_id, payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.get("/checkpoints/{checkpoint_id}/human-reviews")
async def list_human_reviews(checkpoint_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": IncrementalTrainingHumanReviewService(settings).list_reviews(checkpoint_id)}


# -- reports -------------------------------------------------------------------------------------


@router.post("/runs/{run_id}/reports")
async def finalize_report(
    run_id: str, payload: ReportFinalizeRequest, settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return IncrementalTrainingReportService(settings).finalize_report(
        run_id, payload.checkpoint_public_id, admin_id=admin.admin.public_id
    )


@router.get("/runs/{run_id}/reports")
async def list_reports(run_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": IncrementalTrainingReportService(settings).list_reports(run_id)}


@router.get("/reports/{report_id}")
async def get_report(report_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_report(report_id)


# -- checkpoint acceptance & model-candidate handoff ------------------------------------------
# No endpoint in this file ever activates a production model or creates a
# release -- acceptance only ever registers a `model_candidate` (staging).


@router.post("/checkpoints/{checkpoint_id}/accept")
async def accept_checkpoint(
    checkpoint_id: str, payload: AcceptanceDecisionRequest, settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    values = payload.model_dump(exclude={"report_public_id"})
    return IncrementalTrainingCheckpointAcceptanceService(settings).accept(
        checkpoint_id, payload.report_public_id, values, admin_id=admin.admin.public_id
    )


@router.get("/checkpoints/{checkpoint_id}/acceptances")
async def list_acceptances(checkpoint_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {
        "items": IncrementalTrainingCheckpointAcceptanceService(settings).list_acceptances(
            checkpoint_id
        )
    }
