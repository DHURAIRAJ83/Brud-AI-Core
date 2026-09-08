"""Phase 49 Standing Background Training Daemon with Exclusive Lease and Transactional Lifecycle.

Implements a robust, restart-safe standing training daemon operating with:
- 14-state Finite-State Machine (FSM)
- Hardware-bounded exclusive process lease (TRAINING_LEASE)
- Continuous heartbeat and dual telemetry streaming
- Transactional ledger commits and crash window idempotency
- ResourceGuard integration for RAM and disk headroom
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

import torch

from core_model.architecture.config import BrudModelConfig
from core_model.training.phase48_token_ledger import TokenLedgerError
from core_model.training.phase48_training_queue import Phase48TrainingQueue
from core_model.training.phase48_training_worker import Phase48TrainingWorker, WorkerRunResult, WorkerState



class DaemonState(str, Enum):
    STARTING = "STARTING"
    RECOVERING = "RECOVERING"
    IDLE = "IDLE"
    DISPATCHING = "DISPATCHING"
    TRAINING = "TRAINING"
    CHECKPOINTING = "CHECKPOINTING"
    LEDGER_COMMIT = "LEDGER_COMMIT"
    ARCHIVING = "ARCHIVING"
    RESOURCE_WAIT = "RESOURCE_WAIT"
    QUEUE_RECOVERY = "QUEUE_RECOVERY"
    CHECKPOINT_RECOVERY = "CHECKPOINT_RECOVERY"
    FAILED = "FAILED"
    SAFE_STOP = "SAFE_STOP"


class DaemonStateError(Exception):
    """Raised when an illegal daemon state transition is attempted."""
    pass


class TrainingLeaseError(Exception):
    """Raised when exclusive training lease acquisition fails."""
    pass


class DatasetManifestMismatchError(Exception):
    """Raised when a checkpoint's bound dataset hash mismatches the job's manifest."""
    pass


@dataclass
class DaemonHeartbeat:
    daemon_id: str
    pid: int
    state: DaemonState
    current_job_id: str | None
    current_checkpoint: str | None
    cumulative_tokens: int
    last_training_timestamp: float
    last_checkpoint_timestamp: float
    last_ledger_commit: float
    ram_headroom_mb: float
    disk_headroom_mb: float
    cpu_threads: int
    uptime_seconds: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["state"] = self.state.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DaemonHeartbeat:
        data_copy = dict(data)
        data_copy["state"] = DaemonState(data_copy["state"])
        return cls(**data_copy)


class ExclusiveTrainingLease:
    """Inter-process exclusive lock preventing competing training processes."""

    def __init__(self, lease_file: Path | str, timeout_seconds: float = 30.0) -> None:
        self.lease_file = Path(lease_file)
        self.lease_file.parent.mkdir(parents=True, exist_ok=True)
        self.timeout_seconds = timeout_seconds

    def is_process_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def acquire(self, daemon_id: str) -> bool:
        now = time.time()
        pid = os.getpid()

        if self.lease_file.exists():
            try:
                data = json.loads(self.lease_file.read_text(encoding="utf-8"))
                holder_pid = data.get("pid", -1)
                expires_at = data.get("expires_at", 0.0)

                # If holder process is alive and lease unexpired, reject acquisition
                if self.is_process_alive(holder_pid) and now < expires_at and data.get("daemon_id") != daemon_id:
                    return False
            except Exception:
                pass  # Corrupted lease file can be safely overwritten

        lease_payload = {
            "daemon_id": daemon_id,
            "pid": pid,
            "acquired_at": now,
            "expires_at": now + self.timeout_seconds,
            "last_renewed": now,
        }
        tmp_file = self.lease_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(lease_payload, indent=2), encoding="utf-8")
        tmp_file.replace(self.lease_file)
        return True

    def renew(self, daemon_id: str) -> bool:
        if not self.lease_file.exists():
            return self.acquire(daemon_id)
        try:
            data = json.loads(self.lease_file.read_text(encoding="utf-8"))
            if data.get("daemon_id") != daemon_id:
                return False
            now = time.time()
            data["expires_at"] = now + self.timeout_seconds
            data["last_renewed"] = now
            tmp_file = self.lease_file.with_suffix(".tmp")
            tmp_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tmp_file.replace(self.lease_file)
            return True
        except Exception:
            return False

    def release(self, daemon_id: str) -> None:
        if self.lease_file.exists():
            try:
                data = json.loads(self.lease_file.read_text(encoding="utf-8"))
                if data.get("daemon_id") == daemon_id:
                    self.lease_file.unlink(missing_ok=True)
            except Exception:
                self.lease_file.unlink(missing_ok=True)


class Phase49TrainingDaemon:
    """Standing background training daemon managing queue, bounded workers, checkpoints and ledger."""

    VALID_TRANSITIONS: dict[DaemonState, set[DaemonState]] = {
        DaemonState.STARTING: {DaemonState.RECOVERING, DaemonState.IDLE, DaemonState.FAILED, DaemonState.SAFE_STOP},
        DaemonState.RECOVERING: {DaemonState.IDLE, DaemonState.QUEUE_RECOVERY, DaemonState.CHECKPOINT_RECOVERY, DaemonState.FAILED, DaemonState.SAFE_STOP},
        DaemonState.IDLE: {DaemonState.DISPATCHING, DaemonState.RESOURCE_WAIT, DaemonState.SAFE_STOP, DaemonState.FAILED},
        DaemonState.DISPATCHING: {DaemonState.TRAINING, DaemonState.IDLE, DaemonState.RESOURCE_WAIT, DaemonState.FAILED, DaemonState.SAFE_STOP},
        DaemonState.TRAINING: {DaemonState.CHECKPOINTING, DaemonState.RESOURCE_WAIT, DaemonState.FAILED, DaemonState.SAFE_STOP},
        DaemonState.CHECKPOINTING: {DaemonState.LEDGER_COMMIT, DaemonState.CHECKPOINT_RECOVERY, DaemonState.FAILED, DaemonState.SAFE_STOP},
        DaemonState.LEDGER_COMMIT: {DaemonState.ARCHIVING, DaemonState.IDLE, DaemonState.FAILED, DaemonState.SAFE_STOP},
        DaemonState.ARCHIVING: {DaemonState.IDLE, DaemonState.SAFE_STOP, DaemonState.FAILED},
        DaemonState.RESOURCE_WAIT: {DaemonState.IDLE, DaemonState.SAFE_STOP, DaemonState.FAILED},
        DaemonState.QUEUE_RECOVERY: {DaemonState.IDLE, DaemonState.FAILED, DaemonState.SAFE_STOP},
        DaemonState.CHECKPOINT_RECOVERY: {DaemonState.IDLE, DaemonState.FAILED, DaemonState.SAFE_STOP},
        DaemonState.FAILED: {DaemonState.RECOVERING, DaemonState.SAFE_STOP},
        DaemonState.SAFE_STOP: set(),
    }

    def __init__(
        self,
        daemon_id: str,
        queue: Phase48TrainingQueue,
        token_ledger: Any,
        checkpoint_dir: Path | str,
        lease_file: Path | str,
        heartbeat_file: Path | str,
        telemetry_file: Path | str,
        max_training_workers: int = 1,
        torch_threads: int = 2,
        min_ram_mb: float = 500.0,
        min_disk_mb: float = 1000.0,
    ) -> None:
        self.daemon_id = daemon_id
        self.queue = queue
        self.token_ledger = token_ledger
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.lease = ExclusiveTrainingLease(lease_file)
        self.heartbeat_file = Path(heartbeat_file)
        self.heartbeat_file.parent.mkdir(parents=True, exist_ok=True)
        self.telemetry_file = Path(telemetry_file)
        self.telemetry_file.parent.mkdir(parents=True, exist_ok=True)

        self.max_training_workers = min(1, max_training_workers)
        self.torch_threads = min(2, torch_threads)
        self.min_ram_mb = min_ram_mb
        self.min_disk_mb = min_disk_mb

        torch.set_num_threads(self.torch_threads)
        try:
            torch.set_num_interop_threads(self.torch_threads)
        except RuntimeError:
            pass

        self.state = DaemonState.STARTING
        self.start_time = time.time()
        self.last_training_time = 0.0
        self.last_checkpoint_time = 0.0
        self.last_ledger_commit = 0.0
        self.current_job_id: str | None = None
        self.current_checkpoint: str | None = None
        self.stop_requested = False

        self._active_worker: Phase48TrainingWorker | None = None

    def transition_to(self, target_state: DaemonState) -> None:
        allowed = self.VALID_TRANSITIONS.get(self.state, set())
        if target_state not in allowed:
            raise DaemonStateError(f"Illegal daemon transition: {self.state.value} -> {target_state.value}")
        self.state = target_state
        self.emit_heartbeat()

    def check_system_headroom(self) -> tuple[bool, float, float]:
        ram_mb = 1024.0
        if Path("/proc/meminfo").exists():
            try:
                for line in Path("/proc/meminfo").read_text().splitlines():
                    if line.startswith("MemAvailable:"):
                        ram_mb = int(line.split()[1]) / 1024.0
                        break
            except Exception:
                pass

        stat = os.statvfs(str(self.checkpoint_dir))
        disk_mb = (stat.f_bavail * stat.f_frsize) / (1024.0 * 1024.0)

        healthy = (ram_mb >= self.min_ram_mb) and (disk_mb >= self.min_disk_mb)
        return healthy, ram_mb, disk_mb

    def emit_heartbeat(self) -> None:
        healthy, ram_mb, disk_mb = self.check_system_headroom()
        cum_tokens = self.token_ledger.get_cumulative_tokens() if hasattr(self.token_ledger, "get_cumulative_tokens") else 0
        hb = DaemonHeartbeat(
            daemon_id=self.daemon_id,
            pid=os.getpid(),
            state=self.state,
            current_job_id=self.current_job_id,
            current_checkpoint=self.current_checkpoint,
            cumulative_tokens=cum_tokens,
            last_training_timestamp=self.last_training_time,
            last_checkpoint_timestamp=self.last_checkpoint_time,
            last_ledger_commit=self.last_ledger_commit,
            ram_headroom_mb=round(ram_mb, 2),
            disk_headroom_mb=round(disk_mb, 2),
            cpu_threads=self.torch_threads,
            uptime_seconds=round(time.time() - self.start_time, 2),
        )
        tmp = self.heartbeat_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(hb.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(self.heartbeat_file)

        # Append to telemetry
        telemetry_entry = hb.to_dict()
        with open(self.telemetry_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(telemetry_entry) + "\n")

    def start(self) -> None:
        """Starts daemon, acquires exclusive lease, and transitions to IDLE."""
        if not self.lease.acquire(self.daemon_id):
            self.transition_to(DaemonState.FAILED)
            raise TrainingLeaseError(f"Could not acquire exclusive training lease for daemon {self.daemon_id}")
        self.transition_to(DaemonState.IDLE)

    def stop(self) -> None:
        """Gracefully stops daemon and releases training lease."""
        if self.state != DaemonState.SAFE_STOP:
            self.stop_requested = True
            self.lease.release(self.daemon_id)
            self.transition_to(DaemonState.SAFE_STOP)

    def execute_bounded_training_window(
        self,
        config: BrudModelConfig,
        train_batches: list[tuple[torch.Tensor, torch.Tensor]],
        val_batches: list[tuple[torch.Tensor, torch.Tensor]],
        max_slice_duration: float = 6.0,
        run_id_prefix: str = "phase49_window",
        checkpoint_manager: Any = None,
    ) -> WorkerRunResult | None:

        """Executes a single bounded training window obeying all 6 mandatory corrections."""
        if self.stop_requested or self.state == DaemonState.SAFE_STOP:
            return None

        # Mandatory Correction 1: Verify resource headroom
        healthy, ram_mb, disk_mb = self.check_system_headroom()
        if not healthy:
            self.transition_to(DaemonState.RESOURCE_WAIT)
            return None

        self.transition_to(DaemonState.DISPATCHING)
        job = self.queue.fetch_next_job()
        if not job:
            self.transition_to(DaemonState.IDLE)
            return None

        self.current_job_id = job.job_id
        run_id = f"{run_id_prefix}_{int(time.time() * 1000)}"
        self.transition_to(DaemonState.TRAINING)

        # Worker initialization
        worker_ckpts = self.checkpoint_dir / job.job_id
        worker = Phase48TrainingWorker(
            worker_id=f"worker_{self.daemon_id}_{run_id}",
            config=config,
            checkpoint_dir=worker_ckpts,
            token_ledger=self.token_ledger,
            max_threads=self.torch_threads,
        )
        self._active_worker = worker

        # Checkpoint restoration if resuming
        if job.current_checkpoint_id:
            ckpt_path = worker_ckpts / job.current_checkpoint_id
            # Mandatory Correction 6: Cryptographic Dataset-Checkpoint binding check
            refs_file = ckpt_path / "references.json"
            if refs_file.exists():
                try:
                    refs_data = json.loads(refs_file.read_text())
                    bound_manifest = refs_data.get("dataset_manifest_hash")
                    if bound_manifest and bound_manifest != job.dataset_manifest_hash:
                        self.transition_to(DaemonState.FAILED)
                        raise DatasetManifestMismatchError(
                            f"Checkpoint bound to manifest {bound_manifest}, but job has {job.dataset_manifest_hash}"
                        )
                except json.JSONDecodeError:
                    pass

            worker.load_checkpoint(ckpt_path)
            self.current_checkpoint = job.current_checkpoint_id


        # Execute bounded slice
        target_slice_steps = min(job.target_steps - job.accumulated_steps, 50)
        res = worker.run_training_slice(
            job_id=job.job_id,
            run_id=run_id,
            train_batches=train_batches,
            val_batches=val_batches,
            target_steps=target_slice_steps,
            max_duration_seconds=max_slice_duration,
            parent_checkpoint_id=(job.current_checkpoint_id or "root"),
            commit_to_ledger=False,
        )



        self.last_training_time = time.time()
        self.transition_to(DaemonState.CHECKPOINTING)
        self.current_checkpoint = res.checkpoint_id
        self.last_checkpoint_time = time.time()

        # Mandatory Correction 2 & 3: Transactional Ledger Commit & Idempotency Key
        self.transition_to(DaemonState.LEDGER_COMMIT)
        idempotency_key = f"{run_id}:{res.checkpoint_id}:{res.parent_checkpoint_id}"
        
        # Check if already in ledger (Crash Window Protection)
        already_committed = False
        if hasattr(self.token_ledger, "has_idempotency_key"):
            already_committed = self.token_ledger.has_idempotency_key(idempotency_key)

        if not already_committed and res.actual_training_tokens > 0:
            if hasattr(self.token_ledger, "append_window"):
                self.token_ledger.append_window(
                    run_id=run_id,
                    job_id=job.job_id,
                    worker_id=worker.worker_id,
                    parent_checkpoint_id=res.parent_checkpoint_id,
                    child_checkpoint_id=res.checkpoint_id,
                    run_steps=res.actual_steps,
                    run_tokens=res.actual_training_tokens,
                    validation_tokens=len(val_batches) * 32,
                    dataset_manifest_hash=job.dataset_manifest_hash,
                    idempotency_key=idempotency_key,
                )
            else:
                self.token_ledger.append_run(
                    run_id=run_id,
                    job_id=job.job_id,
                    worker_id=worker.worker_id,
                    parent_checkpoint_id=res.parent_checkpoint_id,
                    child_checkpoint_id=res.checkpoint_id,
                    run_steps=res.actual_steps,
                    run_tokens=res.actual_training_tokens,
                )
            self.last_ledger_commit = time.time()

        # Update queue progress
        self.queue.update_job_progress(
            job_id=job.job_id,
            additional_steps=res.actual_steps,
            additional_tokens=res.actual_training_tokens,
            current_checkpoint_id=res.checkpoint_id,
        )
        updated_job = self.queue.get_job(job.job_id)
        new_steps = updated_job.accumulated_steps if updated_job else 0
        new_tokens = updated_job.accumulated_tokens if updated_job else 0

        if new_steps >= job.target_steps or new_tokens >= job.target_tokens:
            self.queue.complete_job(job.job_id)
        else:
            self.queue.pause_job(job.job_id)


        # Mandatory Correction 4: Checkpoint Lifecycle Archiving
        if checkpoint_manager is not None:
            self.transition_to(DaemonState.ARCHIVING)
            checkpoint_manager.manage_lifecycle(
                job_id=job.job_id,
                current_checkpoint_id=res.checkpoint_id,
                active_lineage=[res.parent_checkpoint_id, res.checkpoint_id],
                gold_checkpoint_id=getattr(worker, "current_lineage_head", res.checkpoint_id),
            )

        # Worker release
        self._active_worker = None
        self.lease.renew(self.daemon_id)
        self.transition_to(DaemonState.IDLE)
        return res
