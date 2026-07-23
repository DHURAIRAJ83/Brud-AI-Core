"""Operator CLI for inspecting and recovering pretraining jobs.

Every command operates on public IDs only; there is no path or numeric-ID
argument anywhere in this tool. The only mutating command is ``recover``,
which requires an explicit typed confirmation before it touches the database.
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.migrations import migration_status
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.pretraining import PretrainingRepository, public_row
from backend.database.repositories.training_reliability import TrainingReliabilityRepository
from backend.services.pretraining_reliability_service import PretrainingReliabilityService
from backend.services.worker_recovery_service import WorkerRecoveryService


def _services():
    settings = get_settings()
    reliability = TrainingReliabilityRepository(settings.resolved_database_path)
    pretraining_repository = PretrainingRepository(settings.resolved_database_path)
    return (
        settings,
        pretraining_repository,
        reliability,
        PretrainingReliabilityService(reliability),
        WorkerRecoveryService(pretraining_repository, reliability, settings),
    )


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str))


def _status(settings) -> int:
    _print(migration_status(settings.resolved_database_path))
    return 0


def _stale_jobs(recovery: WorkerRecoveryService) -> int:
    _print(recovery.stale_jobs())
    return 0


def _inspect(
    pretraining_repository: PretrainingRepository,
    recovery: WorkerRecoveryService,
    job_public_id: str,
) -> int:
    with pretraining_repository.transaction() as connection:
        job = public_row(pretraining_repository.job(connection, job_public_id))
    verification = recovery.verify_resume(job_public_id)
    _print({"job": job, "resume_verification": verification})
    return 0


def _verify_resume(recovery: WorkerRecoveryService, job_public_id: str) -> int:
    _print(recovery.verify_resume(job_public_id))
    return 0


def _recover(
    pretraining_repository: PretrainingRepository,
    recovery: WorkerRecoveryService,
    job_public_id: str,
) -> int:
    with pretraining_repository.transaction() as connection:
        job = pretraining_repository.job(connection, job_public_id)
    recovery_type = "stale_lease" if job["recovery_required"] else "manual_resume"
    print(f"About to run '{recovery_type}' recovery for job {job_public_id}.")
    confirmation = input("Type 'recover' to confirm: ").strip().lower()
    if confirmation != "recover":
        print("Recovery cancelled.", file=sys.stderr)
        return 1
    result = recovery.recover(job_public_id, "cli-operator", recovery_type)
    _print(result)
    return 0 if result["status"] == "completed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI training recovery CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("status")
    subparsers.add_parser("stale-jobs")
    inspect_parser = subparsers.add_parser("inspect")
    inspect_parser.add_argument("job_public_id")
    recover_parser = subparsers.add_parser("recover")
    recover_parser.add_argument("job_public_id")
    verify_parser = subparsers.add_parser("verify-resume")
    verify_parser.add_argument("job_public_id")
    args = parser.parse_args(argv)

    settings, pretraining_repository, _reliability, _worker_service, recovery = _services()
    try:
        if args.command == "status":
            return _status(settings)
        if args.command == "stale-jobs":
            return _stale_jobs(recovery)
        if args.command == "inspect":
            return _inspect(pretraining_repository, recovery, args.job_public_id)
        if args.command == "verify-resume":
            return _verify_resume(recovery, args.job_public_id)
        if args.command == "recover":
            return _recover(pretraining_repository, recovery, args.job_public_id)
    except RepositoryError as exc:
        print(f"Recovery command failed: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
