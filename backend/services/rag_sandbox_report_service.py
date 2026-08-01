"""Phase 13 Step 21/23 threshold policy and immutable experiment
report.

`finalize()` recomputes every metric fresh from the live tables --
never trusting a cached rollup -- and refuses while any tested query
(one with an answer run) has no human review at all. Neither
`production_rag_readiness` nor `training_data_observation` is ever an
approval; both are advisory strings consumed only by a human Admin's
separate acceptance decision (Step 24) or by Phase 14's own gates. See
docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.services.rag_sandbox_eligibility_service import RagSandboxError
from core_model.rag_sandbox import DEFAULT_THRESHOLDS, EVALUATION_VERSION, THRESHOLD_VERSION

logger = logging.getLogger(__name__)

# Failing either of these two dimensions always blocks production-RAG
# readiness outright -- no amount of otherwise-good metrics offsets an
# injection failure or an unresolved source conflict.
_HARD_BLOCK_DIMENSIONS = {"maximum_injection_failure_count", "maximum_unresolved_conflict_failures"}


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
                event_type=f"rag_sandbox_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="rag_sandbox_experiment",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("rag_sandbox_audit_write_failed", extra={"action": action})


def _rate(numerator: int, denominator: int) -> float | None:
    return (numerator / denominator) if denominator else None


class RagSandboxReportService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _check_human_review_coverage(self, experiment_public_id: str) -> None:
        answer_runs = self._sandbox.list_answer_runs(experiment_public_id)
        reviews = self._sandbox.list_human_reviews(experiment_public_id)
        reviewed_query_ids = {review["query_public_id"] for review in reviews}
        answered_query_ids = {run["query_public_id"] for run in answer_runs}
        unreviewed = answered_query_ids - reviewed_query_ids
        if unreviewed:
            raise RagSandboxError(
                f"{len(unreviewed)} tested quer{'y' if len(unreviewed) == 1 else 'ies'} "
                "have no human review yet -- review every tested query before finalizing "
                "the report"
            )

    def _threshold_evaluation(
        self, metrics: dict[str, float | int | None]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        rows: list[dict[str, Any]] = []
        blocking_reasons: list[str] = []
        for dimension, threshold_value in DEFAULT_THRESHOLDS.items():
            actual = metrics.get(dimension)
            if actual is None:
                rows.append(
                    {"dimension": dimension, "threshold": threshold_value, "actual": None,
                     "passed": None}
                )
                continue
            is_maximum = dimension.startswith("maximum_")
            passed = actual <= threshold_value if is_maximum else actual >= threshold_value
            rows.append(
                {"dimension": dimension, "threshold": threshold_value, "actual": actual,
                 "passed": passed}
            )
            if not passed and dimension in _HARD_BLOCK_DIMENSIONS:
                blocking_reasons.append(
                    f"{dimension} exceeded: {actual} > {threshold_value}"
                )
        return rows, blocking_reasons

    def finalize(self, experiment_public_id: str, *, admin_id: str) -> dict[str, Any]:
        experiment = self._sandbox.get_experiment(experiment_public_id)
        self._check_human_review_coverage(experiment_public_id)

        corpus = self._sandbox.get_corpus_for_experiment(experiment_public_id)
        records = self._sandbox.list_records(experiment_public_id, limit=100, offset=0)
        indexes = self._sandbox.list_indexes(experiment_public_id)
        query_sets = self._sandbox.list_query_sets(experiment_public_id)
        retrieval_runs = self._sandbox.list_retrieval_runs(experiment_public_id)
        answer_runs = self._sandbox.list_answer_runs(experiment_public_id)
        citations = self._sandbox.list_citations_for_experiment(experiment_public_id)
        evaluations = self._sandbox.list_evaluations(experiment_public_id)
        human_reviews = self._sandbox.list_human_reviews(experiment_public_id)
        approval = self._sandbox.get_latest_approval(experiment_public_id)

        all_retrieval_results = []
        for run in retrieval_runs:
            all_retrieval_results.extend(self._sandbox.list_retrieval_results(run["public_id"]))

        full_metric_results = [
            row for row in all_retrieval_results if row["metric_availability"] == "full"
        ]
        expected_source_hit_rate = _rate(
            sum(1 for row in full_metric_results if row["expected_source_hit"]),
            len(full_metric_results),
        )
        valid_citations = sum(
            1 for c in citations if c["validation_status"] in ("valid", "partially_supporting")
        )
        citation_validity_rate = _rate(valid_citations, len(citations))
        unsupported_evaluations = [
            row for row in evaluations if row["evaluation_type"] == "unsupported_claim"
        ]
        hallucination_rate = _rate(
            sum(1 for row in unsupported_evaluations if row["result_status"] == "unsupported"),
            len(unsupported_evaluations),
        )
        language_evaluations = [
            row for row in evaluations if row["evaluation_type"] == "language_compliance"
        ]
        language_compliance_rate = _rate(
            sum(1 for row in language_evaluations if row["result_status"] == "respected"),
            len(language_evaluations),
        )
        injection_evaluations = [
            row for row in evaluations if row["evaluation_type"] == "prompt_injection"
        ]
        injection_failure_count = sum(
            1 for row in injection_evaluations if row["result_status"] == "failed"
        )
        conflict_evaluations = [
            row for row in evaluations if row["evaluation_type"] == "conflict_handling"
        ]
        unresolved_conflict_failures = sum(
            1
            for row in conflict_evaluations
            if row["result_status"] in ("silent_resolution", "conflict_missed")
        )
        latencies = [
            run["latency_milliseconds"] for run in answer_runs if run["latency_milliseconds"]
        ]
        average_latency_ms = (sum(latencies) / len(latencies)) if latencies else None

        metrics = {
            "minimum_expected_source_hit_rate": expected_source_hit_rate,
            "minimum_citation_validity_rate": citation_validity_rate,
            "maximum_unsupported_claim_rate": hallucination_rate,
            "maximum_hallucination_rate": hallucination_rate,
            "minimum_language_compliance_rate": language_compliance_rate,
            "maximum_injection_failure_count": injection_failure_count,
            "maximum_unresolved_conflict_failures": unresolved_conflict_failures,
            "maximum_average_latency_ms": average_latency_ms,
        }
        threshold_rows, blocking_reasons = self._threshold_evaluation(metrics)

        failed_dimensions = [row["dimension"] for row in threshold_rows if row["passed"] is False]
        if blocking_reasons:
            production_rag_readiness = "blocked"
        elif not failed_dimensions:
            production_rag_readiness = "potentially_ready"
        elif len(failed_dimensions) <= 2:
            production_rag_readiness = "ready_with_conditions"
        else:
            production_rag_readiness = "not_ready"

        contamination_present = any(record["contamination_flagged"] for record in records)
        if contamination_present:
            training_data_observation = "needs_transformation"
        elif production_rag_readiness == "blocked":
            training_data_observation = "not_suitable"
        elif production_rag_readiness == "potentially_ready":
            training_data_observation = "potentially_useful"
        else:
            training_data_observation = "not_assessed"

        failed_queries = [
            {
                "query_public_id": run["query_public_id"],
                "status": run["status"],
            }
            for run in answer_runs
            if run["status"] in ("generation_failed", "retrieval_failed", "blocked_evidence")
        ]

        report_body = {
            "experiment_code": experiment["experiment_code"],
            "purpose": experiment["purpose"],
            "sample_import_public_id": experiment["sample_import_public_id"],
            "sample_report_public_id": experiment["sample_report_public_id"],
            "verification_case_public_id": experiment["verification_case_public_id"],
            "approval_scope": {
                "approval_public_id": approval["public_id"] if approval else None,
                "purpose": approval["purpose"] if approval else None,
                "maximum_records": approval["maximum_records"] if approval else None,
            },
            "selected_records": {
                "count": len(records),
                "contamination_flagged_count": sum(
                    1 for record in records if record["contamination_flagged"]
                ),
            },
            "chunking_configuration": [index["build_config"] for index in indexes],
            "index_configuration": [
                {"public_id": index["public_id"], "index_kind": index["index_kind"],
                 "status": index["status"], "chunk_count": index["chunk_count"]}
                for index in indexes
            ],
            "query_set_summary": {
                "query_set_count": len(query_sets),
                "finalized_count": sum(1 for qs in query_sets if qs["status"] == "finalized"),
                "query_count": sum(qs["query_count"] for qs in query_sets),
            },
            "retrieval_metrics": {
                "expected_source_hit_rate": expected_source_hit_rate,
                "result_count": len(all_retrieval_results),
                "metric_available_count": len(full_metric_results),
            },
            "answer_metrics": {
                "answer_run_count": len(answer_runs),
                "grounded_answer_count": sum(
                    1 for run in answer_runs if run["status"] == "grounded_answer"
                ),
                "insufficient_evidence_count": sum(
                    1 for run in answer_runs if run["status"] == "insufficient_evidence"
                ),
                "average_latency_milliseconds": average_latency_ms,
            },
            "citation_metrics": {
                "citation_count": len(citations),
                "citation_validity_rate": citation_validity_rate,
            },
            "language_metrics": {
                "language_compliance_rate": language_compliance_rate,
                "evaluated_count": len(language_evaluations),
            },
            "insufficient_evidence_results": [
                row for row in evaluations if row["evaluation_type"] == "insufficient_evidence"
            ],
            "conflict_handling_results": conflict_evaluations,
            "injection_resistance_results": injection_evaluations,
            "human_review_summary": {
                "review_count": len(human_reviews),
                "pass_count": sum(1 for row in human_reviews if row["decision"] == "pass"),
                "fail_count": sum(1 for row in human_reviews if row["decision"] == "fail"),
            },
            "failed_queries": failed_queries,
            "conditions": approval["conditions"] if approval else {},
            "blocking_reasons": blocking_reasons,
            "threshold_evaluation": threshold_rows,
            "resource_usage": {
                "chunk_count": sum(index["chunk_count"] for index in indexes),
                "record_count": corpus["record_count"] if corpus else 0,
            },
            "production_rag_readiness": production_rag_readiness,
            "training_data_observation": training_data_observation,
            "threshold_version": THRESHOLD_VERSION,
            "evaluation_version": EVALUATION_VERSION,
        }
        recommended_next_action = (
            "resolve blocking issues before any further use"
            if blocking_reasons
            else "proceed to Admin acceptance review"
        )
        report_body["recommended_next_action"] = recommended_next_action

        report_checksum = hashlib.sha256(dumps_json(report_body).encode("utf-8")).hexdigest()
        report = self._sandbox.add_report(
            experiment_public_id,
            {
                "report": report_body,
                "report_checksum_sha256": report_checksum,
                "production_rag_readiness": production_rag_readiness,
                "training_data_observation": training_data_observation,
                "recommended_next_action": recommended_next_action,
                "finalized_by_admin_public_id": admin_id,
            },
        )

        self._sandbox.update_experiment(
            experiment_public_id,
            {
                "status": "needs_review",
                "current_stage": "final_report",
                "production_rag_readiness": production_rag_readiness,
                "training_data_observation": training_data_observation,
                "eligible_for_production_rag_proposal": int(
                    production_rag_readiness in ("potentially_ready", "ready_with_conditions")
                ),
                "eligible_for_training_assessment": int(
                    training_data_observation in ("potentially_useful", "needs_transformation")
                ),
            },
        )
        self._sandbox.record_event(
            experiment_public_id,
            {
                "event_type": "report_finalized",
                "summary": f"report v{report['report_version']} finalized",
                "metadata": {
                    "production_rag_readiness": production_rag_readiness,
                    "training_data_observation": training_data_observation,
                },
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="finalize_report",
            actor_reference=admin_id,
            resource_public_id=report["public_id"],
            outcome=AuditOutcome.SUCCESS,
            metadata={"production_rag_readiness": production_rag_readiness},
        )
        return report


__all__ = ["RagSandboxReportService"]
