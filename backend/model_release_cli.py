"""Operator CLI for Phase 14 model registry, release candidates, artifact
governance, and metadata-level rollback.

Every command operates on public IDs only. Mutating commands that trigger
real computation or lifecycle transitions require a typed confirmation
before proceeding.
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.models.model_release import (
    ApprovalCreate,
    ModelCardOverrides,
    ModelReleaseCandidateCreate,
    ModelReleaseComparisonCreate,
    ModelReleaseCreate,
    ModelReleaseFamilyCreate,
    RollbackApprovalCreate,
    RollbackPlanCreate,
)
from backend.services.model_release_service import ModelReleaseService

CLI_ADMIN_ID = "00000000-0000-0000-0000-0000000000f9"


def _service() -> ModelReleaseService:
    settings = get_settings()
    return ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def _confirm(prompt: str, word: str) -> bool:
    return input(f"{prompt} Type '{word}' to confirm: ").strip().lower() == word


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI model-release registry CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("families")
    create_family_parser = subparsers.add_parser("create-family")
    create_family_parser.add_argument("--name", required=True)
    create_family_parser.add_argument("--slug", required=True)

    subparsers.add_parser("candidates")
    create_candidate_parser = subparsers.add_parser("create-candidate")
    create_candidate_parser.add_argument("--family", required=True)
    create_candidate_parser.add_argument("--core-model-version", required=True)
    create_candidate_parser.add_argument("--dataset-version", default=None)
    create_candidate_parser.add_argument("--label", default=None)

    collect_parser = subparsers.add_parser("collect-artifacts")
    collect_parser.add_argument("candidate_public_id")
    verify_parser = subparsers.add_parser("verify-artifacts")
    verify_parser.add_argument("candidate_public_id")
    eligibility_parser = subparsers.add_parser("assess-eligibility")
    eligibility_parser.add_argument("candidate_public_id")
    card_parser = subparsers.add_parser("generate-model-card")
    card_parser.add_argument("candidate_public_id")
    validate_card_parser = subparsers.add_parser("validate-model-card")
    validate_card_parser.add_argument("candidate_public_id")
    manifest_parser = subparsers.add_parser("generate-manifest")
    manifest_parser.add_argument("candidate_public_id")
    verify_manifest_parser = subparsers.add_parser("verify-manifest")
    verify_manifest_parser.add_argument("candidate_public_id")

    approve_parser = subparsers.add_parser("approve")
    approve_parser.add_argument("candidate_public_id")
    approve_parser.add_argument("--role", default="release")
    approve_parser.add_argument("--decision", default="approve")
    approve_parser.add_argument("--comment", default="")

    create_release_parser = subparsers.add_parser("create-release")
    create_release_parser.add_argument("candidate_public_id")
    create_release_parser.add_argument("--version", required=True)

    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("release_a")
    compare_parser.add_argument("release_b")

    build_bundle_parser = subparsers.add_parser("build-bundle")
    build_bundle_parser.add_argument("release_public_id")
    verify_bundle_parser = subparsers.add_parser("verify-bundle")
    verify_bundle_parser.add_argument("bundle_public_id")

    create_rollback_parser = subparsers.add_parser("create-rollback")
    create_rollback_parser.add_argument("source_release")
    create_rollback_parser.add_argument("target_release")
    create_rollback_parser.add_argument("--reason", default="")
    validate_rollback_parser = subparsers.add_parser("validate-rollback")
    validate_rollback_parser.add_argument("rollback_public_id")
    approve_rollback_parser = subparsers.add_parser("approve-rollback")
    approve_rollback_parser.add_argument("rollback_public_id")
    execute_rollback_parser = subparsers.add_parser("execute-rollback")
    execute_rollback_parser.add_argument("rollback_public_id")

    args = parser.parse_args(argv)

    service = _service()
    try:
        if args.command == "families":
            _print(service.list_families())
        elif args.command == "create-family":
            _print(
                service.create_family(
                    ModelReleaseFamilyCreate(name=args.name, slug=args.slug), CLI_ADMIN_ID
                )
            )
        elif args.command == "candidates":
            _print(service.list_candidates())
        elif args.command == "create-candidate":
            _print(
                service.create_candidate(
                    ModelReleaseCandidateCreate(
                        model_release_family_public_id=args.family,
                        core_model_version_public_id=args.core_model_version,
                        dataset_version_public_id=args.dataset_version,
                        label=args.label,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "collect-artifacts":
            _print(service.collect_artifacts(args.candidate_public_id, CLI_ADMIN_ID))
        elif args.command == "verify-artifacts":
            _print(service.verify_artifacts(args.candidate_public_id, CLI_ADMIN_ID))
        elif args.command == "assess-eligibility":
            _print(service.assess_eligibility(args.candidate_public_id, CLI_ADMIN_ID))
        elif args.command == "generate-model-card":
            _print(
                service.generate_model_card(
                    args.candidate_public_id, ModelCardOverrides(), CLI_ADMIN_ID
                )
            )
        elif args.command == "validate-model-card":
            _print(service.validate_model_card(args.candidate_public_id, CLI_ADMIN_ID))
        elif args.command == "generate-manifest":
            _print(service.generate_manifest(args.candidate_public_id, CLI_ADMIN_ID))
        elif args.command == "verify-manifest":
            result = service.verify_manifest(args.candidate_public_id)
            _print(result)
            return 0 if result["matches"] else 1
        elif args.command == "approve":
            if not _confirm(
                f"About to record a {args.decision} approval for {args.candidate_public_id}.",
                "approve",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                service.submit_approval(
                    args.candidate_public_id,
                    ApprovalCreate(role=args.role, decision=args.decision, comment=args.comment),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-release":
            if not _confirm(
                f"About to create release {args.version} for {args.candidate_public_id}.",
                "release",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                service.create_release(
                    ModelReleaseCreate(
                        candidate_public_id=args.candidate_public_id, version=args.version
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "compare":
            _print(
                service.compare_releases(
                    ModelReleaseComparisonCreate(
                        left_release_public_id=args.release_a,
                        right_release_public_id=args.release_b,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "build-bundle":
            if not _confirm(
                f"About to build a release bundle for {args.release_public_id}.", "build"
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(service.build_bundle(args.release_public_id, "zip", CLI_ADMIN_ID))
        elif args.command == "verify-bundle":
            result = service.verify_bundle(args.bundle_public_id)
            _print(result)
            return 0 if result["matches"] else 1
        elif args.command == "create-rollback":
            _print(
                service.create_rollback_plan(
                    args.source_release,
                    RollbackPlanCreate(
                        target_release_public_id=args.target_release, reason=args.reason
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "validate-rollback":
            _print(service.validate_rollback_plan(args.rollback_public_id, CLI_ADMIN_ID))
        elif args.command == "approve-rollback":
            if not _confirm(
                f"About to approve rollback plan {args.rollback_public_id}.", "approve"
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                service.approve_rollback_plan(
                    args.rollback_public_id, RollbackApprovalCreate(), CLI_ADMIN_ID
                )
            )
        elif args.command == "execute-rollback":
            if not _confirm(
                f"About to execute rollback plan {args.rollback_public_id}. This changes the "
                "family's current-release pointer.",
                "execute",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(service.execute_rollback_plan(args.rollback_public_id, CLI_ADMIN_ID))
    except RepositoryError as exc:
        print(f"Model release command failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
