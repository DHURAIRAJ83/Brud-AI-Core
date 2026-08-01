"""Phase 13 Isolated RAG Sandbox, Retrieval Evaluation, Grounded
Answer Testing & Admin Acceptance API.

Admin-only, CSRF-protected, under `/api/admin/rag-sandbox`. No
endpoint here downloads an external dataset payload, creates a
training dataset version, modifies model weights, or activates
production RAG -- there is no such endpoint anywhere in this router.
See docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.core.validation import DomainModel
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.services.rag_sandbox_acceptance_service import RagSandboxAcceptanceService
from backend.services.rag_sandbox_answer_service import RagSandboxAnswerService
from backend.services.rag_sandbox_corpus_service import RagSandboxCorpusService
from backend.services.rag_sandbox_deletion_service import RagSandboxDeletionService
from backend.services.rag_sandbox_eligibility_service import (
    RagSandboxApprovalService,
    RagSandboxEligibilityService,
)
from backend.services.rag_sandbox_evaluation_service import RagSandboxEvaluationService
from backend.services.rag_sandbox_human_review_service import RagSandboxHumanReviewService
from backend.services.rag_sandbox_index_service import RagSandboxIndexService
from backend.services.rag_sandbox_query_set_service import RagSandboxQuerySetService
from backend.services.rag_sandbox_report_service import RagSandboxReportService
from backend.services.rag_sandbox_retrieval_service import RagSandboxRetrievalService

router = APIRouter(
    prefix="/admin/rag-sandbox",
    tags=["rag-sandbox"],
    dependencies=[Depends(require_admin)],
)


def repository(settings: SettingsDependency) -> RagSandboxRepository:
    return RagSandboxRepository(settings.resolved_database_path)


# -- request models -------------------------------------------------------------------


class ExperimentCreateRequest(DomainModel):
    sample_import_public_id: str
    experiment_code: str | None = None
    purpose: str
    maximum_records: int = 500
    maximum_total_characters: int = 2_000_000
    maximum_total_tokens: int = 500_000
    expires_at: str | None = None


class ApprovalRequestRequest(DomainModel):
    purpose: str | None = None
    expires_at: str | None = None
    maximum_records: int | None = None
    maximum_total_characters: int | None = None
    maximum_total_tokens: int | None = None
    chunking_configuration: dict[str, Any] = {}
    retrieval_configuration: dict[str, Any] = {}
    embedding_assignment_key: str | None = None
    generation_assignment_key: str | None = None
    query_set_public_id: str | None = None
    conditions: dict[str, Any] = {}


class ApprovalDecisionRequest(DomainModel):
    expires_at: str | None = None


class ApprovalRejectRequest(DomainModel):
    reason: str


class BuildIndexRequest(DomainModel):
    index_kind: str
    chunking_config: dict[str, Any] = {}
    embedding_model_public_id: str | None = None
    top_k: int = 5
    minimum_score: float = 0.15


class QuerySetCreateRequest(DomainModel):
    name: str


class QueryCreateRequest(DomainModel):
    query_text: str
    language: str = "unknown"
    query_type: str
    expected_source_ids: list[str] = []
    expected_answer_notes: str = ""
    must_refuse_if_insufficient: bool = False
    conflict_expected: bool = False
    injection_test: bool = False
    human_authored: bool = True


class RunRetrievalRequest(DomainModel):
    index_public_id: str
    query_set_public_id: str


class RunGenerationRequest(DomainModel):
    retrieval_run_public_id: str
    generation_assignment_public_id: str


class RunEvaluationRequest(DomainModel):
    answer_run_public_id: str


class QueryReviewRequest(DomainModel):
    answer_run_public_id: str | None = None
    retrieval_relevant: bool | None = None
    answer_grounded: bool | None = None
    citations_correct: bool | None = None
    language_appropriate: bool | None = None
    refusal_correct: bool | None = None
    conflict_handled: bool | None = None
    injection_resisted: bool | None = None
    decision: str
    notes: str = ""


class AcceptanceDecisionRequest(DomainModel):
    decision: str
    reason: str
    report_public_id: str
    conditions: dict[str, Any] = {}


class DeletionRequestRequest(DomainModel):
    reason: str


# -- experiments -----------------------------------------------------------------------


@router.post("/experiments")
async def create_experiment(
    payload: ExperimentCreateRequest, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    values = payload.model_dump(exclude={"sample_import_public_id"})
    values["created_by_admin_public_id"] = admin.admin.public_id
    return RagSandboxEligibilityService(settings).create_experiment(
        payload.sample_import_public_id, values
    )


@router.get("/experiments")
async def list_experiments(
    settings: SettingsDependency,
    status: str | None = None,
    sample_import_public_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = repository(settings).list_experiments(
        status=status,
        sample_import_public_id=sample_import_public_id,
        limit=page_size,
        offset=offset,
    )
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/experiments/{experiment_id}")
async def get_experiment(experiment_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).get_experiment(experiment_id)


@router.get("/experiments/{experiment_id}/eligibility")
async def get_eligibility(experiment_id: str, settings: SettingsDependency) -> dict[str, Any]:
    experiment = repository(settings).get_experiment(experiment_id)
    result = RagSandboxEligibilityService(settings).check_eligibility(
        experiment["sample_import_public_id"]
    )
    return {
        "eligible": result["eligible"],
        "checks": result["checks"],
        "blocking_reasons": result["blocking_reasons"],
        "warnings": result["warnings"],
    }


# -- approval ---------------------------------------------------------------------------


@router.post("/experiments/{experiment_id}/request-approval")
async def request_approval(
    experiment_id: str,
    payload: ApprovalRequestRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    values = {key: value for key, value in payload.model_dump().items() if value is not None}
    return RagSandboxApprovalService(settings).request_approval(
        experiment_id, values, admin_id=admin.admin.public_id
    )


@router.post("/experiments/{experiment_id}/approve")
async def approve_experiment(
    experiment_id: str,
    payload: ApprovalDecisionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    approval = repository(settings).get_latest_approval(experiment_id)
    return RagSandboxApprovalService(settings).approve(
        approval["public_id"], admin_id=admin.admin.public_id, expires_at=payload.expires_at
    )


@router.post("/experiments/{experiment_id}/reject-approval")
async def reject_approval(
    experiment_id: str,
    payload: ApprovalRejectRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    approval = repository(settings).get_latest_approval(experiment_id)
    return RagSandboxApprovalService(settings).reject(
        approval["public_id"], admin_id=admin.admin.public_id, reason=payload.reason
    )


@router.post("/experiments/{experiment_id}/cancel")
async def cancel_experiment(
    experiment_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    del admin
    return repository(settings).update_experiment(experiment_id, {"status": "cancelled"})


# -- corpus / records -------------------------------------------------------------------


@router.post("/experiments/{experiment_id}/prepare-corpus")
async def prepare_corpus(
    experiment_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return RagSandboxCorpusService(settings).prepare_corpus(
        experiment_id, admin_id=admin.admin.public_id
    )


@router.get("/experiments/{experiment_id}/records")
async def list_records(
    experiment_id: str,
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = repository(settings).list_records(experiment_id, limit=page_size, offset=offset)
    return {"items": items, "page": page, "page_size": page_size}


# -- indexes ------------------------------------------------------------------------------


@router.post("/experiments/{experiment_id}/build-index")
async def build_index(
    experiment_id: str,
    payload: BuildIndexRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return RagSandboxIndexService(settings).build_index(
        experiment_id, admin_id=admin.admin.public_id, **payload.model_dump()
    )


@router.get("/experiments/{experiment_id}/indexes")
async def list_indexes(experiment_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_indexes(experiment_id)}


@router.post("/experiments/{experiment_id}/indexes/{index_id}/delete")
async def delete_index(
    experiment_id: str, index_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    del experiment_id
    return RagSandboxIndexService(settings).delete_index(index_id, admin_id=admin.admin.public_id)


# -- query sets ---------------------------------------------------------------------------


@router.post("/experiments/{experiment_id}/query-sets")
async def create_query_set(
    experiment_id: str,
    payload: QuerySetCreateRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return RagSandboxQuerySetService(settings).create_query_set(
        experiment_id, name=payload.name, admin_id=admin.admin.public_id
    )


@router.get("/experiments/{experiment_id}/query-sets")
async def list_query_sets(experiment_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_query_sets(experiment_id)}


@router.post("/experiments/{experiment_id}/query-sets/{query_set_id}/queries")
async def add_query(
    experiment_id: str,
    query_set_id: str,
    payload: QueryCreateRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    del experiment_id
    return RagSandboxQuerySetService(settings).add_query(
        query_set_id, payload.model_dump(), created_by=admin.admin.public_id
    )


@router.get("/experiments/{experiment_id}/query-sets/{query_set_id}/queries")
async def list_queries(
    experiment_id: str, query_set_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    del experiment_id
    return {"items": repository(settings).list_queries(query_set_id)}


@router.post("/experiments/{experiment_id}/query-sets/{query_set_id}/finalize")
async def finalize_query_set(
    experiment_id: str, query_set_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    del experiment_id
    return RagSandboxQuerySetService(settings).finalize_query_set(
        query_set_id, admin_id=admin.admin.public_id
    )


@router.post("/experiments/{experiment_id}/queries/{query_id}/review-suggestion")
async def review_suggested_query(
    experiment_id: str, query_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    del experiment_id
    return RagSandboxQuerySetService(settings).review_query(
        query_id, admin_id=admin.admin.public_id
    )


# -- retrieval ------------------------------------------------------------------------------


@router.post("/experiments/{experiment_id}/run-retrieval")
async def run_retrieval(
    experiment_id: str,
    payload: RunRetrievalRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return RagSandboxRetrievalService(settings).run_retrieval(
        experiment_id,
        index_public_id=payload.index_public_id,
        query_set_public_id=payload.query_set_public_id,
        admin_id=admin.admin.public_id,
    )


@router.get("/experiments/{experiment_id}/retrieval-runs")
async def list_retrieval_runs(experiment_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_retrieval_runs(experiment_id)}


@router.get("/experiments/{experiment_id}/retrieval-runs/{run_id}")
async def get_retrieval_run(
    experiment_id: str, run_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    del experiment_id
    repo = repository(settings)
    run = repo.get_retrieval_run(run_id)
    return {"run": run, "results": repo.list_retrieval_results(run_id)}


# -- answers ---------------------------------------------------------------------------------


@router.post("/experiments/{experiment_id}/run-generation")
async def run_generation(
    experiment_id: str,
    payload: RunGenerationRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return RagSandboxAnswerService(settings).run_generation(
        experiment_id,
        retrieval_run_public_id=payload.retrieval_run_public_id,
        generation_assignment_public_id=payload.generation_assignment_public_id,
        admin_id=admin.admin.public_id,
    )


@router.get("/experiments/{experiment_id}/answer-runs")
async def list_answer_runs(experiment_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_answer_runs(experiment_id)}


@router.get("/experiments/{experiment_id}/answer-runs/{run_id}")
async def get_answer_run(
    experiment_id: str, run_id: str, settings: SettingsDependency
) -> dict[str, Any]:
    del experiment_id
    repo = repository(settings)
    return {"answer_run": repo.get_answer_run(run_id), "citations": repo.list_citations(run_id)}


# -- citations / evaluations --------------------------------------------------------------


@router.get("/experiments/{experiment_id}/citations")
async def list_citations(experiment_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_citations_for_experiment(experiment_id)}


@router.get("/experiments/{experiment_id}/evaluations")
async def list_evaluations(
    experiment_id: str, settings: SettingsDependency, evaluation_type: str | None = None
) -> dict[str, Any]:
    return {
        "items": repository(settings).list_evaluations(
            experiment_id, evaluation_type=evaluation_type
        )
    }


@router.post("/experiments/{experiment_id}/evaluations/run")
async def run_evaluation(
    experiment_id: str,
    payload: RunEvaluationRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    evaluations = RagSandboxEvaluationService(settings).run_evaluation(
        experiment_id, payload.answer_run_public_id, admin_id=admin.admin.public_id
    )
    return {"items": evaluations}


# -- human review / report / acceptance ----------------------------------------------------


@router.post("/experiments/{experiment_id}/queries/{query_id}/review")
async def review_query(
    experiment_id: str,
    query_id: str,
    payload: QueryReviewRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return RagSandboxHumanReviewService(settings).review_query(
        experiment_id, query_id, payload.model_dump(), admin_id=admin.admin.public_id
    )


@router.post("/experiments/{experiment_id}/finalize-report")
async def finalize_report(
    experiment_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    return RagSandboxReportService(settings).finalize(experiment_id, admin_id=admin.admin.public_id)


@router.get("/experiments/{experiment_id}/report")
async def get_report(experiment_id: str, settings: SettingsDependency) -> dict[str, Any]:
    return {"items": repository(settings).list_reports(experiment_id)}


@router.post("/experiments/{experiment_id}/accept")
async def accept_experiment(
    experiment_id: str,
    payload: AcceptanceDecisionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return RagSandboxAcceptanceService(settings).decide(
        experiment_id,
        decision=payload.decision,
        reason=payload.reason,
        report_public_id=payload.report_public_id,
        conditions=payload.conditions,
        admin_id=admin.admin.public_id,
    )


@router.post("/experiments/{experiment_id}/reject")
async def reject_experiment(
    experiment_id: str,
    payload: AcceptanceDecisionRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    values = payload.model_dump()
    values["decision"] = "rejected"
    return RagSandboxAcceptanceService(settings).decide(
        experiment_id,
        decision="rejected",
        reason=values["reason"],
        report_public_id=values["report_public_id"],
        conditions=values["conditions"],
        admin_id=admin.admin.public_id,
    )


# -- deletion ---------------------------------------------------------------------------------


@router.post("/experiments/{experiment_id}/request-deletion")
async def request_deletion(
    experiment_id: str,
    payload: DeletionRequestRequest,
    settings: SettingsDependency,
    admin: CsrfDependency,
) -> dict[str, Any]:
    return RagSandboxDeletionService(settings).request_deletion(
        experiment_id, reason=payload.reason, admin_id=admin.admin.public_id
    )


@router.post("/experiments/{experiment_id}/confirm-deletion")
async def confirm_deletion(
    experiment_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    latest = repository(settings).get_latest_deletion_request(experiment_id)
    return RagSandboxDeletionService(settings).confirm_deletion(
        latest["deletion_request_code"], admin_id=admin.admin.public_id
    )


@router.post("/experiments/{experiment_id}/execute-deletion")
async def execute_deletion(
    experiment_id: str, settings: SettingsDependency, admin: CsrfDependency
) -> dict[str, Any]:
    latest = repository(settings).get_latest_deletion_request(experiment_id)
    return RagSandboxDeletionService(settings).execute_deletion(
        latest["deletion_request_code"], admin_id=admin.admin.public_id
    )


# -- events / overview -----------------------------------------------------------------------


@router.get("/experiments/{experiment_id}/events")
async def list_events(
    experiment_id: str,
    settings: SettingsDependency,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
) -> dict[str, Any]:
    offset = (page - 1) * page_size
    items = repository(settings).list_events(experiment_id, limit=page_size, offset=offset)
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/overview")
async def get_overview(settings: SettingsDependency) -> dict[str, Any]:
    return repository(settings).overview_counts()
