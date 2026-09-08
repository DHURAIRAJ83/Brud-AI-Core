"""Phase 48 Hardware-Aware Worker Pool.

Manages training worker lifecycle and job dispatching under strict hardware bounds
(max 1 training worker, 2 torch threads on the Pentium G2030 host).
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Sequence

import torch

from core_model.architecture.config import BrudModelConfig
from core_model.training.phase48_token_ledger import Phase48TokenLedger
from core_model.training.phase48_training_queue import JobStatus, Phase48TrainingQueue, TrainingJob
from core_model.training.phase48_training_worker import Phase48TrainingWorker, WorkerRunResult, WorkerState


class WorkerPoolError(Exception):
    """Raised when worker pool encounters concurrency or dispatch violations."""
    pass


class Phase48WorkerPool:
    """Hardware-aware pool enforcing safe sequential bounded worker runs."""

    def __init__(
        self,
        queue: Phase48TrainingQueue,
        ledger: Phase48TokenLedger,
        checkpoint_base_dir: Path | str,
        max_training_workers: int = 1,
        torch_threads: int = 2,
    ) -> None:
        self.queue = queue
        self.ledger = ledger
        self.checkpoint_base_dir = Path(checkpoint_base_dir)
        self.checkpoint_base_dir.mkdir(parents=True, exist_ok=True)
        self.max_training_workers = max_training_workers
        self.torch_threads = torch_threads

        # Strict hardware clamping: never exceed 1 training worker on 2-core CPU
        if self.max_training_workers > 1:
            self.max_training_workers = 1

        self.active_worker: Phase48TrainingWorker | None = None
        self.current_job_id: str | None = None

    def dispatch_next_job(
        self,
        config: BrudModelConfig,
        train_batches: Sequence[tuple[torch.Tensor, torch.Tensor]],
        val_batches: Sequence[tuple[torch.Tensor, torch.Tensor]] | None = None,
        max_slice_duration: float = 15.0,
        run_id_prefix: str = "run",
    ) -> WorkerRunResult | None:
        """Fetches the next queued job, instantiates a bounded worker, runs a training slice, and persists state."""
        job = self.queue.fetch_next_job()
        if not job:
            return None

        worker_id = f"worker_{int(time.time() * 1000)}"
        run_id = f"{run_id_prefix}_{int(time.time() * 1000)}"

        # Mark job as running
        self.queue.set_job_status(job.job_id, JobStatus.RUNNING)
        self.current_job_id = job.job_id

        # Instantiate bounded worker
        worker = Phase48TrainingWorker(
            worker_id=worker_id,
            config=config,
            checkpoint_dir=self.checkpoint_base_dir / job.job_id,
            token_ledger=self.ledger,
            max_threads=self.torch_threads,
        )
        self.active_worker = worker

        parent_ckpt_id = job.current_checkpoint_id or job.base_checkpoint_id or "root"

        # Resume from checkpoint if job already has progress
        if job.current_checkpoint_id:
            ckpt_path = self.checkpoint_base_dir / job.job_id / job.current_checkpoint_id
            if ckpt_path.exists():
                worker.load_checkpoint(ckpt_path)

        # Execute bounded slice
        steps_remaining = max(1, job.target_steps - job.accumulated_steps)
        run_result = worker.run_training_slice(
            job_id=job.job_id,
            run_id=run_id,
            train_batches=train_batches,
            val_batches=val_batches,
            target_steps=steps_remaining,
            max_duration_seconds=min(max_slice_duration, job.max_runtime_seconds),
            parent_checkpoint_id=parent_ckpt_id,
        )

        # Update persistent queue progress
        new_status = JobStatus.COMPLETED.value if (job.accumulated_steps + run_result.actual_steps >= job.target_steps) else JobStatus.PAUSED.value
        self.queue.update_job_progress(
            job_id=job.job_id,
            additional_steps=run_result.actual_steps,
            additional_tokens=run_result.actual_training_tokens,
            current_checkpoint_id=run_result.checkpoint_id,
            status=new_status,
        )

        # Clean worker release (Mandatory Correction 2)
        self.active_worker = None
        self.current_job_id = None
        return run_result

    def get_pool_status(self) -> dict[str, Any]:
        return {
            "max_training_workers": self.max_training_workers,
            "torch_threads": self.torch_threads,
            "is_busy": self.active_worker is not None,
            "current_job_id": self.current_job_id,
            "active_worker_id": self.active_worker.worker_id if self.active_worker else None,
            "cumulative_tokens": self.ledger.get_cumulative_tokens(),
            "queued_jobs": len(self.queue.list_jobs(status=JobStatus.QUEUED.value)),
            "paused_jobs": len(self.queue.list_jobs(status=JobStatus.PAUSED.value)),
            "completed_jobs": len(self.queue.list_jobs(status=JobStatus.COMPLETED.value)),
        }
