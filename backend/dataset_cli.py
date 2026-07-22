"""Safe Phase 6 dataset quality and versioning CLI."""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.services.dataset_quality import DatasetQualityService
from backend.services.dataset_versioning import DatasetVersioningService

CLI_ACTOR = "cli-admin"


def _services():
    settings = get_settings()
    repository = DatasetQualityRepository(settings.resolved_database_path)
    return DatasetQualityService(repository, settings), DatasetVersioningService(
        repository, settings
    )


def _confirm(prompt: str) -> None:
    value = input(f"{prompt} Type YES to continue: ")
    if value != "YES":
        raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI dataset quality and versioning CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("quality-summary")
    assess = sub.add_parser("assess-record")
    assess.add_argument("public_id")
    sub.add_parser("list-versions")
    inspect = sub.add_parser("inspect-version")
    inspect.add_argument("public_id")
    verify = sub.add_parser("verify-version")
    verify.add_argument("public_id")
    export = sub.add_parser("export-version")
    export.add_argument("public_id")
    args = parser.parse_args(argv)
    quality, versions = _services()
    try:
        if args.command == "quality-summary":
            print(json.dumps(quality.summary(), ensure_ascii=False))
        elif args.command == "assess-record":
            _confirm("Assessing writes a new immutable assessment.")
            print(json.dumps(quality.assess_record(args.public_id, CLI_ACTOR), ensure_ascii=False))
        elif args.command == "list-versions":
            print(json.dumps(versions.list_versions(1, 100), ensure_ascii=False))
        elif args.command == "inspect-version":
            print(json.dumps(versions.get_version(args.public_id), ensure_ascii=False))
        elif args.command == "verify-version":
            print(
                json.dumps(versions.verify_version(args.public_id, CLI_ACTOR), ensure_ascii=False)
            )
        elif args.command == "export-version":
            _confirm("Exporting writes files under the configured dataset export directory.")
            print(
                json.dumps(
                    versions.create_export(args.public_id, "jsonl", CLI_ACTOR), ensure_ascii=False
                )
            )
    except (RepositoryError, ValueError, OSError) as exc:
        print(f"Dataset CLI error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
