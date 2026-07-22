"""Safe maintenance CLI for registered dataset-import jobs."""

import argparse
import json

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.services.import_service import ImportService


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI dataset import maintenance")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list")
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("public_id")
    subparsers.add_parser("expire-old")
    args = parser.parse_args(argv)
    service = ImportService(get_settings())
    try:
        if args.command == "list":
            print(
                json.dumps(
                    service.list_jobs(
                        status=None, file_type=None, search=None, page=1, page_size=100
                    ),
                    default=str,
                )
            )
        elif args.command == "inspect":
            print(json.dumps(service.get_job(args.public_id), default=str))
        else:
            if input("Type expire to confirm: ").strip() != "expire":
                print("Expiry cancelled")
                return 1
            print(json.dumps({"expired_jobs": service.expire_old(confirm=True)}))
    except (RepositoryError, ValueError, OSError) as exc:
        print(f"Import command failed: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
