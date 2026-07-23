"""Local bounded instruction-tuning worker.

Mirrors ``training_worker.py`` exactly, but polls
``InstructionTuningService.run_one()`` instead of ``PretrainingService.run_one()``
— it only ever claims jobs linked from ``instruction_tuning_runs``, and the
base-pretraining worker can never claim these jobs (enforced by
``PretrainingService._claim``'s ``require_instruction_tuning`` guard, not by
convention). Heartbeats, leases, and fencing are handled by the composed
``PretrainingService``; this module only owns the poll loop and
graceful-shutdown wiring.
"""

from __future__ import annotations

import argparse
import signal
import time
from uuid import uuid4

from backend.core.config import get_settings
from backend.database.repositories.instruction_tuning import InstructionTuningRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.training_reliability import TrainingReliabilityRepository
from backend.services.instruction_tuning_service import InstructionTuningService

STOP = False


def _stop(_signum, _frame) -> None:
    global STOP
    STOP = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Brud AI local instruction-tuning worker")
    parser.add_argument("--once", action="store_true", help="claim at most one queued job and exit")
    parser.add_argument(
        "--poll-seconds", type=float, default=None, help="override the poll interval"
    )
    parser.add_argument("--worker-name", default=f"instruction-worker-{uuid4().hex[:12]}")
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    settings = get_settings()
    poll_seconds = (
        args.poll_seconds
        if args.poll_seconds is not None
        else settings.pretraining_worker_poll_seconds
    )
    service = InstructionTuningService(
        InstructionTuningRepository(settings.resolved_database_path),
        PretrainingRepository(settings.resolved_database_path),
        settings,
    )
    worker_id = args.worker_name
    try:
        while not STOP:
            result = service.run_one(worker_id)
            if result:
                print(result)
                if args.once:
                    return 0 if result.get("status") in {"completed", "paused", "cancelled"} else 1
            elif args.once:
                print({"status": "idle"})
                return 0
            time.sleep(poll_seconds)
    finally:
        with service.repository.transaction() as connection:
            reliability = TrainingReliabilityRepository(settings.resolved_database_path)
            if connection.execute(
                "SELECT 1 FROM worker_heartbeats WHERE worker_id=?", (worker_id,)
            ).fetchone():
                reliability.mark_stopped(connection, worker_id)
    print({"status": "stopped"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
