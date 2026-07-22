"""Safe tokenizer CLI for registered Phase 7 tokenizer versions."""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.services.tokenizer_registry import TokenizerService

CLI_ACTOR = "cli-admin"


def _service() -> TokenizerService:
    settings = get_settings()
    return TokenizerService(TokenizerRepository(settings.resolved_database_path), settings)


def _confirm(message: str) -> None:
    if input(f"{message} Type YES to continue: ") != "YES":
        raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI tokenizer CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    sub.add_parser("list")
    inspect = sub.add_parser("inspect")
    inspect.add_argument("public_id")
    for command in ("build-corpus", "dry-run", "train"):
        item = sub.add_parser(command)
        item.add_argument("public_id", help="tokenizer training job public ID")
    for command in ("evaluate", "verify", "activate"):
        item = sub.add_parser(command)
        item.add_argument("public_id", help="tokenizer version public ID")
    args = parser.parse_args(argv)
    service = _service()
    try:
        if args.command == "capabilities":
            print(json.dumps(service.capabilities(), ensure_ascii=False))
        elif args.command == "list":
            print(json.dumps(service.list_versions(1, 100), ensure_ascii=False))
        elif args.command == "inspect":
            print(json.dumps(service.get_version(args.public_id), ensure_ascii=False))
        elif args.command == "build-corpus":
            print(json.dumps(service.build_corpus(args.public_id, CLI_ACTOR), ensure_ascii=False))
        elif args.command == "dry-run":
            print(json.dumps(service.dry_run(args.public_id, CLI_ACTOR), ensure_ascii=False))
        elif args.command == "train":
            _confirm("Training writes tokenizer artifacts.")
            print(json.dumps(service.train(args.public_id, CLI_ACTOR), ensure_ascii=False))
        elif args.command == "evaluate":
            print(json.dumps(service.evaluate(args.public_id, CLI_ACTOR), ensure_ascii=False))
        elif args.command == "verify":
            print(json.dumps(service.verify(args.public_id, CLI_ACTOR), ensure_ascii=False))
        elif args.command == "activate":
            _confirm("Activation changes the active tokenizer assignment.")
            print(json.dumps(service.activate(args.public_id, CLI_ACTOR), ensure_ascii=False))
    except (RepositoryError, ValueError, OSError) as exc:
        print(f"Tokenizer CLI error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
