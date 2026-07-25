"""Operator CLI for Phase 18 feedback, human review, dataset
candidates, regression suites, and improvement reports.

Every command operates on public IDs only. Mutating commands require a
typed confirmation before proceeding.
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.feedback import FeedbackRepository
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.models.feedback import (
    CandidateApprovalCreate,
    CorrectedResponseCreate,
    DatasetCandidateCreate,
    FeedbackPolicyCreate,
    HumanReviewCreate,
    ImprovementReportCreate,
    RegressionRunCompareRequest,
    RegressionSuiteCreate,
    ReviewAssignmentCreate,
)
from backend.services.feedback_dataset_service import FeedbackDatasetService
from backend.services.feedback_review_service import FeedbackReviewService
from backend.services.feedback_service import FeedbackService
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService
from backend.services.regression_evaluation_service import RegressionEvaluationService

CLI_ADMIN_ID = "00000000-0000-0000-0000-0000000000fc"


def _feedback() -> FeedbackService:
    settings = get_settings()
    return FeedbackService(FeedbackRepository(settings.resolved_database_path), settings)


def _review() -> FeedbackReviewService:
    settings = get_settings()
    return FeedbackReviewService(FeedbackRepository(settings.resolved_database_path), settings)


def _dataset() -> FeedbackDatasetService:
    settings = get_settings()
    return FeedbackDatasetService(
        FeedbackRepository(settings.resolved_database_path),
        DatasetAdminRepository(settings.resolved_database_path),
        settings,
    )


def _regression() -> RegressionEvaluationService:
    settings = get_settings()
    inference_repository = InferenceRuntimeRepository(settings.resolved_database_path)
    release_repository = ModelReleaseRepository(settings.resolved_database_path)
    runtime_service = InferenceRuntimeService(inference_repository, release_repository, settings)
    assignment_service = ModelAssignmentService(
        inference_repository, release_repository, runtime_service, settings
    )
    return RegressionEvaluationService(
        FeedbackRepository(settings.resolved_database_path),
        inference_repository, assignment_service, settings,
    )


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def _confirm(prompt: str, word: str) -> bool:
    return input(f"{prompt} Type '{word}' to confirm: ").strip().lower() == word


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI feedback CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("policies")

    create_policy = subparsers.add_parser("create-policy")
    create_policy.add_argument("--name", required=True)

    subparsers.add_parser("events")

    inspect_event = subparsers.add_parser("inspect-event")
    inspect_event.add_argument("feedback_public_id")

    triage = subparsers.add_parser("triage")
    triage.add_argument("feedback_public_id")

    assign_review = subparsers.add_parser("assign-review")
    assign_review.add_argument("feedback_public_id")
    assign_review.add_argument("--queue", dest="queue_public_id", required=True)
    assign_review.add_argument("--reviewer", dest="reviewer_admin_public_id", required=True)

    review = subparsers.add_parser("review")
    review.add_argument("feedback_public_id")
    review.add_argument("--overall-score", type=int, required=True)
    review.add_argument("--verdict", required=True)

    add_correction = subparsers.add_parser("add-correction")
    add_correction.add_argument("feedback_public_id")
    add_correction.add_argument("--text", dest="corrected_response_text", required=True)
    add_correction.add_argument("--language", default="unknown")

    validate_correction = subparsers.add_parser("validate-correction")
    validate_correction.add_argument("correction_public_id")

    create_candidate = subparsers.add_parser("create-candidate")
    create_candidate.add_argument("feedback_public_id")
    create_candidate.add_argument("--prompt-text", required=True)
    create_candidate.add_argument("--correction", dest="corrected_response_public_id")

    validate_candidate = subparsers.add_parser("validate-candidate")
    validate_candidate.add_argument("candidate_public_id")

    approve_candidate = subparsers.add_parser("approve-candidate")
    approve_candidate.add_argument("candidate_public_id")

    export_candidate = subparsers.add_parser("export-candidate")
    export_candidate.add_argument("candidate_public_id")

    create_regression_suite = subparsers.add_parser("create-regression-suite")
    create_regression_suite.add_argument("--name", required=True)

    execute_regression = subparsers.add_parser("execute-regression")
    execute_regression.add_argument("run_public_id")

    compare_runs = subparsers.add_parser("compare-runs")
    compare_runs.add_argument("run_a")
    compare_runs.add_argument("run_b")

    create_report = subparsers.add_parser("create-report")
    create_report.add_argument("--policy", dest="feedback_policy_public_id")

    verify_manifest = subparsers.add_parser("verify-manifest")
    verify_manifest.add_argument("policy_public_id")

    args = parser.parse_args(argv)

    try:
        if args.command == "policies":
            _print(_feedback().list_policies())
        elif args.command == "create-policy":
            if not _confirm(f"About to create feedback policy '{args.name}'.", "create-policy"):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(_feedback().create_policy(FeedbackPolicyCreate(name=args.name), CLI_ADMIN_ID))
        elif args.command == "events":
            _print(_feedback().list_events())
        elif args.command == "inspect-event":
            event = _feedback().get_event(args.feedback_public_id)
            classifications = _feedback().get_classifications(args.feedback_public_id)
            findings = _feedback().get_findings(args.feedback_public_id)
            _print({"event": event, "classifications": classifications, "findings": findings})
        elif args.command == "triage":
            _print(_feedback().triage(args.feedback_public_id, CLI_ADMIN_ID))
        elif args.command == "assign-review":
            _print(
                _review().assign_review(
                    args.queue_public_id,
                    ReviewAssignmentCreate(
                        feedback_event_public_id=args.feedback_public_id,
                        reviewer_admin_public_id=args.reviewer_admin_public_id,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "review":
            _print(
                _review().create_review(
                    args.feedback_public_id,
                    HumanReviewCreate(overall_score=args.overall_score, verdict=args.verdict),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "add-correction":
            _print(
                _review().create_corrected_response(
                    args.feedback_public_id,
                    CorrectedResponseCreate(
                        corrected_response_text=args.corrected_response_text,
                        language=args.language,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "validate-correction":
            _print(_review().validate_corrected_response(args.correction_public_id, CLI_ADMIN_ID))
        elif args.command == "create-candidate":
            _print(
                _dataset().create_candidate(
                    args.feedback_public_id,
                    DatasetCandidateCreate(
                        prompt_text=args.prompt_text,
                        corrected_response_public_id=args.corrected_response_public_id,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "validate-candidate":
            _print(_dataset().validate_candidate(args.candidate_public_id, CLI_ADMIN_ID))
        elif args.command == "approve-candidate":
            if not _confirm(
                f"About to approve candidate {args.candidate_public_id}.", "approve"
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                _dataset().approve_candidate(
                    args.candidate_public_id, "approve", CandidateApprovalCreate(), CLI_ADMIN_ID
                )
            )
        elif args.command == "export-candidate":
            if not _confirm(
                f"About to export candidate {args.candidate_public_id} into the dataset "
                "pipeline.", "export",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(_dataset().export_candidate(args.candidate_public_id, CLI_ADMIN_ID))
        elif args.command == "create-regression-suite":
            if not _confirm(f"About to create regression suite '{args.name}'.", "create"):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(_regression().create_suite(RegressionSuiteCreate(name=args.name), CLI_ADMIN_ID))
        elif args.command == "execute-regression":
            _print(_regression().execute_run(args.run_public_id, CLI_ADMIN_ID))
        elif args.command == "compare-runs":
            _print(
                _regression().compare_runs(
                    RegressionRunCompareRequest(
                        left_run_public_id=args.run_a, right_run_public_id=args.run_b
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-report":
            _print(
                _regression().create_improvement_report(
                    ImprovementReportCreate(
                        feedback_policy_public_id=args.feedback_policy_public_id
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "verify-manifest":
            _print(_regression().verify_manifest(args.policy_public_id))
    except RepositoryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
