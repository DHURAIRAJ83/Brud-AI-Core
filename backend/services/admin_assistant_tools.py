"""Read-only tool registry for the floating Admin Assistant.

Every tool here is a thin, uniform wrapper around one method of an
existing, already-secured Phase 2-7 service or repository -- never a
new data-access layer, never raw SQL, and never a mutation. A tool
either returns real data or a structured `{"available": False, ...}`
result when the target does not exist or is not reachable; it never
fabricates a status, a count, or a success it did not observe.

`ReadOnlyToolError` is the one exception type every tool call may
raise; the caller (chat orchestration, Step 93's companion task)
converts it into a bounded, redacted, non-stack-trace message and logs
the attempt as an `admin_assistant_tool_invocations` row.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from backend.core.config import Settings
from backend.core.exceptions import BrudError
from backend.core.json_utils import redact_secrets
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.corpus import CorpusRepository
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.documents import DocumentRepository
from backend.database.repositories.model_evaluation import ModelEvaluationRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.phase2 import AuditLogRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.pretraining_readiness import (
    PretrainingReadinessRepository,
)
from backend.database.repositories.rag import RagRepository
from core_model.admin_assistant.dashboard_registry import (
    get_page_by_id,
    get_page_by_nav_key,
)

logger = logging.getLogger(__name__)


class ReadOnlyToolError(BrudError):
    """Raised when a read-only tool cannot answer (bad params, unknown
    target) -- never for the mutation-adjacent cases, since no tool
    here mutates anything."""

    status_code = 422
    code = "admin_assistant_tool_rejected"


ToolFunction = Callable[[Settings, dict[str, Any]], dict[str, Any]]


def _require(params: dict[str, Any], *names: str) -> None:
    missing = [name for name in names if not params.get(name)]
    if missing:
        raise ReadOnlyToolError(f"missing required parameter(s): {', '.join(missing)}")


def _tool_dashboard_overview(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.admin_assistant_service import AdminAssistantService

    return AdminAssistantService(settings).dashboard_overview()


def _tool_page_help(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    del settings
    page = None
    if params.get("page_id"):
        page = get_page_by_id(params["page_id"])
    elif params.get("nav_key"):
        page = get_page_by_nav_key(params["nav_key"])
    else:
        raise ReadOnlyToolError("missing required parameter(s): page_id or nav_key")
    if page is None:
        return {"available": False, "reason": "unknown page"}
    return {
        "available": True,
        "page_id": page.page_id,
        "nav_key": page.nav_key,
        "implemented": page.implemented,
        "mode": page.mode,
        "title": page.title,
        "purpose": page.purpose,
        "tabs": list(page.tabs),
        "related_page_ids": list(page.related_page_ids),
        "safety_note": page.safety_note,
    }


def _tool_pending_admin_proposals(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.admin_assistant_service import AdminAssistantService

    limit = int(params.get("limit", 20))
    proposals = AdminAssistantService(settings).list_proposals(status="pending", limit=limit)
    return {"available": True, "items": [proposal.model_dump() for proposal in proposals]}


def _tool_governance_review_queue(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.governance_service import GovernanceReviewService

    service = GovernanceReviewService(settings)
    return service.queue(
        status=params.get("status"),
        priority=params.get("priority"),
        entity_type=params.get("entity_type"),
        page=int(params.get("page", 1)),
        page_size=int(params.get("page_size", 20)),
    )


def _tool_governance_entity_status(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.governance_service import GovernanceApprovalService

    _require(params, "entity_type", "entity_public_id")
    service = GovernanceApprovalService(settings)
    # status() is a total, read-only function over any (entity_type,
    # entity_public_id) pair -- an entity with no governance activity at
    # all simply comes back with every target_use as "not_requested",
    # never a NotFoundError, matching the same real behavior the Quality
    # & Approval page's Approvals tab relies on.
    status = service.status(params["entity_type"], params["entity_public_id"])
    return {"available": True, **status}


def _tool_governed_build_status(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.governed_build_service import GovernedBuildService

    _require(params, "public_id")
    service = GovernedBuildService(settings)
    try:
        return {"available": True, **service.get(params["public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "build request not found"}


def _tool_list_governed_builds(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.governed_build_service import GovernedBuildService

    service = GovernedBuildService(settings)
    return service.list(
        status=params.get("status"),
        target_pipeline=params.get("target_pipeline"),
        page=int(params.get("page", 1)),
        page_size=int(params.get("page_size", 20)),
    )


def _tool_lineage_trace(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.lineage_graph_service import LineageGraphService

    _require(params, "entity_type", "entity_id")
    service = LineageGraphService(settings)
    return {
        "available": True,
        **service.trace(
            params["entity_type"], params["entity_id"], max_depth=int(params.get("max_depth", 10))
        ),
    }


def _tool_source_status(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.data_source_service import SourceRegistryService

    _require(params, "public_id")
    repository = DataSourceRepository(settings.resolved_database_path)
    service = SourceRegistryService(repository, settings)
    try:
        return {"available": True, **service.get(params["public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "source not found"}


def _tool_list_rag_knowledge_spaces(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    del params
    from backend.services.rag_ingestion_service import RagIngestionService

    repository = RagRepository(settings.resolved_database_path)
    return RagIngestionService(repository, settings).list_spaces()


def _tool_model_evaluation_run(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.model_evaluation_service import ModelEvaluationService

    _require(params, "public_id")
    repository = ModelEvaluationRepository(settings.resolved_database_path)
    service = ModelEvaluationService(repository, settings)
    try:
        return {"available": True, **service.get_run(params["public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "evaluation run not found"}


def _tool_model_release_candidate(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.model_release_service import ModelReleaseService

    _require(params, "public_id")
    repository = ModelReleaseRepository(settings.resolved_database_path)
    service = ModelReleaseService(repository, settings)
    try:
        return {"available": True, **service.get_candidate(params["public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "release candidate not found"}


def _tool_pretraining_readiness_evaluations(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    del params
    from backend.services.base_model_readiness_service import BaseModelReadinessService

    database_path = settings.resolved_database_path
    service = BaseModelReadinessService(
        PretrainingReadinessRepository(database_path),
        CorpusRepository(database_path),
        PretrainingRepository(database_path),
        settings,
    )
    return service.list_evaluations()


def _tool_recent_audit_events(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    limit = int(params.get("limit", 20))
    offset = int(params.get("offset", 0))
    events = AuditLogRepository(settings.resolved_database_path).recent(limit=limit, offset=offset)
    return {"available": True, "items": [event.model_dump() for event in events]}


def _tool_list_external_data_providers(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.external_data_provider_service import ExternalDataProviderService

    service = ExternalDataProviderService(settings)
    items = service.list_providers(
        provider_type=params.get("provider_type"),
        lifecycle_status=params.get("lifecycle_status"),
        enabled=params.get("enabled"),
        limit=int(params.get("limit", 50)),
    )
    return {"available": True, "items": items}


def _tool_get_external_data_provider(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.external_data_provider_service import ExternalDataProviderService

    _require(params, "public_id")
    service = ExternalDataProviderService(settings)
    try:
        return {"available": True, **service.get_provider(params["public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "external data provider not found"}


def _tool_get_provider_capabilities(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.external_data_provider_service import (
        ExternalDataProviderCapabilityService,
    )

    _require(params, "public_id")
    service = ExternalDataProviderCapabilityService(settings)
    try:
        return {"available": True, "items": service.list_capabilities(params["public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "external data provider not found"}


def _tool_get_provider_connection_status(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.external_data_provider_service import (
        ExternalDataProviderConnectionService,
    )

    _require(params, "public_id")
    service = ExternalDataProviderConnectionService(settings)
    try:
        tests = service.list_connection_tests(params["public_id"], limit=5)
    except NotFoundError:
        return {"available": False, "reason": "external data provider not found"}
    return {
        "available": True,
        "most_recent": tests[0] if tests else None,
        "recent_tests": tests,
    }


def _tool_list_dataset_search_sessions(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.external_dataset_search_service import (
        ExternalDatasetSearchSessionService,
    )

    service = ExternalDatasetSearchSessionService(settings)
    items = service.list_sessions(
        status=params.get("status"), limit=int(params.get("limit", 20))
    )
    return {"available": True, "items": items}


def _tool_get_dataset_search_session(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.external_dataset_search_service import (
        ExternalDatasetSearchSessionService,
    )

    _require(params, "public_id")
    service = ExternalDatasetSearchSessionService(settings)
    try:
        session = service.get_session(params["public_id"])
    except NotFoundError:
        return {"available": False, "reason": "search session not found"}
    return {
        "available": True,
        "session": session,
        "requirement": service.get_requirements(params["public_id"]),
    }


def _tool_list_dataset_candidates(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.external_dataset_search_service import ExternalDatasetCandidateService

    _require(params, "session_public_id")
    service = ExternalDatasetCandidateService(settings)
    try:
        items = service.list_candidates(
            params["session_public_id"],
            include_excluded=bool(params.get("include_excluded", True)),
        )
    except NotFoundError:
        return {"available": False, "reason": "search session not found"}
    return {"available": True, "items": items}


def _tool_get_dataset_candidate(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.external_dataset_search_service import ExternalDatasetCandidateService

    _require(params, "public_id")
    service = ExternalDatasetCandidateService(settings)
    try:
        return {"available": True, **service.get_candidate_detail(params["public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "candidate not found"}


def _tool_get_dataset_verification_case(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.dataset_verification_case_service import (
        ExternalDatasetVerificationService,
    )

    _require(params, "public_id")
    service = ExternalDatasetVerificationService(settings)
    try:
        return {"available": True, "case": service.get_case(params["public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "verification case not found"}


def _tool_list_dataset_evidence(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.database.repositories.dataset_verification import (
        DatasetVerificationRepository,
    )

    _require(params, "case_public_id")
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    try:
        items = repository.list_evidence_snapshots(
            params["case_public_id"], current_only=bool(params.get("current_only", True))
        )
    except NotFoundError:
        return {"available": False, "reason": "verification case not found"}
    return {"available": True, "items": items}


def _tool_get_dataset_permission_assessments(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.dataset_verification import (
        DatasetVerificationRepository,
    )

    _require(params, "case_public_id")
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    try:
        items = repository.list_permission_assessments(params["case_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "verification case not found"}
    return {"available": True, "items": items}


def _tool_get_dataset_verification_conflicts(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.dataset_verification import (
        DatasetVerificationRepository,
    )

    _require(params, "case_public_id")
    repository = DatasetVerificationRepository(settings.resolved_database_path)
    try:
        items = repository.list_conflict_events(params["case_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "verification case not found"}
    return {"available": True, "items": items}


def _tool_get_dataset_verification_report(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.dataset_verification_case_service import (
        ExternalDatasetVerificationService,
    )

    _require(params, "case_public_id")
    service = ExternalDatasetVerificationService(settings)
    try:
        case = service.get_case(params["case_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "verification case not found"}
    if case["locked_at"] is None:
        return {"available": False, "reason": "case is not finalized yet -- no report exists"}
    return {"available": True, "status": case["status"], "report": case["report"]}


def _tool_get_dataset_reverification_status(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.dataset_verification_case_service import (
        ExternalDatasetVerificationService,
    )

    _require(params, "case_public_id")
    service = ExternalDatasetVerificationService(settings)
    try:
        case = service.get_case(params["case_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "verification case not found"}
    return {
        "available": True,
        "verification_expiry_status": case["verification_expiry_status"],
        "last_verified_at": case["last_verified_at"],
        "next_reverification_at": case["next_reverification_at"],
    }


# -- Phase 12: Approved Sample Import, Quarantine, File Safety, PII & Quality ------------


def _tool_get_sample_import(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )

    _require(params, "public_id")
    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    try:
        sample_import = repository.get_sample_import(params["public_id"])
    except NotFoundError:
        return {"available": False, "reason": "sample import not found"}
    return {"available": True, "sample_import": sample_import}


def _tool_list_sample_files(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )

    _require(params, "sample_import_public_id")
    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    try:
        files = repository.list_files(params["sample_import_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "sample import not found"}
    sanitized = [{k: v for k, v in f.items() if k != "relative_path"} for f in files]
    return {"available": True, "files": sanitized}


def _tool_get_sample_scan_summary(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )

    _require(params, "sample_import_public_id")
    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    try:
        results = repository.list_scan_results(params["sample_import_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "sample import not found"}
    counts: dict[str, int] = {}
    for result in results:
        counts[result["verdict"]] = counts.get(result["verdict"], 0) + 1
    return {"available": True, "total_files_scanned": len(results), "verdict_counts": counts}


def _tool_get_sample_quality_summary(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )

    _require(params, "sample_import_public_id")
    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    try:
        issues = repository.list_record_issues(
            params["sample_import_public_id"], issue_category="quality"
        )
    except NotFoundError:
        return {"available": False, "reason": "sample import not found"}
    counts: dict[str, int] = {}
    for issue in issues:
        counts[issue["status"]] = counts.get(issue["status"], 0) + 1
    return {"available": True, "total_quality_issues": len(issues), "status_counts": counts}


def _tool_get_sample_pii_summary(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    """Counts and categories only -- never a raw matched PII value."""

    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )

    _require(params, "sample_import_public_id")
    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    try:
        issues = repository.list_record_issues(
            params["sample_import_public_id"], issue_category="pii"
        )
    except NotFoundError:
        return {"available": False, "reason": "sample import not found"}
    category_counts: dict[str, int] = {}
    unresolved = 0
    for issue in issues:
        category_counts[issue["issue_type"]] = category_counts.get(issue["issue_type"], 0) + 1
        if issue["reviewer_decision"] is None:
            unresolved += 1
    return {
        "available": True,
        "total_pii_findings": len(issues),
        "category_counts": category_counts,
        "unresolved_findings": unresolved,
    }


def _tool_get_sample_duplicate_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )

    _require(params, "sample_import_public_id")
    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    try:
        issues = repository.list_record_issues(
            params["sample_import_public_id"], issue_category="duplicate"
        )
    except NotFoundError:
        return {"available": False, "reason": "sample import not found"}
    groups = {issue["related_group_id"] for issue in issues if issue["related_group_id"]}
    return {
        "available": True,
        "duplicate_groups": len(groups),
        "records_in_duplicate_groups": len(issues),
    }


def _tool_get_sample_contamination_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )

    _require(params, "sample_import_public_id")
    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    try:
        issues = repository.list_record_issues(
            params["sample_import_public_id"], issue_category="contamination"
        )
    except NotFoundError:
        return {"available": False, "reason": "sample import not found"}
    return {
        "available": True,
        "confirmed_overlap_count": sum(
            1 for issue in issues if issue["status"] == "confirmed_overlap"
        ),
    }


def _tool_get_sample_validation_report(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )

    _require(params, "sample_import_public_id")
    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    try:
        repository.get_sample_import(params["sample_import_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "sample import not found"}
    report = repository.get_latest_report(params["sample_import_public_id"])
    if report is None:
        return {"available": False, "reason": "report not yet finalized"}
    return {"available": True, "report": report}


def _tool_get_sample_rag_eligibility(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    """Only the two Phase 12 signals -- never anything resembling
    training or production-RAG approval."""

    from backend.database.repositories.dataset_sample_import import (
        DatasetSampleImportRepository,
    )

    _require(params, "sample_import_public_id")
    repository = DatasetSampleImportRepository(settings.resolved_database_path)
    try:
        sample_import = repository.get_sample_import(params["sample_import_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "sample import not found"}
    return {
        "available": True,
        "rag_sandbox_eligible": sample_import["rag_sandbox_eligible"],
        "training_assessment_status": sample_import["training_assessment_status"],
    }


# -- Phase 13: Isolated RAG Sandbox, Retrieval Evaluation, Grounded Answer Testing -------


def _tool_get_rag_sandbox_experiment(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.database.repositories.rag_sandbox import RagSandboxRepository

    _require(params, "public_id")
    repository = RagSandboxRepository(settings.resolved_database_path)
    try:
        experiment = repository.get_experiment(params["public_id"])
    except NotFoundError:
        return {"available": False, "reason": "rag sandbox experiment not found"}
    return {"available": True, "experiment": experiment}


def _tool_get_rag_sandbox_eligibility(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.rag_sandbox_eligibility_service import RagSandboxEligibilityService

    _require(params, "sample_import_public_id")
    try:
        result = RagSandboxEligibilityService(settings).check_eligibility(
            params["sample_import_public_id"]
        )
    except NotFoundError:
        return {"available": False, "reason": "sample import not found"}
    return {
        "available": True,
        "eligible": result["eligible"],
        "blocking_reasons": result["blocking_reasons"],
        "warnings": result["warnings"],
    }


def _tool_list_rag_sandbox_indexes(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.database.repositories.rag_sandbox import RagSandboxRepository

    _require(params, "experiment_public_id")
    repository = RagSandboxRepository(settings.resolved_database_path)
    try:
        indexes = repository.list_indexes(params["experiment_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "rag sandbox experiment not found"}
    return {"available": True, "indexes": indexes}


def _tool_get_rag_sandbox_retrieval_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.rag_sandbox import RagSandboxRepository

    _require(params, "experiment_public_id")
    repository = RagSandboxRepository(settings.resolved_database_path)
    try:
        runs = repository.list_retrieval_runs(params["experiment_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "rag sandbox experiment not found"}
    results = []
    for run in runs:
        results.extend(repository.list_retrieval_results(run["public_id"]))
    with_full_metrics = [row for row in results if row["metric_availability"] == "full"]
    hits = sum(1 for row in with_full_metrics if row["expected_source_hit"])
    return {
        "available": True,
        "retrieval_run_count": len(runs),
        "result_count": len(results),
        "metric_available_count": len(with_full_metrics),
        "expected_source_hit_rate": (hits / len(with_full_metrics)) if with_full_metrics else None,
    }


def _tool_get_rag_sandbox_answer_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.rag_sandbox import RagSandboxRepository

    _require(params, "experiment_public_id")
    repository = RagSandboxRepository(settings.resolved_database_path)
    try:
        answer_runs = repository.list_answer_runs(params["experiment_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "rag sandbox experiment not found"}
    return {
        "available": True,
        "answer_run_count": len(answer_runs),
        "grounded_answer_count": sum(
            1 for run in answer_runs if run["status"] == "grounded_answer"
        ),
        "insufficient_evidence_count": sum(
            1 for run in answer_runs if run["status"] == "insufficient_evidence"
        ),
        "refusal_count": sum(1 for run in answer_runs if run["refusal_used"]),
    }


def _tool_get_rag_sandbox_citation_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.rag_sandbox import RagSandboxRepository

    _require(params, "experiment_public_id")
    repository = RagSandboxRepository(settings.resolved_database_path)
    try:
        citations = repository.list_citations_for_experiment(params["experiment_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "rag sandbox experiment not found"}
    counts: dict[str, int] = {}
    for citation in citations:
        counts[citation["validation_status"]] = counts.get(citation["validation_status"], 0) + 1
    return {"available": True, "citation_count": len(citations), "counts_by_status": counts}


def _tool_get_rag_sandbox_language_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.rag_sandbox import RagSandboxRepository

    _require(params, "experiment_public_id")
    repository = RagSandboxRepository(settings.resolved_database_path)
    try:
        evaluations = repository.list_evaluations(
            params["experiment_public_id"], evaluation_type="language_compliance"
        )
    except NotFoundError:
        return {"available": False, "reason": "rag sandbox experiment not found"}
    respected = sum(1 for row in evaluations if row["result_status"] == "respected")
    return {
        "available": True,
        "evaluated_count": len(evaluations),
        "language_compliance_rate": (respected / len(evaluations)) if evaluations else None,
    }


def _tool_get_rag_sandbox_injection_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.rag_sandbox import RagSandboxRepository

    _require(params, "experiment_public_id")
    repository = RagSandboxRepository(settings.resolved_database_path)
    try:
        evaluations = repository.list_evaluations(
            params["experiment_public_id"], evaluation_type="prompt_injection"
        )
    except NotFoundError:
        return {"available": False, "reason": "rag sandbox experiment not found"}
    counts: dict[str, int] = {}
    for row in evaluations:
        counts[row["result_status"]] = counts.get(row["result_status"], 0) + 1
    return {
        "available": True,
        "evaluated_count": len(evaluations),
        "counts_by_result": counts,
        "note": "never claims complete prompt-injection security -- only what was tested",
    }


def _tool_get_rag_sandbox_report(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.database.repositories.rag_sandbox import RagSandboxRepository

    _require(params, "experiment_public_id")
    repository = RagSandboxRepository(settings.resolved_database_path)
    try:
        report = repository.get_latest_report(params["experiment_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "rag sandbox experiment not found"}
    if report is None:
        return {"available": False, "reason": "no finalized report yet"}
    return {
        "available": True,
        "report_version": report["report_version"],
        "production_rag_readiness": report["production_rag_readiness"],
        "training_data_observation": report["training_data_observation"],
        "recommended_next_action": report["recommended_next_action"],
    }


def _tool_get_rag_sandbox_acceptance_status(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.database.repositories.rag_sandbox import RagSandboxRepository

    _require(params, "experiment_public_id")
    repository = RagSandboxRepository(settings.resolved_database_path)
    try:
        acceptance = repository.get_latest_acceptance(params["experiment_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "rag sandbox experiment not found"}
    if acceptance is None:
        return {"available": True, "decided": False}
    return {
        "available": True,
        "decided": True,
        "decision": acceptance["decision"],
        "reviewed_at": acceptance["reviewed_at"],
    }


def _tool_get_knowledge_routing_policy(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    del settings, params
    from core_model.knowledge_routing.policy_loader import PolicyValidationError, get_policy

    try:
        policy = get_policy()
    except PolicyValidationError as exc:
        return {"available": True, "valid": False, "error": str(exc)}
    return {
        "available": True,
        "valid": True,
        "policy_version": policy["policy_version"],
        "taxonomy_version": policy["taxonomy_version"],
        "policy_checksum_sha256": policy.get("policy_checksum_sha256"),
        "domain_count": len(policy.get("domains", {})),
        "intent_count": len(policy.get("intents", {})),
    }


def _tool_list_knowledge_routing_reason_codes(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    del settings, params
    from core_model.knowledge_routing.reason_codes import REASON_CODE_REGISTRY

    return {
        "available": True,
        "reason_codes": REASON_CODE_REGISTRY,
        "count": len(REASON_CODE_REGISTRY),
    }


def _tool_get_knowledge_routing_metrics(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    del params
    from backend.services.knowledge_routing_classification_service import (
        KnowledgeRoutingClassificationService,
    )

    metrics = KnowledgeRoutingClassificationService(settings).aggregate_metrics()
    return {"available": True, **metrics}


def _tool_list_knowledge_routing_decisions(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.knowledge_routing_classification_service import (
        KnowledgeRoutingClassificationService,
    )

    service = KnowledgeRoutingClassificationService(settings)
    decisions = service.list_decisions(
        limit=int(params.get("limit", 20)),
        offset=int(params.get("offset", 0)),
        context_type=params.get("context_type"),
        execution_route=params.get("execution_route"),
        domain=params.get("domain"),
    )
    return {"available": True, "items": decisions}


def _tool_preview_knowledge_routing_classification(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    """Read-only preview: classifies text without persisting a decision
    row -- so this tool, unlike the API's `/classify` endpoint, never
    writes to the database."""

    del settings
    _require(params, "text")
    from core_model.knowledge_routing import CONTEXT_TYPES
    from core_model.knowledge_routing.pipeline import ClassificationInputError, classify

    context_type = params.get("context_type", "public_chat_question")
    if context_type not in CONTEXT_TYPES:
        raise ReadOnlyToolError(f"unknown context_type: {context_type!r}")
    try:
        result = classify(params["text"], context_type=context_type)
    except ClassificationInputError as exc:
        raise ReadOnlyToolError(str(exc)) from exc
    return {
        "available": True,
        "recommendation_only": True,
        "route_executed": False,
        "language_category": result.language_category,
        "intent": result.intent,
        "domain": result.domain,
        "subdomain": result.subdomain,
        "freshness": result.freshness,
        "evidence_requirement": result.evidence_requirement,
        "execution_route": result.execution_route,
        "learning_target": result.learning_target,
        "safety_risk": result.safety_risk,
        "all_reason_codes": list(result.all_reason_codes),
    }


def _tool_get_public_chat_routing_overview(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    """Aggregate route/safety/language counts for the Phase 18 public
    chatbot -- never raw question or answer text, since that is never
    persisted in the first place."""

    del params
    from backend.database.repositories.public_chat import PublicChatRoutingRepository

    repo = PublicChatRoutingRepository(settings.resolved_database_path)
    metrics = repo.aggregate_metrics()
    language = repo.language_compliance_summary()
    return {
        "available": True,
        **metrics,
        "language_compliance": language,
        "clarification_count": metrics["by_resolved_route"].get("clarify", 0),
        "refusal_count": metrics["by_resolved_route"].get("refuse", 0),
        "insufficient_count": metrics["by_resolved_route"].get("insufficient", 0),
    }


def _tool_get_public_chat_route_event(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    _require(params, "public_id")
    from backend.database.repositories.public_chat import PublicChatRoutingRepository

    repo = PublicChatRoutingRepository(settings.resolved_database_path)
    event = repo.get_event(params["public_id"])
    if event is None:
        return {"available": False, "reason": "event not found"}
    return {"available": True, **event}


def _tool_get_public_chat_language_compliance(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    del params
    from backend.database.repositories.public_chat import PublicChatRoutingRepository

    repo = PublicChatRoutingRepository(settings.resolved_database_path)
    return {"available": True, **repo.language_compliance_summary()}


def _tool_get_public_chat_safety_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    del params
    from backend.database.repositories.public_chat import PublicChatRoutingRepository

    repo = PublicChatRoutingRepository(settings.resolved_database_path)
    metrics = repo.aggregate_metrics()
    return {
        "available": True,
        "by_safety_status": metrics["by_safety_status"],
        "refusal_count": metrics["by_resolved_route"].get("refuse", 0),
        "total_requests": metrics["total_requests"],
    }


def _tool_get_public_chat_unavailable_route_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    """Reports Trusted-Web/Tool recommendation-vs-availability honesty
    counts and overall insufficient-evidence volume -- these routes are
    intentionally unavailable in Phase 18, never silently substituted."""

    del params
    from backend.database.repositories.public_chat import PublicChatRoutingRepository

    repo = PublicChatRoutingRepository(settings.resolved_database_path)
    metrics = repo.aggregate_metrics()
    return {
        "available": True,
        "trusted_web_unavailable_count": metrics["trusted_web_unavailable_count"],
        "tool_unavailable_count": metrics["tool_unavailable_count"],
        "insufficient_count": metrics["by_resolved_route"].get("insufficient", 0),
        "total_requests": metrics["total_requests"],
    }


def _tool_get_knowledge_gap_overview(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    del params
    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository

    repo = KnowledgeGapRepository(settings.resolved_database_path)
    overview = repo.aggregate_overview()
    return {
        "available": True,
        **overview,
        "tamil": repo.tamil_capability_summary(),
        "web_demand": repo.web_demand_summary(),
        "tool_demand": repo.tool_demand_summary(),
        "language_failures": repo.language_failure_summary(),
    }


def _tool_get_knowledge_gap_case(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    _require(params, "case_public_id")
    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository

    repo = KnowledgeGapRepository(settings.resolved_database_path)
    try:
        case = repo.get_case(params["case_public_id"])
    except Exception:
        return {"available": False, "reason": "case not found"}
    return {"available": True, **case}


def _tool_list_top_knowledge_gaps(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository

    repo = KnowledgeGapRepository(settings.resolved_database_path)
    cases = repo.list_cases(
        limit=int(params.get("limit", 10)),
        priority_band=params.get("priority_band"),
        event_type=params.get("event_type"),
    )
    return {"available": True, "items": cases}


def _tool_get_knowledge_gap_cluster(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    _require(params, "cluster_public_id")
    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository

    repo = KnowledgeGapRepository(settings.resolved_database_path)
    try:
        cluster = repo.get_cluster(params["cluster_public_id"])
    except Exception:
        return {"available": False, "reason": "cluster not found"}
    cluster["members"] = repo.list_cluster_members(params["cluster_public_id"])
    return {"available": True, **cluster}


def _tool_get_tamil_knowledge_gap_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    del params
    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository

    repo = KnowledgeGapRepository(settings.resolved_database_path)
    return {"available": True, **repo.tamil_capability_summary()}


def _tool_get_web_demand_summary(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    del params
    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository

    repo = KnowledgeGapRepository(settings.resolved_database_path)
    return {"available": True, **repo.web_demand_summary()}


def _tool_get_tool_demand_summary(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    del params
    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository

    repo = KnowledgeGapRepository(settings.resolved_database_path)
    return {"available": True, **repo.tool_demand_summary()}


def _tool_get_language_failure_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    del params
    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository

    repo = KnowledgeGapRepository(settings.resolved_database_path)
    return {"available": True, **repo.language_failure_summary()}


def _tool_get_daily_knowledge_gap_report(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    del params
    from backend.services.knowledge_gap_daily_report_service import (
        KnowledgeGapDailyReportService,
    )

    report = KnowledgeGapDailyReportService(settings).latest()
    if report is None:
        return {"available": False, "reason": "no daily report generated yet"}
    return {"available": True, **report}


def _tool_get_trusted_web_overview(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    del params
    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
    from backend.database.repositories.trusted_web_tool_gateway import (
        TrustedWebToolGatewayRepository,
    )

    repo = TrustedWebToolGatewayRepository(settings.resolved_database_path)
    overview = repo.trusted_web_overview()
    overview["web_demand"] = KnowledgeGapRepository(
        settings.resolved_database_path
    ).web_demand_summary()
    return {"available": True, **overview}


def _tool_get_trusted_web_health(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    del params
    from backend.services.trusted_web_answer_service import TrustedWebAnswerService
    from backend.services.trusted_web_policy_service import load_policy

    service = TrustedWebAnswerService(settings)
    try:
        load_policy()
        policy_loaded = True
    except Exception:  # noqa: BLE001
        policy_loaded = False
    return {
        "available": True,
        "provider_available": service.is_available(),
        "policy_loaded": policy_loaded,
        "external_mcp_enabled": settings.external_mcp_enabled,
    }


def _tool_get_web_source_verification_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    del params
    from backend.database.repositories.trusted_web_tool_gateway import (
        TrustedWebToolGatewayRepository,
    )

    repo = TrustedWebToolGatewayRepository(settings.resolved_database_path)
    return {"available": True, **repo.web_verification_summary()}


def _tool_get_web_freshness_summary(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    del params
    from backend.database.repositories.trusted_web_tool_gateway import (
        TrustedWebToolGatewayRepository,
    )

    repo = TrustedWebToolGatewayRepository(settings.resolved_database_path)
    return {"available": True, **repo.web_freshness_summary()}


def _tool_get_web_conflict_summary(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    del params
    from backend.database.repositories.trusted_web_tool_gateway import (
        TrustedWebToolGatewayRepository,
    )

    repo = TrustedWebToolGatewayRepository(settings.resolved_database_path)
    overview = repo.trusted_web_overview()
    return {"available": True, "conflicts": overview["conflicts"]}


def _tool_get_tool_gateway_overview(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    del params
    from backend.database.repositories.knowledge_gap import KnowledgeGapRepository
    from backend.database.repositories.trusted_web_tool_gateway import (
        TrustedWebToolGatewayRepository,
    )

    repo = TrustedWebToolGatewayRepository(settings.resolved_database_path)
    overview = repo.tool_gateway_overview()
    overview["tool_demand"] = KnowledgeGapRepository(
        settings.resolved_database_path
    ).tool_demand_summary()
    overview["external_mcp_enabled"] = settings.external_mcp_enabled
    return {"available": True, **overview}


def _tool_get_tool_execution_summary(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.database.repositories.trusted_web_tool_gateway import (
        TrustedWebToolGatewayRepository,
    )

    repo = TrustedWebToolGatewayRepository(settings.resolved_database_path)
    items = repo.list_tool_executions(
        limit=int(params.get("limit", 20)), offset=0, tool_name=params.get("tool_name")
    )
    return {"available": True, "items": items}


def _tool_get_mcp_readiness_summary(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    del params
    from backend.services.deterministic_tool_registry import list_tool_descriptors

    descriptors = list_tool_descriptors()
    return {
        "available": True,
        "external_mcp_enabled": settings.external_mcp_enabled,
        "built_in_deterministic_tools": [d.tool_name for d in descriptors],
        "internal_service_tools": [],
        "external_mcp_tools": [],
    }


def _tool_analyze_document_readiness(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.document_workspace_service import PDFResearchWorkspaceService

    _require(params, "document_public_id")
    service = PDFResearchWorkspaceService(settings)
    try:
        return {"available": True, **service.workspace(params["document_public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "document not found"}


def _tool_get_document_issue_summary(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.document_workspace_service import DocumentPageReviewService

    _require(params, "document_public_id")
    service = DocumentPageReviewService(settings)
    try:
        return {"available": True, **service.review_summary(params["document_public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "document not found"}


def _tool_list_critical_document_pages(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    _require(params, "document_public_id")
    repository = DocumentRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            document = repository.document(connection, params["document_public_id"])
            rows = connection.execute(
                "SELECT page_number,review_status,extraction_status,confidence_score,"
                "warnings_json FROM document_pages WHERE document_source_id=? "
                "ORDER BY page_number",
                (document["id"],),
            ).fetchall()
            tamil_pages = {
                row["page_number"]
                for row in connection.execute(
                    "SELECT DISTINCT page_number FROM document_tamil_quality_issues "
                    "WHERE document_source_id=? AND review_status='pending'",
                    (document["id"],),
                ).fetchall()
            }
    except NotFoundError:
        return {"available": False, "reason": "document not found"}
    critical: list[dict[str, Any]] = []
    for row in rows:
        reasons = []
        if row["extraction_status"] == "failed":
            reasons.append("extraction_failed")
        if (
            row["confidence_score"] is not None
            and row["confidence_score"] < settings.ocr_confidence_warning_threshold
        ):
            reasons.append("low_ocr_confidence")
        if row["warnings_json"] not in (None, "[]"):
            reasons.append("extraction_warnings")
        if row["page_number"] in tamil_pages:
            reasons.append("tamil_quality_issue")
        if row["review_status"] in ("needs_correction", "rejected"):
            reasons.append(f"review_status_{row['review_status']}")
        if reasons:
            critical.append({"page_number": row["page_number"], "reasons": reasons})
    return {
        "available": True,
        "document_public_id": params["document_public_id"],
        "critical_page_count": len(critical),
        "critical_pages": critical,
    }


def _tool_get_document_cleanup_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.document_workspace_service import DocumentCleanupService

    _require(params, "document_public_id")
    service = DocumentCleanupService(settings)
    try:
        elements = service.list_repeated_elements(params["document_public_id"], None)
    except NotFoundError:
        return {"available": False, "reason": "document not found"}
    by_type: dict[str, int] = {}
    for item in elements.get("items", []):
        by_type[item["element_type"]] = by_type.get(item["element_type"], 0) + 1
    return {
        "available": True,
        "repeated_element_count": len(elements.get("items", [])),
        "by_element_type": by_type,
    }


def _tool_get_document_tamil_quality_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.document_tamil_quality_service import DocumentTamilQualityService

    _require(params, "document_public_id")
    service = DocumentTamilQualityService(settings)
    try:
        return {"available": True, **service.summary(params["document_public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "document not found"}


def _tool_get_document_chunk_summary(settings: Settings, params: dict[str, Any]) -> dict[str, Any]:
    from backend.services.semantic_chunk_service import ChunkConflictService

    _require(params, "document_public_id")
    service = ChunkConflictService(settings)
    try:
        coverage = service.coverage_report(params["document_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "document not found"}
    return {"available": True, "coverage_by_page": coverage}


def _tool_get_document_sft_candidate_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.document_sft_candidate_service import (
        DocumentSftCandidateGenerationService,
    )

    _require(params, "document_public_id")
    service = DocumentSftCandidateGenerationService(settings)
    try:
        return {"available": True, **service.summary(params["document_public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "document not found"}


def _tool_get_document_training_readiness(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.document_sft_candidate_service import (
        DocumentSftCandidateGenerationService,
    )

    _require(params, "document_public_id")
    service = DocumentSftCandidateGenerationService(settings)
    try:
        summary = service.summary(params["document_public_id"])
    except NotFoundError:
        return {"available": False, "reason": "document not found"}
    approved = summary["approved_count"]
    blockers = [] if approved > 0 else ["no approved SFT candidates yet"]
    return {
        "available": True,
        "document_public_id": params["document_public_id"],
        "approved_candidate_count": approved,
        "ready_to_export": approved > 0,
        "blockers": blockers,
        "next_action": (
            "export approved candidates to JSONL"
            if approved > 0
            else "review and approve SFT candidates"
        ),
    }


def _tool_get_document_sft_handoff_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.document_sft_export_service import DocumentSftExportService

    _require(params, "document_public_id")
    export_service = DocumentSftExportService(settings)
    try:
        exports = export_service.list_exports(params["document_public_id"])["items"]
    except NotFoundError:
        return {"available": False, "reason": "document not found"}
    if not exports:
        return {"available": True, "handoff_exists": False, "exports": []}
    repository = DocumentRepository(settings.resolved_database_path)
    handoffs = []
    with repository.transaction() as connection:
        for export in exports:
            row = connection.execute(
                "SELECT * FROM document_sft_dataset_handoffs WHERE export_public_id=?",
                (export["public_id"],),
            ).fetchone()
            if row is not None:
                handoffs.append(dict(row))
    return {"available": True, "handoff_exists": bool(handoffs), "handoffs": handoffs}


def _tool_get_document_sft_generator_eligibility(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    _require(params, "document_public_id")
    repository = DocumentRepository(settings.resolved_database_path)
    try:
        with repository.transaction() as connection:
            document = repository.document(connection, params["document_public_id"])
            rows = connection.execute(
                "SELECT chunk_type,COUNT(*) count FROM semantic_chunks WHERE "
                "document_source_id=? AND status='approved' GROUP BY chunk_type",
                (document["id"],),
            ).fetchall()
    except NotFoundError:
        return {"available": False, "reason": "document not found"}
    by_chunk_type = {row["chunk_type"]: row["count"] for row in rows}
    return {"available": True, "approved_chunk_counts_by_type": by_chunk_type}


def _tool_get_document_cleanup_detector_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.document_workspace_service import DocumentCleanupService

    _require(params, "document_public_id")
    service = DocumentCleanupService(settings)
    try:
        elements = service.list_repeated_elements(params["document_public_id"], None)
    except NotFoundError:
        return {"available": False, "reason": "document not found"}
    by_type: dict[str, int] = {}
    items = elements.get("items", [])
    for item in items:
        by_type[item["element_type"]] = by_type.get(item["element_type"], 0) + 1
    return {"available": True, "repeated_element_count": len(items), "by_type": by_type}


def _tool_get_document_tamil_correction_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    del params
    from backend.services.document_tamil_correction_registry_service import (
        DocumentTamilCorrectionRegistryService,
    )

    service = DocumentTamilCorrectionRegistryService(settings)
    rules = service.list_rules(page_size=200)["items"]
    by_status: dict[str, int] = {}
    for rule in rules:
        by_status[rule["status"]] = by_status.get(rule["status"], 0) + 1
    return {"available": True, "total_rules": len(rules), "by_status": by_status}


def _tool_get_document_media_content_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.document_content_classification_service import (
        DocumentContentClassificationService,
    )

    _require(params, "document_public_id")
    service = DocumentContentClassificationService(settings)
    try:
        return {"available": True, **service.summary(params["document_public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "document not found"}


def _tool_get_document_security_review_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.document_security_review_service import DocumentSecurityReviewService

    _require(params, "document_public_id")
    service = DocumentSecurityReviewService(settings)
    try:
        return {"available": True, **service.summary(params["document_public_id"])}
    except NotFoundError:
        return {"available": False, "reason": "document not found"}


def _tool_get_document_pii_review_summary(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.document_security_review_service import DocumentSecurityReviewService

    _require(params, "document_public_id")
    service = DocumentSecurityReviewService(settings)
    try:
        findings = service.list_findings(params["document_public_id"], page_size=200)["items"]
    except NotFoundError:
        return {"available": False, "reason": "document not found"}
    pii_findings = [item for item in findings if item["finding_type"].startswith("pii_")]
    by_type: dict[str, int] = {}
    pending_review = 0
    for item in pii_findings:
        by_type[item["finding_type"]] = by_type.get(item["finding_type"], 0) + 1
        if item["review_status"] == "pending":
            pending_review += 1
    return {
        "available": True,
        "total_pii_findings": len(pii_findings),
        "by_type": by_type,
        "pending_review": pending_review,
    }


def _tool_get_document_dataset_version_status(
    settings: Settings, params: dict[str, Any]
) -> dict[str, Any]:
    from backend.services.document_sft_export_service import DocumentSftExportService

    _require(params, "document_public_id")
    export_service = DocumentSftExportService(settings)
    try:
        exports = export_service.list_exports(params["document_public_id"])["items"]
    except NotFoundError:
        return {"available": False, "reason": "document not found"}
    repository = DocumentRepository(settings.resolved_database_path)
    with repository.transaction() as connection:
        for export in exports:
            row = connection.execute(
                "SELECT status,dataset_version_public_id,dataset_build_public_id FROM "
                "document_sft_dataset_handoffs WHERE export_public_id=?",
                (export["public_id"],),
            ).fetchone()
            if row is not None and row["dataset_version_public_id"]:
                return {
                    "available": True, "status": row["status"],
                    "dataset_version_public_id": row["dataset_version_public_id"],
                    "dataset_build_public_id": row["dataset_build_public_id"],
                }
    return {
        "available": True,
        "status": "no_dataset_version_proposed",
        "dataset_version_public_id": None,
    }


class ToolDefinition:
    __slots__ = ("name", "mode", "description", "required_params", "handler")

    def __init__(
        self,
        name: str,
        mode: str,
        description: str,
        required_params: tuple[str, ...],
        handler: ToolFunction,
    ) -> None:
        self.name = name
        self.mode = mode
        self.description = description
        self.required_params = required_params
        self.handler = handler


READ_ONLY_TOOLS: tuple[ToolDefinition, ...] = (
    ToolDefinition(
        "get_dashboard_overview",
        "guide",
        "Counts and guidance across every governed area of the dashboard.",
        (),
        _tool_dashboard_overview,
    ),
    ToolDefinition(
        "get_page_help",
        "guide",
        "Purpose, tabs, prerequisites, and safety notes for one dashboard page.",
        (),  # accepts either page_id or nav_key -- enforced inside the handler
        _tool_page_help,
    ),
    ToolDefinition(
        "get_pending_admin_proposals",
        "governance",
        "Admin Assistant proposals currently awaiting Admin Review.",
        (),
        _tool_pending_admin_proposals,
    ),
    ToolDefinition(
        "get_governance_review_queue",
        "governance",
        "The unified Quality & Approval review queue, optionally filtered.",
        (),
        _tool_governance_review_queue,
    ),
    ToolDefinition(
        "get_governance_entity_status",
        "governance",
        "Per-target-use governance approval status for one entity.",
        ("entity_type", "entity_public_id"),
        _tool_governance_entity_status,
    ),
    ToolDefinition(
        "get_governed_build_status",
        "data",
        "Status, selection, and progress of one Builds & Pipelines build request.",
        ("public_id",),
        _tool_governed_build_status,
    ),
    ToolDefinition(
        "list_governed_builds",
        "data",
        "Recent Builds & Pipelines build requests, optionally filtered by status/target.",
        (),
        _tool_list_governed_builds,
    ),
    ToolDefinition(
        "get_lineage_trace",
        "data",
        "Upstream/downstream lineage trace anchored at one entity.",
        ("entity_type", "entity_id"),
        _tool_lineage_trace,
    ),
    ToolDefinition(
        "get_source_status",
        "data",
        "A registered data source's status, type, and rights linkage.",
        ("public_id",),
        _tool_source_status,
    ),
    ToolDefinition(
        "list_rag_knowledge_spaces",
        "rag",
        "Every Knowledge & RAG knowledge space and its status.",
        (),
        _tool_list_rag_knowledge_spaces,
    ),
    ToolDefinition(
        "get_model_evaluation_run",
        "model",
        "Status, metrics, and issues for one Evaluation run.",
        ("public_id",),
        _tool_model_evaluation_run,
    ),
    ToolDefinition(
        "get_model_release_candidate",
        "model",
        "Status, eligibility, and approvals for one Model Registry release candidate.",
        ("public_id",),
        _tool_model_release_candidate,
    ),
    ToolDefinition(
        "list_pretraining_readiness_evaluations",
        "model",
        "Every recorded Pretraining Readiness evaluation and its outcome.",
        (),
        _tool_pretraining_readiness_evaluations,
    ),
    ToolDefinition(
        "get_recent_audit_events",
        "system",
        "The most recent audit log entries.",
        (),
        _tool_recent_audit_events,
    ),
    ToolDefinition(
        "list_external_data_providers",
        "data",
        "Every registered external data provider, optionally filtered by type/lifecycle/enabled.",
        (),
        _tool_list_external_data_providers,
    ),
    ToolDefinition(
        "get_external_data_provider",
        "data",
        "Full registry detail for one external data provider.",
        ("public_id",),
        _tool_get_external_data_provider,
    ),
    ToolDefinition(
        "get_provider_capabilities",
        "data",
        "The declared capabilities (read/search/etc.) for one external data provider.",
        ("public_id",),
        _tool_get_provider_capabilities,
    ),
    ToolDefinition(
        "get_provider_connection_status",
        "data",
        "The most recent connection-test result(s) for one external data provider.",
        ("public_id",),
        _tool_get_provider_connection_status,
    ),
    ToolDefinition(
        "list_dataset_search_sessions",
        "data",
        "Recent Live Dataset Discovery research sessions, optionally filtered by status.",
        (),
        _tool_list_dataset_search_sessions,
    ),
    ToolDefinition(
        "get_dataset_search_session",
        "data",
        "One discovery session's status/stage plus its captured requirement, if any.",
        ("public_id",),
        _tool_get_dataset_search_session,
    ),
    ToolDefinition(
        "list_dataset_candidates",
        "data",
        "Every discovered/manually-added candidate in one discovery session.",
        ("session_public_id",),
        _tool_list_dataset_candidates,
    ),
    ToolDefinition(
        "get_dataset_candidate",
        "data",
        "One candidate's normalized metadata, raw provider sources, and explainable scores.",
        ("public_id",),
        _tool_get_dataset_candidate,
    ),
    ToolDefinition(
        "get_dataset_verification_case",
        "data",
        "One licence/rights verification case's full status: identity, evidence, licence, "
        "terms, upstream, and permission roll-ups.",
        ("public_id",),
        _tool_get_dataset_verification_case,
    ),
    ToolDefinition(
        "list_dataset_evidence",
        "data",
        "Every collected evidence snapshot for one verification case (type, authority "
        "level, checksum, retrieval status).",
        ("case_public_id",),
        _tool_list_dataset_evidence,
    ),
    ToolDefinition(
        "get_dataset_permission_assessments",
        "data",
        "All 16 independently-assessed permission dimensions for one verification case, "
        "each with its own status/decision basis/reviewer.",
        ("case_public_id",),
        _tool_get_dataset_permission_assessments,
    ),
    ToolDefinition(
        "get_dataset_verification_conflicts",
        "data",
        "Every detected evidence conflict for one verification case, with severity and "
        "resolution status.",
        ("case_public_id",),
        _tool_get_dataset_verification_conflicts,
    ),
    ToolDefinition(
        "get_dataset_verification_report",
        "data",
        "The immutable finalized verification report for one case, if it has been "
        "finalized -- unavailable otherwise.",
        ("case_public_id",),
        _tool_get_dataset_verification_report,
    ),
    ToolDefinition(
        "get_dataset_reverification_status",
        "data",
        "One verification case's expiry status and last/next reverification dates.",
        ("case_public_id",),
        _tool_get_dataset_reverification_status,
    ),
    ToolDefinition(
        "get_sample_import",
        "data",
        "One Phase 12 sample import's full status: lifecycle, current stage, approval "
        "linkage, and quarantine footprint.",
        ("public_id",),
        _tool_get_sample_import,
    ),
    ToolDefinition(
        "list_sample_files",
        "data",
        "Every quarantined file for one sample import, with validation/scan status -- "
        "metadata only, never a file path or raw content.",
        ("sample_import_public_id",),
        _tool_list_sample_files,
    ),
    ToolDefinition(
        "get_sample_scan_summary",
        "data",
        "Security-scan verdict counts for one sample import's files.",
        ("sample_import_public_id",),
        _tool_get_sample_scan_summary,
    ),
    ToolDefinition(
        "get_sample_quality_summary",
        "data",
        "Quality-issue counts by review status for one sample import's records.",
        ("sample_import_public_id",),
        _tool_get_sample_quality_summary,
    ),
    ToolDefinition(
        "get_sample_pii_summary",
        "data",
        "PII finding counts by category for one sample import -- counts and categories "
        "only, never a raw matched value.",
        ("sample_import_public_id",),
        _tool_get_sample_pii_summary,
    ),
    ToolDefinition(
        "get_sample_duplicate_summary",
        "data",
        "Duplicate-group counts for one sample import's records.",
        ("sample_import_public_id",),
        _tool_get_sample_duplicate_summary,
    ),
    ToolDefinition(
        "get_sample_contamination_summary",
        "data",
        "Confirmed evaluation-contamination overlap count for one sample import.",
        ("sample_import_public_id",),
        _tool_get_sample_contamination_summary,
    ),
    ToolDefinition(
        "get_sample_validation_report",
        "data",
        "The immutable finalized sample-validation report, if finalized -- unavailable "
        "otherwise.",
        ("sample_import_public_id",),
        _tool_get_sample_validation_report,
    ),
    ToolDefinition(
        "get_sample_rag_eligibility",
        "data",
        "Only `rag_sandbox_eligible` and `training_assessment_status` -- never anything "
        "resembling training or production-RAG approval.",
        ("sample_import_public_id",),
        _tool_get_sample_rag_eligibility,
    ),
    ToolDefinition(
        "get_rag_sandbox_experiment",
        "data",
        "One Phase 13 RAG sandbox experiment's full status: lifecycle, current stage, "
        "and advisory readiness signals.",
        ("public_id",),
        _tool_get_rag_sandbox_experiment,
    ),
    ToolDefinition(
        "get_rag_sandbox_eligibility",
        "data",
        "Whether a Phase 12 sample import is eligible to become a RAG sandbox experiment, "
        "and why not if blocked.",
        ("sample_import_public_id",),
        _tool_get_rag_sandbox_eligibility,
    ),
    ToolDefinition(
        "list_rag_sandbox_indexes",
        "data",
        "Every BM25/vector/hybrid index built for one sandbox experiment, with status "
        "and chunk counts.",
        ("experiment_public_id",),
        _tool_list_rag_sandbox_indexes,
    ),
    ToolDefinition(
        "get_rag_sandbox_retrieval_summary",
        "data",
        "Retrieval-run and expected-source-hit-rate summary for one sandbox experiment.",
        ("experiment_public_id",),
        _tool_get_rag_sandbox_retrieval_summary,
    ),
    ToolDefinition(
        "get_rag_sandbox_answer_summary",
        "data",
        "Grounded-answer and refusal counts for one sandbox experiment.",
        ("experiment_public_id",),
        _tool_get_rag_sandbox_answer_summary,
    ),
    ToolDefinition(
        "get_rag_sandbox_citation_summary",
        "data",
        "Citation validation-status counts for one sandbox experiment.",
        ("experiment_public_id",),
        _tool_get_rag_sandbox_citation_summary,
    ),
    ToolDefinition(
        "get_rag_sandbox_language_summary",
        "data",
        "Language-compliance evaluation counts and rate for one sandbox experiment.",
        ("experiment_public_id",),
        _tool_get_rag_sandbox_language_summary,
    ),
    ToolDefinition(
        "get_rag_sandbox_injection_summary",
        "data",
        "Prompt-injection resistance test counts by result for one sandbox experiment -- "
        "never claims complete security.",
        ("experiment_public_id",),
        _tool_get_rag_sandbox_injection_summary,
    ),
    ToolDefinition(
        "get_rag_sandbox_report",
        "data",
        "The latest finalized sandbox report's advisory readiness signals, if finalized.",
        ("experiment_public_id",),
        _tool_get_rag_sandbox_report,
    ),
    ToolDefinition(
        "get_rag_sandbox_acceptance_status",
        "data",
        "Whether an Admin has made an acceptance decision for one sandbox experiment, "
        "and what it was.",
        ("experiment_public_id",),
        _tool_get_rag_sandbox_acceptance_status,
    ),
    ToolDefinition(
        "get_knowledge_routing_policy",
        "governance",
        "The loaded, checksum-verified Phase 17 knowledge-routing policy's version and summary.",
        (),
        _tool_get_knowledge_routing_policy,
    ),
    ToolDefinition(
        "list_knowledge_routing_reason_codes",
        "governance",
        "The full stable reason-code registry the knowledge-routing classifier emits from.",
        (),
        _tool_list_knowledge_routing_reason_codes,
    ),
    ToolDefinition(
        "get_knowledge_routing_metrics",
        "governance",
        "Aggregate counts of stored knowledge-routing classification decisions, by execution "
        "route, domain, and learning target.",
        (),
        _tool_get_knowledge_routing_metrics,
    ),
    ToolDefinition(
        "list_knowledge_routing_decisions",
        "governance",
        "Recently stored knowledge-routing classification decisions -- never includes raw "
        "question text, only the SHA-256 input hash and structured outputs.",
        (),
        _tool_list_knowledge_routing_decisions,
    ),
    ToolDefinition(
        "preview_knowledge_routing_classification",
        "governance",
        "Classify a piece of text with the Phase 17 knowledge-routing pipeline without "
        "persisting a decision row -- recommendation only, no route is executed.",
        ("text",),
        _tool_preview_knowledge_routing_classification,
    ),
    ToolDefinition(
        "get_public_chat_routing_overview",
        "governance",
        "Aggregate route/safety/language counts for the Phase 18 public chatbot -- never "
        "raw question or answer text.",
        (),
        _tool_get_public_chat_routing_overview,
    ),
    ToolDefinition(
        "get_public_chat_route_event",
        "governance",
        "One stored public-chat routing event by its public id -- structured route/safety/"
        "language outcome only, no raw text.",
        ("public_id",),
        _tool_get_public_chat_route_event,
    ),
    ToolDefinition(
        "get_public_chat_language_compliance",
        "governance",
        "Tanglish-output-compliance counts for the public chatbot's answer language policy.",
        (),
        _tool_get_public_chat_language_compliance,
    ),
    ToolDefinition(
        "get_public_chat_safety_summary",
        "governance",
        "Input/output safety-status counts and refusal volume for the public chatbot.",
        (),
        _tool_get_public_chat_safety_summary,
    ),
    ToolDefinition(
        "get_public_chat_unavailable_route_summary",
        "governance",
        "How often Trusted-Web/Tool were recommended but honestly reported unavailable, "
        "and the resulting insufficient-evidence volume.",
        (),
        _tool_get_public_chat_unavailable_route_summary,
    ),
    ToolDefinition(
        "get_knowledge_gap_overview",
        "governance",
        "Aggregate counts of the Phase 19 knowledge-gap registry -- by event type, status, "
        "priority band, plus Tamil/Web/Tool/language-failure summaries.",
        (),
        _tool_get_knowledge_gap_overview,
    ),
    ToolDefinition(
        "get_knowledge_gap_case",
        "governance",
        "One knowledge-gap case by its public id -- structured fields only, never raw "
        "question text.",
        ("case_public_id",),
        _tool_get_knowledge_gap_case,
    ),
    ToolDefinition(
        "list_top_knowledge_gaps",
        "governance",
        "Recent knowledge-gap cases, optionally filtered by priority band or event type, "
        "ordered by priority.",
        (),
        _tool_list_top_knowledge_gaps,
    ),
    ToolDefinition(
        "get_knowledge_gap_cluster",
        "governance",
        "One knowledge-gap cluster and its member cases by cluster public id.",
        ("cluster_public_id",),
        _tool_get_knowledge_gap_cluster,
    ),
    ToolDefinition(
        "get_tamil_knowledge_gap_summary",
        "governance",
        "Tamil-language capability-gap counts and how many received the explainable "
        "Tamil-first priority boost.",
        (),
        _tool_get_tamil_knowledge_gap_summary,
    ),
    ToolDefinition(
        "get_web_demand_summary",
        "governance",
        "How much demand exists for Trusted-Web capability that is currently unavailable.",
        (),
        _tool_get_web_demand_summary,
    ),
    ToolDefinition(
        "get_tool_demand_summary",
        "governance",
        "How much demand exists for deterministic-tool capability that is currently "
        "unavailable.",
        (),
        _tool_get_tool_demand_summary,
    ),
    ToolDefinition(
        "get_language_failure_summary",
        "governance",
        "Count of registered wrong-output-language / language-understanding failure cases.",
        (),
        _tool_get_language_failure_summary,
    ),
    ToolDefinition(
        "get_daily_knowledge_gap_report",
        "governance",
        "The most recently generated daily knowledge-gap report summary.",
        (),
        _tool_get_daily_knowledge_gap_report,
    ),
    ToolDefinition(
        "get_trusted_web_overview",
        "governance",
        "Aggregate counts of the Phase 20 Trusted Web gateway -- search events by status/"
        "category, conflicts, blocked fetches, injection blocks, resolved Web capability gaps, "
        "plus real Web demand from the knowledge-gap registry.",
        (),
        _tool_get_trusted_web_overview,
    ),
    ToolDefinition(
        "get_trusted_web_health",
        "governance",
        "Whether the configured search provider is currently healthy, whether the source-trust "
        "policy loaded successfully, and whether external MCP is enabled (always false in this "
        "phase).",
        (),
        _tool_get_trusted_web_health,
    ),
    ToolDefinition(
        "get_web_source_verification_summary",
        "governance",
        "Counts of retained Web evidence by achieved verification level (search_result_only "
        "through official_source_verified).",
        (),
        _tool_get_web_source_verification_summary,
    ),
    ToolDefinition(
        "get_web_freshness_summary",
        "governance",
        "Counts of Web search events by overall freshness status (fresh/possibly_stale/stale/"
        "undated/conflicting).",
        (),
        _tool_get_web_freshness_summary,
    ),
    ToolDefinition(
        "get_web_conflict_summary",
        "governance",
        "Counts of Web search events by source-conflict status -- never silently resolved, "
        "always disclosed.",
        (),
        _tool_get_web_conflict_summary,
    ),
    ToolDefinition(
        "get_tool_gateway_overview",
        "governance",
        "Aggregate counts of the Phase 20 deterministic tool gateway -- executions by tool/"
        "status, resolved Tool capability gaps, real Tool demand, external MCP enabled state.",
        (),
        _tool_get_tool_gateway_overview,
    ),
    ToolDefinition(
        "get_tool_execution_summary",
        "governance",
        "Recent deterministic-tool execution events, optionally filtered by tool name.",
        (),
        _tool_get_tool_execution_summary,
    ),
    ToolDefinition(
        "get_mcp_readiness_summary",
        "governance",
        "The MCP-ready contract's tool sources -- built-in deterministic tools (active), "
        "internal-service and external-MCP tools (both always empty in this phase) -- and "
        "whether external MCP is enabled (always false).",
        (),
        _tool_get_mcp_readiness_summary,
    ),
    ToolDefinition(
        "analyze_document_readiness",
        "data",
        "Overall readiness snapshot for one document: source link, rights warnings, page "
        "review counts, and readiness status.",
        ("document_public_id",),
        _tool_analyze_document_readiness,
    ),
    ToolDefinition(
        "get_document_issue_summary",
        "data",
        "Per-document page review counts, next unreviewed page, and low-OCR-confidence pages.",
        ("document_public_id",),
        _tool_get_document_issue_summary,
    ),
    ToolDefinition(
        "list_critical_document_pages",
        "data",
        "Pages that need admin attention (failed extraction, low OCR confidence, extraction "
        "warnings, pending Tamil quality issues, or a needs_correction/rejected review status) "
        "so the admin does not have to inspect every page.",
        ("document_public_id",),
        _tool_list_critical_document_pages,
    ),
    ToolDefinition(
        "get_document_cleanup_summary",
        "data",
        "Repeated header/footer/page-number cleanup suggestions detected for one document, "
        "grouped by element type.",
        ("document_public_id",),
        _tool_get_document_cleanup_summary,
    ),
    ToolDefinition(
        "get_document_tamil_quality_summary",
        "data",
        "Tamil Unicode/OCR quality issue counts for one document, by issue type, review "
        "status, and correction risk.",
        ("document_public_id",),
        _tool_get_document_tamil_quality_summary,
    ),
    ToolDefinition(
        "get_document_chunk_summary",
        "data",
        "Semantic chunk coverage report for one document.",
        ("document_public_id",),
        _tool_get_document_chunk_summary,
    ),
    ToolDefinition(
        "get_document_sft_candidate_summary",
        "data",
        "SFT candidate counts for one document, by task type and quality/review status.",
        ("document_public_id",),
        _tool_get_document_sft_candidate_summary,
    ),
    ToolDefinition(
        "get_document_training_readiness",
        "data",
        "Whether one document's approved SFT candidates are ready to export, and what is "
        "still blocking export if not.",
        ("document_public_id",),
        _tool_get_document_training_readiness,
    ),
    ToolDefinition(
        "get_document_sft_handoff_summary",
        "data",
        "Whether an SFT export for this document has been handed off into the dataset "
        "system yet, and the handoff record's status.",
        ("document_public_id",),
        _tool_get_document_sft_handoff_summary,
    ),
    ToolDefinition(
        "get_document_sft_generator_eligibility",
        "data",
        "Approved chunk counts by chunk type for one document -- the real signal for which "
        "SFT generators have eligible input.",
        ("document_public_id",),
        _tool_get_document_sft_generator_eligibility,
    ),
    ToolDefinition(
        "get_document_cleanup_detector_summary",
        "data",
        "Repeated-element cleanup detection counts by element type for one document.",
        ("document_public_id",),
        _tool_get_document_cleanup_detector_summary,
    ),
    ToolDefinition(
        "get_document_tamil_correction_summary",
        "data",
        "Tamil correction-rule registry counts by lifecycle status (draft/needs_review/"
        "approved/active/rejected).",
        (),
        _tool_get_document_tamil_correction_summary,
    ),
    ToolDefinition(
        "get_document_media_content_summary",
        "data",
        "Page content-type classification counts for one document (text_only, "
        "image_with_caption, table, vision_required, ...).",
        ("document_public_id",),
        _tool_get_document_media_content_summary,
    ),
    ToolDefinition(
        "get_document_security_review_summary",
        "data",
        "Prompt-injection/PII security finding counts for one document, by type and action.",
        ("document_public_id",),
        _tool_get_document_security_review_summary,
    ),
    ToolDefinition(
        "get_document_pii_review_summary",
        "data",
        "PII-specific finding counts and pending-review count for one document.",
        ("document_public_id",),
        _tool_get_document_pii_review_summary,
    ),
    ToolDefinition(
        "get_document_dataset_version_status",
        "data",
        "The dataset-version/build status resulting from this document's SFT handoff, if any.",
        ("document_public_id",),
        _tool_get_document_dataset_version_status,
    ),
)

TOOL_BY_NAME: dict[str, ToolDefinition] = {tool.name: tool for tool in READ_ONLY_TOOLS}


def get_tool(name: str) -> ToolDefinition | None:
    return TOOL_BY_NAME.get(name)


def tools_for_mode(mode: str) -> tuple[ToolDefinition, ...]:
    return tuple(tool for tool in READ_ONLY_TOOLS if tool.mode == mode)


def run_tool(name: str, settings: Settings, params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Look up and execute a read-only tool by name, returning a
    sanitized result. Never raises anything except `ReadOnlyToolError`
    (unknown tool/bad params) or `NotFoundError`/`ValidationError` from
    the wrapped service -- callers are expected to catch those and
    record a `failed`/`denied` tool-invocation row rather than leak a
    stack trace to the admin."""

    params = params or {}
    tool = get_tool(name)
    if tool is None:
        raise ReadOnlyToolError(f"unknown read-only tool: {name}")
    for required in tool.required_params:
        if not params.get(required):
            raise ReadOnlyToolError(f"missing required parameter: {required}")
    try:
        result = tool.handler(settings, params)
    except ValidationError as exc:
        raise ReadOnlyToolError(str(exc)) from exc
    return redact_secrets(result)
