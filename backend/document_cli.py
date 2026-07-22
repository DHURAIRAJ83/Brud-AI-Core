"""Safe registered-document inspection and page reprocessing CLI."""

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.models.documents import ExtractionStrategy, ProcessRequest
from backend.services.document_service import DocumentService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI registered document utilities")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("capabilities")
    commands.add_parser("list")
    inspect_parser = commands.add_parser("inspect")
    inspect_parser.add_argument("public_id")
    reprocess = commands.add_parser("reprocess-page")
    reprocess.add_argument("public_id")
    reprocess.add_argument("page_number", type=int)
    args = parser.parse_args(argv)
    service = DocumentService(get_settings())
    try:
        if args.command == "capabilities":
            result = service.capabilities()
        elif args.command == "list":
            result = service.list(None, None, 1, 100)
        elif args.command == "inspect":
            result = service.get(args.public_id)
        else:
            if (
                input(
                    f"Reprocess page {args.page_number} of registered document "
                    f"{args.public_id}? [y/N] "
                )
                .strip()
                .lower()
                != "y"
            ):
                print("Cancelled.")
                return 1
            result = service.process(
                args.public_id,
                ProcessRequest(strategy=ExtractionStrategy.AUTO, pages=[args.page_number]),
                "local-cli",
                reprocess=True,
            )
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0
    except (RepositoryError, ValueError) as exc:
        print(f"Document command failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
