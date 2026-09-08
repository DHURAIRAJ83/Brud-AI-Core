"""Phase 48 Persistent Durable Training Queue.

Provides independent, persistent, file-backed training queue storage
with zero dependency on the production database.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class TrainingJob:
    job_id: str
    tenant_id: str
    dataset_manifest_hash: str
    base_checkpoint_id: str | None = None
    target_tokens: int = 10_000
    target_steps: int = 1_000
    max_runtime_seconds: float = 30.0
    priority: int = 0
    status: str = JobStatus.QUEUED.value
    accumulated_tokens: int = 0
    accumulated_steps: int = 0
    current_checkpoint_id: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TrainingJob:
        return cls(**data)


class Phase48TrainingQueue:
    """Independent durable queue stored in a dedicated JSON file (zero production DB dependency)."""

    def __init__(self, queue_file: Path | str) -> None:
        self.queue_file = Path(queue_file)
        self.queue_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.queue_file.exists():
            self._write_jobs({})

    def _read_jobs(self) -> dict[str, dict[str, Any]]:
        if not self.queue_file.exists():
            return {}
        try:
            with open(self.queue_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_jobs(self, jobs: dict[str, dict[str, Any]]) -> None:
        temp_file = self.queue_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(jobs, f, indent=2)
        temp_file.replace(self.queue_file)

    def submit_job(
        self,
        job_id: str,
        tenant_id: str,
        dataset_manifest_hash: str,
        base_checkpoint_id: str | None = None,
        target_tokens: int = 10_000,
        target_steps: int = 1_000,
        max_runtime_seconds: float = 30.0,
        priority: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> TrainingJob:
        jobs = self._read_jobs()
        if job_id in jobs:
            raise ValueError(f"Job {job_id} already exists in queue")

        job = TrainingJob(
            job_id=job_id,
            tenant_id=tenant_id,
            dataset_manifest_hash=dataset_manifest_hash,
            base_checkpoint_id=base_checkpoint_id,
            target_tokens=target_tokens,
            target_steps=target_steps,
            max_runtime_seconds=max_runtime_seconds,
            priority=priority,
            current_checkpoint_id=base_checkpoint_id,
            metadata=metadata or {},
        )
        jobs[job_id] = job.to_dict()
        self._write_jobs(jobs)
        return job

    def get_job(self, job_id: str) -> TrainingJob | None:
        jobs = self._read_jobs()
        if job_id in jobs:
            return TrainingJob.from_dict(jobs[job_id])
        return None

    def list_jobs(
        self,
        tenant_id: str | None = None,
        status: str | None = None,
    ) -> list[TrainingJob]:
        jobs = self._read_jobs()
        result: list[TrainingJob] = []
        for d in jobs.values():
            j = TrainingJob.from_dict(d)
            if tenant_id and j.tenant_id != tenant_id:
                continue
            if status and j.status != status:
                continue
            result.append(j)
        return sorted(result, key=lambda x: (-x.priority, x.created_at))

    def fetch_next_job(self, tenant_id: str | None = None) -> TrainingJob | None:
        candidates = self.list_jobs(tenant_id=tenant_id)
        for job in candidates:
            if job.status in {JobStatus.QUEUED.value, JobStatus.PAUSED.value}:
                return job
        return None

    def update_job_progress(
        self,
        job_id: str,
        additional_steps: int,
        additional_tokens: int,
        current_checkpoint_id: str,
        status: str | None = None,
    ) -> TrainingJob:
        jobs = self._read_jobs()
        if job_id not in jobs:
            raise KeyError(f"Job {job_id} not found")
        d = jobs[job_id]
        d["accumulated_steps"] += additional_steps
        d["accumulated_tokens"] += additional_tokens
        d["current_checkpoint_id"] = current_checkpoint_id
        d["updated_at"] = time.time()
        if status:
            d["status"] = status
        jobs[job_id] = d
        self._write_jobs(jobs)
        return TrainingJob.from_dict(d)

    def set_job_status(self, job_id: str, status: JobStatus, error_message: str | None = None) -> TrainingJob:
        jobs = self._read_jobs()
        if job_id not in jobs:
            raise KeyError(f"Job {job_id} not found")
        d = jobs[job_id]
        d["status"] = status.value
        d["updated_at"] = time.time()
        if error_message:
            d["error_message"] = error_message
        jobs[job_id] = d
        self._write_jobs(jobs)
        return TrainingJob.from_dict(d)

    def pause_job(self, job_id: str) -> TrainingJob:
        return self.set_job_status(job_id, JobStatus.PAUSED)

    def resume_job(self, job_id: str) -> TrainingJob:
        return self.set_job_status(job_id, JobStatus.QUEUED)

    def cancel_job(self, job_id: str) -> TrainingJob:
        return self.set_job_status(job_id, JobStatus.CANCELLED)

    def complete_job(self, job_id: str) -> TrainingJob:
        return self.set_job_status(job_id, JobStatus.COMPLETED)

    def fail_job(self, job_id: str, error_message: str) -> TrainingJob:
        return self.set_job_status(job_id, JobStatus.FAILED, error_message=error_message)
