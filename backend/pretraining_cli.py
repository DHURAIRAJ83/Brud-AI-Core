"""CLI utilities for bounded pretraining jobs."""

from __future__ import annotations

import argparse

from backend.core.config import get_settings
from backend.database.repositories.pretraining import PretrainingRepository
from backend.services.pretraining_service import PretrainingService


def _service() -> PretrainingService:
    settings = get_settings()
    return PretrainingService(PretrainingRepository(settings.resolved_database_path), settings)


def _confirm(prompt: str) -> None:
    value = input(f"{prompt} Type YES to continue: ")
    if value != "YES":
        raise SystemExit(2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI pretraining utilities")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("capabilities")
    sub.add_parser("list")
    for name in (
        "inspect",
        "preflight",
        "queue",
        "pause",
        "resume",
        "cancel",
        "metrics",
        "list-checkpoints",
    ):
        item = sub.add_parser(name)
        item.add_argument("public_id")
    verify = sub.add_parser("verify-checkpoint")
    verify.add_argument("public_id")
    promote = sub.add_parser("promote")
    promote.add_argument("public_id")
    args = parser.parse_args(argv)

    service = _service()
    if args.command == "capabilities":
        print(service.capabilities())
    elif args.command == "list":
        print(service.list_jobs(1, 25))
    elif args.command == "inspect":
        print(service.get_job(args.public_id))
    elif args.command == "preflight":
        print(service.validate_job(args.public_id, "cli"))
    elif args.command == "queue":
        _confirm("Queue this pretraining job?")
        print(service.queue_job(args.public_id, "cli"))
    elif args.command == "pause":
        _confirm("Request pause for this pretraining job?")
        print(service.pause(args.public_id, "cli"))
    elif args.command == "resume":
        _confirm("Resume this pretraining job?")
        print(service.resume(args.public_id, "cli"))
    elif args.command == "cancel":
        _confirm("Cancel this pretraining job?")
        print(service.cancel(args.public_id, "cli"))
    elif args.command == "metrics":
        print(service.metrics(args.public_id))
    elif args.command == "list-checkpoints":
        print(service.checkpoints(args.public_id))
    elif args.command == "verify-checkpoint":
        print(service.verify_checkpoint(args.public_id, "cli"))
    elif args.command == "promote":
        _confirm("Promote this checkpoint to a base-pretrained staging model?")
        print(service.promote(args.public_id, "cli"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
