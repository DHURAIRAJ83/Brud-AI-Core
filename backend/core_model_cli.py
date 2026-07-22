"""Safe Core Model CLI for Phase 8 registered public IDs."""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.core_models import CoreModelRepository
from backend.services.core_model_service import CoreModelService

CLI_ACTOR = "cli-admin"


def _service() -> CoreModelService:
    settings = get_settings()
    return CoreModelService(CoreModelRepository(settings.resolved_database_path), settings)


def _confirm(message: str) -> None:
    if input(f"{message} Type YES to continue: ") != "YES":
        raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI Core Model CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    sub.add_parser("list-configs")
    inspect_config = sub.add_parser("inspect-config")
    inspect_config.add_argument("public_id")
    estimate = sub.add_parser("estimate-config")
    estimate.add_argument("public_id")
    sub.add_parser("list-versions")
    inspect_version = sub.add_parser("inspect-version")
    inspect_version.add_argument("public_id")
    for command in ("initialize", "verify", "smoke-test"):
        item = sub.add_parser(command)
        item.add_argument("public_id")
    checkpoint = sub.add_parser("verify-checkpoint")
    checkpoint.add_argument("public_id")
    args = parser.parse_args(argv)
    service = _service()
    try:
        if args.command == "capabilities":
            print(json.dumps(service.capabilities(), ensure_ascii=False))
        elif args.command == "list-configs":
            print(json.dumps(service.list_configs(1, 100), ensure_ascii=False))
        elif args.command == "inspect-config":
            print(json.dumps(service.get_config(args.public_id), ensure_ascii=False))
        elif args.command == "estimate-config":
            print(json.dumps(service.get_config(args.public_id), ensure_ascii=False))
        elif args.command == "list-versions":
            print(json.dumps(service.list_versions(1, 100), ensure_ascii=False))
        elif args.command == "inspect-version":
            print(json.dumps(service.get_version(args.public_id), ensure_ascii=False))
        elif args.command == "initialize":
            _confirm("Initialization writes random-weight checkpoint artifacts.")
            print(json.dumps(service.initialize(args.public_id, CLI_ACTOR), ensure_ascii=False))
        elif args.command == "verify":
            print(
                json.dumps(
                    service.verify_architecture(args.public_id, CLI_ACTOR),
                    ensure_ascii=False,
                )
            )
        elif args.command == "smoke-test":
            _confirm("Smoke test performs bounded local optimization.")
            print(json.dumps(service.smoke_test(args.public_id, CLI_ACTOR), ensure_ascii=False))
        elif args.command == "verify-checkpoint":
            print(
                json.dumps(
                    service.verify_checkpoint(args.public_id, CLI_ACTOR),
                    ensure_ascii=False,
                )
            )
    except (RepositoryError, ValueError, OSError) as exc:
        print(f"Core Model CLI error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
