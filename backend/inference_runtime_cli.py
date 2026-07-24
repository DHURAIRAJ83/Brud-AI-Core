"""Operator CLI for Phase 15 controlled inference runtime, model
assignment, canary activation, and safe rollback.

Every command operates on public IDs only. Mutating commands that change
runtime or assignment state require a typed confirmation before
proceeding.
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.models.inference_runtime import (
    AssignmentApprovalCreate,
    AssignmentCreate,
    CanaryStartRequest,
    DiagnosticGenerateRequest,
    RollbackPreviewRequest,
    RuntimeProfileCreate,
)
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService

CLI_ADMIN_ID = "00000000-0000-0000-0000-0000000000fa"


def _runtime_service() -> InferenceRuntimeService:
    settings = get_settings()
    return InferenceRuntimeService(
        InferenceRuntimeRepository(settings.resolved_database_path),
        ModelReleaseRepository(settings.resolved_database_path),
        settings,
    )


def _assignment_service() -> ModelAssignmentService:
    settings = get_settings()
    return ModelAssignmentService(
        InferenceRuntimeRepository(settings.resolved_database_path),
        ModelReleaseRepository(settings.resolved_database_path),
        _runtime_service(),
        settings,
    )


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def _confirm(prompt: str, word: str) -> bool:
    return input(f"{prompt} Type '{word}' to confirm: ").strip().lower() == word


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI controlled inference runtime CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("profiles")
    create_profile_parser = subparsers.add_parser("create-profile")
    create_profile_parser.add_argument("--name", required=True)
    create_profile_parser.add_argument("--maximum-context-length", type=int, required=True)
    create_profile_parser.add_argument("--maximum-new-tokens", type=int, required=True)
    create_profile_parser.add_argument(
        "--minimum-available-memory-bytes", type=int, required=True
    )
    create_profile_parser.add_argument("--minimum-available-disk-bytes", type=int, required=True)

    subparsers.add_parser("instances")
    start_instance_parser = subparsers.add_parser("start-instance")
    start_instance_parser.add_argument("instance_public_id")

    assess_release_parser = subparsers.add_parser("assess-release")
    assess_release_parser.add_argument("release_public_id")
    assess_release_parser.add_argument("--profile", required=True)

    create_assignment_parser = subparsers.add_parser("create-assignment")
    create_assignment_parser.add_argument("--scope", required=True)
    create_assignment_parser.add_argument("--release", required=True)
    create_assignment_parser.add_argument("--profile", required=True)

    validate_assignment_parser = subparsers.add_parser("validate-assignment")
    validate_assignment_parser.add_argument("assignment_public_id")

    approve_assignment_parser = subparsers.add_parser("approve-assignment")
    approve_assignment_parser.add_argument("assignment_public_id")
    approve_assignment_parser.add_argument("--role", default="release")
    approve_assignment_parser.add_argument("--decision", default="approve")
    approve_assignment_parser.add_argument("--comment", default="")

    activate_assignment_parser = subparsers.add_parser("activate-assignment")
    activate_assignment_parser.add_argument("assignment_public_id")
    activate_assignment_parser.add_argument("--confirm-public-activation", action="store_true")

    diagnostic_generate_parser = subparsers.add_parser("diagnostic-generate")
    diagnostic_generate_parser.add_argument("assignment_public_id")
    diagnostic_generate_parser.add_argument("--prompt", required=True)

    start_canary_parser = subparsers.add_parser("start-canary")
    start_canary_parser.add_argument("assignment_public_id")
    start_canary_parser.add_argument("--percentage", type=int, default=100)
    start_canary_parser.add_argument("--max-requests", type=int, default=10)

    stop_canary_parser = subparsers.add_parser("stop-canary")
    stop_canary_parser.add_argument("assignment_public_id")
    stop_canary_parser.add_argument("--reason", default="admin_stop")

    rollback_preview_parser = subparsers.add_parser("rollback-preview")
    rollback_preview_parser.add_argument("assignment_public_id")
    rollback_preview_parser.add_argument("--target-version", required=True)

    rollback_execute_parser = subparsers.add_parser("rollback-execute")
    rollback_execute_parser.add_argument("assignment_public_id")
    rollback_execute_parser.add_argument("--target-version", required=True)

    verify_manifest_parser = subparsers.add_parser("verify-manifest")
    verify_manifest_parser.add_argument("assignment_public_id")

    args = parser.parse_args(argv)

    try:
        if args.command == "profiles":
            _print(_runtime_service().list_profiles())
        elif args.command == "create-profile":
            if not _confirm("Create a new runtime profile?", "create-profile"):
                return 1
            payload = RuntimeProfileCreate(
                name=args.name,
                maximum_context_length=args.maximum_context_length,
                maximum_new_tokens=args.maximum_new_tokens,
                minimum_available_memory_bytes=args.minimum_available_memory_bytes,
                minimum_available_disk_bytes=args.minimum_available_disk_bytes,
            )
            _print(_runtime_service().create_profile(payload, CLI_ADMIN_ID))
        elif args.command == "instances":
            _print(_runtime_service().list_instances())
        elif args.command == "start-instance":
            if not _confirm(
                f"Start runtime instance {args.instance_public_id}?", "start-instance"
            ):
                return 1
            _print(_runtime_service().start_instance(args.instance_public_id, CLI_ADMIN_ID))
        elif args.command == "assess-release":
            _print(
                _runtime_service().assess_compatibility(
                    args.release_public_id, args.profile, CLI_ADMIN_ID
                )
            )
        elif args.command == "create-assignment":
            payload = AssignmentCreate(
                scope=args.scope,
                release_public_id=args.release,
                runtime_profile_public_id=args.profile,
            )
            _print(_assignment_service().create_assignment(payload, CLI_ADMIN_ID))
        elif args.command == "validate-assignment":
            _print(
                _assignment_service().validate_assignment(args.assignment_public_id, CLI_ADMIN_ID)
            )
        elif args.command == "approve-assignment":
            if not _confirm(
                f"Record a '{args.decision}' approval for {args.assignment_public_id}?",
                "approve-assignment",
            ):
                return 1
            payload = AssignmentApprovalCreate(
                role=args.role, decision=args.decision, comment=args.comment
            )
            _print(
                _assignment_service().approve_assignment(
                    args.assignment_public_id, payload, CLI_ADMIN_ID
                )
            )
        elif args.command == "activate-assignment":
            if not _confirm(
                f"Activate assignment {args.assignment_public_id}?", "activate-assignment"
            ):
                return 1
            _print(
                _assignment_service().activate_assignment(
                    args.assignment_public_id,
                    CLI_ADMIN_ID,
                    explicit_activation_confirmed=args.confirm_public_activation,
                )
            )
        elif args.command == "diagnostic-generate":
            payload = DiagnosticGenerateRequest(prompt=args.prompt)
            _print(
                _assignment_service().diagnostic_generate(
                    args.assignment_public_id, payload, CLI_ADMIN_ID
                )
            )
        elif args.command == "start-canary":
            payload = CanaryStartRequest(
                percentage=args.percentage, max_request_count=args.max_requests
            )
            _print(
                _assignment_service().start_canary(
                    args.assignment_public_id, payload, CLI_ADMIN_ID
                )
            )
        elif args.command == "stop-canary":
            if not _confirm(
                f"Stop the canary for {args.assignment_public_id}?", "stop-canary"
            ):
                return 1
            _print(
                _assignment_service().stop_canary(
                    args.assignment_public_id, args.reason, CLI_ADMIN_ID
                )
            )
        elif args.command == "rollback-preview":
            payload = RollbackPreviewRequest(target_version_public_id=args.target_version)
            _print(
                _assignment_service().rollback_preview(
                    args.assignment_public_id, payload, CLI_ADMIN_ID
                )
            )
        elif args.command == "rollback-execute":
            if not _confirm(
                f"Execute rollback for {args.assignment_public_id} to version "
                f"{args.target_version}?",
                "rollback-execute",
            ):
                return 1
            payload = RollbackPreviewRequest(target_version_public_id=args.target_version)
            _print(
                _assignment_service().rollback_execute(
                    args.assignment_public_id, payload, CLI_ADMIN_ID
                )
            )
        elif args.command == "verify-manifest":
            _print(_assignment_service().verify_manifest(args.assignment_public_id))
    except RepositoryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
