"""Read-only worker heartbeat views for the admin dashboard."""

from __future__ import annotations

from typing import Any

from backend.database.repositories.training_reliability import (
    TrainingReliabilityRepository,
    public_row,
)


class PretrainingReliabilityService:
    def __init__(self, reliability: TrainingReliabilityRepository) -> None:
        self.reliability = reliability

    def workers(self) -> dict[str, Any]:
        with self.reliability.transaction() as connection:
            rows = self.reliability.list_workers(connection)
        return {"items": [public_row(row) for row in rows]}

    def worker(self, worker_public_id: str) -> dict[str, Any]:
        with self.reliability.transaction() as connection:
            row = self.reliability.worker_by_public_id(connection, worker_public_id)
        return public_row(row)
