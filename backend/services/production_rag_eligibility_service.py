"""Phase 15 Step 3: production RAG eligibility gate.

Read-only over Phase 11 (rights/permissions), Phase 12 (sample
lineage), and Phase 13 (RAG sandbox report/evaluations/acceptance) --
never writes anything. A `production_rag_promotion_requests` row may
only ever be created once this gate passes (enforced by
`ProductionRagPromotionService`, not here -- this service only
measures and explains). See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

from typing import Any

from backend.core.config import Settings
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository

_ACCEPTED_DECISIONS = ("accepted", "accepted_with_conditions")
_DENIED_PERMISSION_STATUSES = ("not_approved", "prohibited")
_UNSUPPORTED_CLAIM_RATE_THRESHOLD = 0.2


class ProductionRagEligibilityService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._verification = DatasetVerificationRepository(settings.resolved_database_path)

    def check_eligibility(
        self, rag_sandbox_experiment_public_id: str, *, commercial_use_context: str = "unknown"
    ) -> dict[str, Any]:
        blocking: list[str] = []
        warnings: list[str] = []

        experiment = self._sandbox.get_experiment(rag_sandbox_experiment_public_id)
        acceptance = self._sandbox.get_latest_acceptance(rag_sandbox_experiment_public_id)
        if acceptance is None or acceptance["decision"] not in _ACCEPTED_DECISIONS:
            blocking.append(
                "RAG sandbox experiment has no accepted/accepted_with_conditions acceptance"
            )
        report = self._sandbox.get_latest_report(rag_sandbox_experiment_public_id)
        if report is None:
            blocking.append("no finalized RAG sandbox report exists")
        elif report["production_rag_readiness"] not in (
            "potentially_ready", "ready_with_conditions",
        ):
            blocking.append(
                f"report production_rag_readiness is '{report['production_rag_readiness']}'"
            )
        if not experiment.get("eligible_for_production_rag_proposal"):
            blocking.append("experiment is not marked eligible_for_production_rag_proposal")
        if not experiment.get("accepted_record_checksum_set_hash"):
            blocking.append("no accepted-record checksum set is recorded for this experiment")

        case = self._verification.get_case(experiment["verification_case_public_id"])
        if case["verification_expiry_status"] in ("expired", "source_changed", "withdrawn"):
            blocking.append(f"source verification status is '{case['verification_expiry_status']}'")
        rag_permission = self._verification.get_permission_assessment(case["public_id"], "rag_use")
        if rag_permission is None or rag_permission["status"] in _DENIED_PERMISSION_STATUSES:
            blocking.append("RAG use permission is not approved")
        elif rag_permission["status"] == "approved_with_conditions":
            warnings.append("RAG use permission is approved_with_conditions")

        if commercial_use_context == "commercial":
            commercial_permission = self._verification.get_permission_assessment(
                case["public_id"], "commercial_use"
            )
            if commercial_permission is None or commercial_permission["status"] in (
                "unknown", *_DENIED_PERMISSION_STATUSES,
            ):
                blocking.append(
                    "commercial use context requires an approved commercial_use permission -- "
                    "unknown commercial status never silently passes"
                )

        injection_evaluations = self._sandbox.list_evaluations(
            rag_sandbox_experiment_public_id, evaluation_type="prompt_injection"
        )
        if any(item["result_status"] == "failed" for item in injection_evaluations):
            blocking.append("an unresolved successful prompt-injection finding exists")

        conflict_evaluations = self._sandbox.list_evaluations(
            rag_sandbox_experiment_public_id, evaluation_type="conflict_handling"
        )
        if any(item["result_status"] == "conflict_missed" for item in conflict_evaluations):
            blocking.append("an unresolved high-severity conflict-handling failure exists")

        claim_evaluations = self._sandbox.list_evaluations(
            rag_sandbox_experiment_public_id, evaluation_type="unsupported_claim"
        )
        if claim_evaluations:
            unsupported_count = sum(
                1 for item in claim_evaluations if item["result_status"] == "unsupported"
            )
            rate = unsupported_count / len(claim_evaluations)
            if rate > _UNSUPPORTED_CLAIM_RATE_THRESHOLD:
                blocking.append(
                    f"unsupported-claim rate {rate:.2f} exceeds policy threshold "
                    f"{_UNSUPPORTED_CLAIM_RATE_THRESHOLD}"
                )
            elif unsupported_count:
                warnings.append(f"{unsupported_count} unsupported-claim finding(s) present")
        else:
            warnings.append("no unsupported-claim evaluations were recorded for this experiment")

        return {
            "eligible": not blocking,
            "blocking_reasons": blocking,
            "warnings": warnings,
            "rag_sandbox_experiment_public_id": rag_sandbox_experiment_public_id,
            "accepted_record_checksum_set_hash": experiment.get(
                "accepted_record_checksum_set_hash"
            ),
            "report_checksum_sha256": report["report_checksum_sha256"] if report else None,
            "report_public_id": report["public_id"] if report else None,
        }


__all__ = ["ProductionRagEligibilityService"]
