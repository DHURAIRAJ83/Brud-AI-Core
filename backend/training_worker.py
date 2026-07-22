"""Local bounded pretraining worker.

This is an honest worker process: it claims queued jobs from SQLite and runs at
most one job at a time in the current process. It is not a FastAPI background
task and does not claim distributed training support.
"""

from __future__ import annotations

import argparse
import signal
import time
from uuid import uuid4

from backend.core.config import get_settings
from backend.database.repositories.pretraining import PretrainingRepository
from backend.services.pretraining_service import PretrainingService

STOP = False


def _stop(_signum, _frame) -> None:
    global STOP
    STOP = True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Brud AI local pretraining worker")
    parser.add_argument("--once", action="store_true", help="claim at most one queued job and exit")
    parser.add_argument("--worker-id", default=f"worker-{uuid4().hex[:12]}")
    args = parser.parse_args(argv)

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    settings = get_settings()
    service = PretrainingService(
        PretrainingRepository(settings.resolved_database_path),
        settings,
    )
    while not STOP:
        result = service.run_one(args.worker_id)
        if result:
            print(result)
            if args.once:
                return 0 if result.get("status") in {"completed", "paused", "cancelled"} else 1
        elif args.once:
            print({"status": "idle"})
            return 0
        time.sleep(settings.pretraining_worker_poll_seconds)
    print({"status": "stopped"})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
