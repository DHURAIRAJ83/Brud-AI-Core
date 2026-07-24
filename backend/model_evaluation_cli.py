"""Operator CLI for Phase 13 multilingual evaluation, safety validation, and
chat-readiness assessment.

Every command operates on public IDs only. Mutating commands that trigger
real computation (bounded generation over fixtures, readiness assessment)
require a typed confirmation before proceeding.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.model_evaluation import ModelEvaluationRepository
from backend.models.model_evaluation import (
    ModelEvaluationComparisonCreate,
    ModelEvaluationFixtureSetCreate,
    ModelEvaluationRunCreate,
)
from backend.services.model_evaluation_service import ModelEvaluationService

CLI_ADMIN_ID = "00000000-0000-0000-0000-0000000000d3"


def _service() -> ModelEvaluationService:
    settings = get_settings()
    return ModelEvaluationService(
        ModelEvaluationRepository(settings.resolved_database_path), settings
    )


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def _confirm(prompt: str, word: str) -> bool:
    return input(f"{prompt} Type '{word}' to confirm: ").strip().lower() == word


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI model-evaluation CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("candidates")
    subparsers.add_parser("suites")
    inspect_suite_parser = subparsers.add_parser("inspect-suite")
    inspect_suite_parser.add_argument("suite_public_id")
    validate_suite_parser = subparsers.add_parser("validate-suite")
    validate_suite_parser.add_argument("suite_public_id")
    activate_suite_parser = subparsers.add_parser("activate-suite")
    activate_suite_parser.add_argument("suite_public_id")

    create_fixture_set_parser = subparsers.add_parser("create-fixture-set")
    create_fixture_set_parser.add_argument("suite_public_id")
    create_fixture_set_parser.add_argument(
        "--file", required=True, help="JSON file with {name, description, fixtures}"
    )
    fixture_sets_parser = subparsers.add_parser("fixture-sets")
    fixture_sets_parser.add_argument("suite_public_id")
    coverage_parser = subparsers.add_parser("fixture-set-coverage")
    coverage_parser.add_argument("fixture_set_public_id")

    create_run_parser = subparsers.add_parser("create-run")
    create_run_parser.add_argument("fixture_set_public_id")
    create_run_parser.add_argument("candidate_public_id")
    execute_run_parser = subparsers.add_parser("execute-run")
    execute_run_parser.add_argument("run_public_id")
    inspect_run_parser = subparsers.add_parser("inspect-run")
    inspect_run_parser.add_argument("run_public_id")
    subparsers.add_parser("runs")

    review_queue_parser = subparsers.add_parser("review-queue")
    review_queue_parser.add_argument("run_public_id")
    assess_readiness_parser = subparsers.add_parser("assess-readiness")
    assess_readiness_parser.add_argument("run_public_id")
    readiness_parser = subparsers.add_parser("readiness")
    readiness_parser.add_argument("run_public_id")

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("--left", required=True)
    compare_parser.add_argument("--right", required=True)

    manifest_parser = subparsers.add_parser("generate-manifest")
    manifest_parser.add_argument("run_public_id")
    verify_parser = subparsers.add_parser("verify-manifest")
    verify_parser.add_argument("run_public_id")

    args = parser.parse_args(argv)

    service = _service()
    try:
        if args.command == "candidates":
            _print(service.eligible_candidates())
        elif args.command == "suites":
            _print(service.list_suites())
        elif args.command == "inspect-suite":
            _print(service.get_suite(args.suite_public_id))
        elif args.command == "validate-suite":
            _print(service.validate_suite(args.suite_public_id, CLI_ADMIN_ID))
        elif args.command == "activate-suite":
            if not _confirm(f"About to activate suite {args.suite_public_id}.", "activate"):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(service.activate_suite(args.suite_public_id, CLI_ADMIN_ID))
        elif args.command == "create-fixture-set":
            payload_dict = json.loads(Path(args.file).read_text(encoding="utf-8"))
            payload = ModelEvaluationFixtureSetCreate(**payload_dict)
            _print(service.create_fixture_set(args.suite_public_id, payload, CLI_ADMIN_ID))
        elif args.command == "fixture-sets":
            _print(service.list_fixture_sets(args.suite_public_id))
        elif args.command == "fixture-set-coverage":
            _print(service.fixture_set_coverage(args.fixture_set_public_id))
        elif args.command == "create-run":
            payload = ModelEvaluationRunCreate(
                model_evaluation_fixture_set_public_id=args.fixture_set_public_id,
                candidate_core_model_version_public_id=args.candidate_public_id,
            )
            _print(service.create_run(payload, CLI_ADMIN_ID))
        elif args.command == "execute-run":
            if not _confirm(f"About to execute evaluation run {args.run_public_id}.", "execute"):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(service.execute_run(args.run_public_id, CLI_ADMIN_ID))
        elif args.command == "inspect-run":
            _print(service.get_run(args.run_public_id))
        elif args.command == "runs":
            _print(service.list_runs())
        elif args.command == "review-queue":
            _print(service.review_queue(args.run_public_id))
        elif args.command == "assess-readiness":
            _print(service.assess_readiness(args.run_public_id, CLI_ADMIN_ID))
        elif args.command == "readiness":
            _print(service.latest_readiness(args.run_public_id))
        elif args.command == "compare":
            payload = ModelEvaluationComparisonCreate(
                left_run_public_id=args.left, right_run_public_id=args.right
            )
            _print(service.compare_runs(payload, CLI_ADMIN_ID))
        elif args.command == "generate-manifest":
            _print(service.generate_manifest(args.run_public_id, CLI_ADMIN_ID))
        elif args.command == "verify-manifest":
            result = service.verify_manifest(args.run_public_id)
            _print(result)
            return 0 if result["matches"] else 1
    except RepositoryError as exc:
        print(f"Model evaluation command failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
