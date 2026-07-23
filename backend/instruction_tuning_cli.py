"""Operator CLI for Phase 12 instruction-tuning experiments.

Every command operates on public IDs only. Mutating commands that trigger
real computation (training runs, candidate selection) require a typed
confirmation before proceeding.
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.instruction_tuning import InstructionTuningRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.models.instruction_tuning import InstructionTuningRunCreate
from backend.services.instruction_tuning_service import InstructionTuningService

CLI_ADMIN_ID = "00000000-0000-0000-0000-0000000000c2"


def _service() -> InstructionTuningService:
    settings = get_settings()
    return InstructionTuningService(
        InstructionTuningRepository(settings.resolved_database_path),
        PretrainingRepository(settings.resolved_database_path),
        settings,
    )


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def _confirm(prompt: str, word: str) -> bool:
    return input(f"{prompt} Type '{word}' to confirm: ").strip().lower() == word


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI instruction-tuning experiment CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("experiment_public_id")
    profile_parser = subparsers.add_parser("profile")
    profile_parser.add_argument("experiment_public_id")
    validate_template_parser = subparsers.add_parser("validate-template")
    validate_template_parser.add_argument("template_public_id")
    create_run_parser = subparsers.add_parser("create-run")
    create_run_parser.add_argument("experiment_public_id")
    create_run_parser.add_argument("--label", default="CLI run")
    evaluate_run_parser = subparsers.add_parser("evaluate-run")
    evaluate_run_parser.add_argument("run_public_id")
    diagnostic_parser = subparsers.add_parser("diagnostic-generate")
    diagnostic_parser.add_argument("run_public_id")
    diagnostic_parser.add_argument("--prompt", required=True)
    diagnostic_parser.add_argument("--max-new-tokens", type=int, default=32)
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("experiment_public_id")
    compare_parser.add_argument("--left")
    compare_parser.add_argument("--right")
    select_parser = subparsers.add_parser("select-candidate")
    select_parser.add_argument("experiment_public_id")
    verify_parser = subparsers.add_parser("verify-manifest")
    verify_parser.add_argument("experiment_public_id")
    args = parser.parse_args(argv)

    service = _service()
    try:
        if args.command == "list":
            _print(service.list_experiments(1, 100))
        elif args.command == "inspect":
            _print(service.get_experiment(args.experiment_public_id))
        elif args.command == "profile":
            _print(service.generate_profile(args.experiment_public_id, CLI_ADMIN_ID))
        elif args.command == "validate-template":
            _print(service.validate_template(args.template_public_id, CLI_ADMIN_ID))
        elif args.command == "create-run":
            if not _confirm(f"About to create a run for {args.experiment_public_id}.", "create"):
                print("Cancelled.", file=sys.stderr)
                return 1
            payload = InstructionTuningRunCreate(run_label=args.label)
            _print(service.create_run(args.experiment_public_id, payload, CLI_ADMIN_ID))
        elif args.command == "evaluate-run":
            _print(service.evaluate_run(args.run_public_id, CLI_ADMIN_ID))
        elif args.command == "diagnostic-generate":
            _print(
                service.diagnostic_generate(
                    args.run_public_id, args.prompt, args.max_new_tokens, CLI_ADMIN_ID
                )
            )
        elif args.command == "compare":
            if not args.left or not args.right:
                runs = service.list_runs(args.experiment_public_id)["items"]
                if len(runs) < 2:
                    print("At least two runs are required to compare.", file=sys.stderr)
                    return 1
                args.left, args.right = runs[0]["public_id"], runs[1]["public_id"]
            _print(
                service.compare_runs(
                    args.experiment_public_id, args.left, args.right, CLI_ADMIN_ID
                )
            )
        elif args.command == "select-candidate":
            if not _confirm(
                f"About to select/reject a candidate for {args.experiment_public_id}.",
                "select",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(service.select_candidate(args.experiment_public_id, None, CLI_ADMIN_ID))
        elif args.command == "verify-manifest":
            result = service.verify_manifest(args.experiment_public_id)
            _print(result)
            return 0 if result["matches"] else 1
    except RepositoryError as exc:
        print(f"Instruction tuning command failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
