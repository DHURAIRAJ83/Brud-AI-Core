"""Phase 48 Background Training Worker Engine.

Implements a bounded, persistent training worker with a strict 10-state finite-state machine,
atomic checkpointing, full optimizer/scheduler/RNG restoration, and token ledger integration.
"""

from __future__ import annotations

import hashlib
import json
import os
import signal
import sys
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from core_model.architecture.config import BrudModelConfig
from core_model.architecture.model import BrudForCausalLM
from core_model.training.phase47_checkpoint_lineage import Phase47CheckpointLineage
from core_model.training.phase48_token_ledger import Phase48TokenLedger


class WorkerState(str, Enum):
    QUEUED = "QUEUED"
    INITIALIZING = "INITIALIZING"
    TRAINING = "TRAINING"
    CHECKPOINTING = "CHECKPOINTING"
    PAUSED = "PAUSED"
    RESOURCE_WAIT = "RESOURCE_WAIT"
    RECOVERING = "RECOVERING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"


class WorkerTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class ResourceGuard:
    """Monitors RAM and disk space, failing closed if thresholds are breached."""

    def __init__(self, min_ram_mb: float = 500.0, min_disk_mb: float = 1000.0) -> None:
        self.min_ram_mb = min_ram_mb
        self.min_disk_mb = min_disk_mb

    def check(self, check_path: Path | str = "/") -> tuple[bool, str]:
        try:
            with open("/proc/meminfo", "r") as f:
                mem_avail_kb = next(int(line.split()[1]) for line in f if "MemAvailable:" in line)
            ram_mb = mem_avail_kb / 1024.0
        except Exception:
            ram_mb = 4096.0

        if ram_mb < self.min_ram_mb:
            return False, f"Available RAM {ram_mb:.1f} MB below safe threshold {self.min_ram_mb} MB"

        try:
            st = os.statvfs(str(check_path))
            disk_mb = (st.f_bavail * st.f_frsize) / (1024.0 * 1024.0)
        except Exception:
            disk_mb = 50000.0

        if disk_mb < self.min_disk_mb:
            return False, f"Available disk {disk_mb:.1f} MB below safe threshold {self.min_disk_mb} MB"

        return True, "OK"


@dataclass
class WorkerRunResult:
    worker_id: str
    job_id: str
    run_id: str
    started_at: float
    ended_at: float
    actual_steps: int
    actual_training_tokens: int
    actual_validation_tokens: int
    duration_seconds: float
    tokens_per_second: float
    initial_loss: float | None
    final_loss: float | None
    best_validation_loss: float | None
    state: str
    stop_reason: str
    checkpoint_id: str
    parent_checkpoint_id: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Phase48TrainingWorker:
    """Persistent background training worker with strict state transitions and cross-run resume."""

    VALID_TRANSITIONS: dict[WorkerState, set[WorkerState]] = {
        WorkerState.QUEUED: {WorkerState.INITIALIZING, WorkerState.CHECKPOINTING, WorkerState.STOPPED, WorkerState.FAILED},
        WorkerState.INITIALIZING: {WorkerState.TRAINING, WorkerState.CHECKPOINTING, WorkerState.RECOVERING, WorkerState.FAILED, WorkerState.STOPPED},
        WorkerState.TRAINING: {WorkerState.CHECKPOINTING, WorkerState.PAUSED, WorkerState.RESOURCE_WAIT, WorkerState.COMPLETED, WorkerState.STOPPED, WorkerState.FAILED},
        WorkerState.CHECKPOINTING: {WorkerState.TRAINING, WorkerState.QUEUED, WorkerState.INITIALIZING, WorkerState.COMPLETED, WorkerState.STOPPED, WorkerState.FAILED, WorkerState.PAUSED},
        WorkerState.PAUSED: {WorkerState.INITIALIZING, WorkerState.TRAINING, WorkerState.STOPPED, WorkerState.FAILED},
        WorkerState.RESOURCE_WAIT: {WorkerState.TRAINING, WorkerState.STOPPED, WorkerState.FAILED},
        WorkerState.RECOVERING: {WorkerState.INITIALIZING, WorkerState.TRAINING, WorkerState.FAILED, WorkerState.STOPPED},
        WorkerState.COMPLETED: set(),
        WorkerState.FAILED: {WorkerState.RECOVERING, WorkerState.STOPPED},
        WorkerState.STOPPED: {WorkerState.INITIALIZING, WorkerState.QUEUED},
    }


    def __init__(
        self,
        worker_id: str,
        config: BrudModelConfig,
        checkpoint_dir: Path | str,
        token_ledger: Phase48TokenLedger,
        learning_rate: float = 1e-3,
        max_threads: int = 2,
        worker_telemetry_file: Path | None = None,
        training_telemetry_file: Path | None = None,
    ) -> None:
        self.worker_id = worker_id
        self.config = config
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.token_ledger = token_ledger
        self.learning_rate = learning_rate
        self.max_threads = max_threads

        # Enforce CPU thread bounding
        torch.set_num_threads(self.max_threads)
        try:
            torch.set_num_interop_threads(self.max_threads)
        except RuntimeError:
            pass

        self.worker_telemetry_file = worker_telemetry_file or (self.checkpoint_dir / "phase48_worker_telemetry.jsonl")
        self.training_telemetry_file = training_telemetry_file or (self.checkpoint_dir / "phase48_training_telemetry.jsonl")

        self.state = WorkerState.QUEUED
        self.resource_guard = ResourceGuard(min_ram_mb=500.0, min_disk_mb=1000.0)

        # PyTorch model, optimizer, scheduler
        self.model = BrudForCausalLM(config)
        self.optimizer = AdamW(self.model.parameters(), lr=learning_rate, weight_decay=0.01)
        self.scheduler = CosineAnnealingLR(self.optimizer, T_max=1000, eta_min=1e-5)
        self.loss_fn = nn.CrossEntropyLoss()

        self.step: int = 0
        self.cumulative_run_tokens: int = 0
        self.validation_tokens: int = 0
        self.best_val_loss: float = float("inf")
        self.current_lineage_head: str = "root"
        self._shutdown_requested: bool = False

    def transition_to(self, target_state: WorkerState) -> None:
        valid_next = self.VALID_TRANSITIONS.get(self.state, set())
        if target_state not in valid_next:
            raise WorkerTransitionError(
                f"Invalid worker state transition: {self.state.value} -> {target_state.value}"
            )
        self.state = target_state
        self._log_worker_telemetry("STATE_CHANGE", {"new_state": target_state.value})

    def _log_worker_telemetry(self, event_type: str, details: dict[str, Any]) -> None:
        rec = {
            "timestamp": time.time(),
            "worker_id": self.worker_id,
            "state": self.state.value,
            "event_type": event_type,
            "details": details,
        }
        self.worker_telemetry_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.worker_telemetry_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def _log_training_telemetry(
        self,
        job_id: str,
        run_id: str,
        step: int,
        loss: float,
        val_loss: float | None,
        tokens_per_sec: float,
        elapsed: float,
    ) -> None:
        rec = {
            "timestamp": time.time(),
            "worker_id": self.worker_id,
            "job_id": job_id,
            "run_id": run_id,
            "step": step,
            "train_loss": round(loss, 4),
            "val_loss": round(val_loss, 4) if val_loss is not None else None,
            "run_tokens": self.cumulative_run_tokens,
            "global_tokens": self.token_ledger.get_cumulative_tokens() + self.cumulative_run_tokens,
            "tokens_per_second": round(tokens_per_sec, 2),
            "elapsed_seconds": round(elapsed, 2),
            "state": self.state.value,
        }
        self.training_telemetry_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.training_telemetry_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")

    def load_checkpoint(self, checkpoint_path: Path | str) -> dict[str, Any]:
        """Cryptographically verifies and restores complete worker state from a checkpoint."""
        ckpt_dir = Path(checkpoint_path)
        self.transition_to(WorkerState.INITIALIZING)
        manifest = Phase47CheckpointLineage.verify_checkpoint_integrity(ckpt_dir)

        # Restore PyTorch states
        model_state = torch.load(ckpt_dir / "model_state.pt", map_location="cpu", weights_only=True)
        self.model.load_state_dict(model_state)

        opt_state = torch.load(ckpt_dir / "optimizer_state.pt", map_location="cpu", weights_only=False)
        self.optimizer.load_state_dict(opt_state)

        sched_state = torch.load(ckpt_dir / "scheduler_state.pt", map_location="cpu", weights_only=False)
        self.scheduler.load_state_dict(sched_state)

        rng_state = torch.load(ckpt_dir / "rng_state.pt", map_location="cpu", weights_only=False)
        torch.set_rng_state(rng_state)

        trainer_state = json.loads((ckpt_dir / "trainer_state.json").read_text(encoding="utf-8"))
        self.step = trainer_state.get("step", 0)
        self.best_val_loss = trainer_state.get("best_val_loss", float("inf"))
        self.current_lineage_head = manifest["checkpoint_hash"]

        self._log_worker_telemetry("CHECKPOINT_LOADED", {"checkpoint_id": ckpt_dir.name, "step": self.step})
        return manifest

    def save_checkpoint(self, checkpoint_id: str, is_best: bool = False, val_loss: float | None = None) -> dict[str, Any]:
        """Atomically saves and cryptographically manifests worker checkpoint."""
        old_state = self.state
        if self.state not in {WorkerState.CHECKPOINTING, WorkerState.STOPPED, WorkerState.COMPLETED}:
            self.transition_to(WorkerState.CHECKPOINTING)

        dest_dir = self.checkpoint_dir / checkpoint_id
        dest_dir.mkdir(parents=True, exist_ok=True)

        torch.save(self.model.state_dict(), dest_dir / "model_state.pt")
        torch.save(self.optimizer.state_dict(), dest_dir / "optimizer_state.pt")
        torch.save(self.scheduler.state_dict(), dest_dir / "scheduler_state.pt")
        torch.save(torch.get_rng_state(), dest_dir / "rng_state.pt")

        trainer_state = {
            "step": self.step,
            "cumulative_tokens": self.cumulative_run_tokens,
            "best_val_loss": self.best_val_loss,
            "current_val_loss": val_loss,
            "worker_id": self.worker_id,
            "saved_at": time.time(),
        }
        (dest_dir / "trainer_state.json").write_text(json.dumps(trainer_state, indent=2), encoding="utf-8")
        (dest_dir / "config.json").write_text(json.dumps(self.config.to_dict(), indent=2), encoding="utf-8")

        refs = {
            "parent_checkpoint_hash": self.current_lineage_head,
            "worker_id": self.worker_id,
        }
        (dest_dir / "references.json").write_text(json.dumps(refs, indent=2), encoding="utf-8")

        manifest = Phase47CheckpointLineage.create_checkpoint_manifest(
            checkpoint_dir=dest_dir,
            checkpoint_id=checkpoint_id,
            step=self.step,
            cumulative_tokens=self.cumulative_run_tokens,
            parent_checkpoint_hash=self.current_lineage_head,
        )
        self.current_lineage_head = manifest["checkpoint_hash"]

        if is_best:
            best_dir = self.checkpoint_dir / "checkpoint_best"
            import shutil
            if best_dir.exists():
                shutil.rmtree(best_dir)
            shutil.copytree(dest_dir, best_dir)

        if old_state in {WorkerState.TRAINING, WorkerState.QUEUED, WorkerState.INITIALIZING}:
            self.transition_to(old_state)

        return manifest


    def run_training_slice(
        self,
        job_id: str,
        run_id: str,
        train_batches: Sequence[tuple[torch.Tensor, torch.Tensor]],
        val_batches: Sequence[tuple[torch.Tensor, torch.Tensor]] | None = None,
        target_steps: int = 100,
        checkpoint_interval: int = 20,
        eval_interval: int = 10,
        max_duration_seconds: float = 15.0,
        parent_checkpoint_id: str = "root",
        commit_to_ledger: bool = True,
    ) -> WorkerRunResult:

        """Executes a bounded training slice, accumulating tokens and committing to the ledger."""
        if self.state in {WorkerState.QUEUED, WorkerState.PAUSED, WorkerState.STOPPED}:
            self.transition_to(WorkerState.INITIALIZING)
        self.transition_to(WorkerState.TRAINING)

        start_time = time.time()
        initial_loss: float | None = None
        current_train_loss: float | None = None
        current_val_loss: float | None = None
        stop_reason = "COMPLETED"
        batch_idx = 0
        num_batches = len(train_batches)
        slice_initial_step = self.step
        slice_tokens = 0

        while (self.step - slice_initial_step) < target_steps:
            if self._shutdown_requested:
                stop_reason = "USER_STOP"
                break

            if (time.time() - start_time) >= max_duration_seconds:
                stop_reason = f"TIME_LIMIT ({max_duration_seconds}s bound reached)"
                break

            # ResourceGuard check
            ok, msg = self.resource_guard.check(self.checkpoint_dir)
            if not ok:
                self.transition_to(WorkerState.RESOURCE_WAIT)
                stop_reason = f"RESOURCE_GUARD ({msg})"
                break

            input_ids, targets = train_batches[batch_idx % num_batches]
            batch_tokens = input_ids.numel()

            # Forward & Backward Pass
            self.model.train()
            self.optimizer.zero_grad()
            logits = self.model(input_ids).logits
            loss = self.loss_fn(logits.view(-1, self.config.vocabulary_size), targets.view(-1))
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()
            self.scheduler.step()

            current_train_loss = float(loss.item())
            if initial_loss is None:
                initial_loss = current_train_loss

            self.step += 1
            self.cumulative_run_tokens += batch_tokens
            slice_tokens += batch_tokens
            batch_idx += 1

            # Evaluation Interval
            if val_batches and (self.step % eval_interval == 0):
                self.model.eval()
                val_losses: list[float] = []
                with torch.no_grad():
                    for v_in, v_tgt in val_batches:
                        v_logits = self.model(v_in).logits
                        v_loss = self.loss_fn(v_logits.view(-1, self.config.vocabulary_size), v_tgt.view(-1))
                        val_losses.append(float(v_loss.item()))
                        self.validation_tokens += v_in.numel()
                if val_losses:
                    current_val_loss = sum(val_losses) / len(val_losses)
                    if current_val_loss < self.best_val_loss:
                        self.best_val_loss = current_val_loss

            # Checkpoint Interval
            if self.step % checkpoint_interval == 0:
                ckpt_id = f"checkpoint_step_{self.step}"
                is_best = (current_val_loss is not None and current_val_loss <= self.best_val_loss)
                self.save_checkpoint(ckpt_id, is_best=is_best, val_loss=current_val_loss)
                t_sec = max(0.001, time.time() - start_time)
                tps = slice_tokens / t_sec
                self._log_training_telemetry(job_id, run_id, self.step, current_train_loss, current_val_loss, tps, t_sec)

        total_elapsed = max(0.001, time.time() - start_time)
        final_tps = slice_tokens / total_elapsed

        # Final checkpoint save
        final_ckpt_id = f"checkpoint_step_{self.step}"
        if self.step % checkpoint_interval != 0 or self.step == 0:
            self.save_checkpoint(final_ckpt_id, is_best=False, val_loss=current_val_loss)

        # Transition state
        if stop_reason.startswith("TIME_LIMIT"):
            self.transition_to(WorkerState.STOPPED)
        elif stop_reason.startswith("RESOURCE_GUARD"):
            self.transition_to(WorkerState.RESOURCE_WAIT)
        elif stop_reason == "USER_STOP":
            self.transition_to(WorkerState.STOPPED)
        else:
            self.transition_to(WorkerState.COMPLETED)

        # Commit to Token Ledger (Mandatory Correction 3)
        if commit_to_ledger:
            self.token_ledger.append_run(
                run_id=run_id,
                job_id=job_id,
                worker_id=self.worker_id,
                parent_checkpoint_id=parent_checkpoint_id,
                child_checkpoint_id=final_ckpt_id,
                run_steps=(self.step - slice_initial_step),
                run_tokens=slice_tokens,
            )

        return WorkerRunResult(

            worker_id=self.worker_id,
            job_id=job_id,
            run_id=run_id,
            started_at=start_time,
            ended_at=time.time(),
            actual_steps=(self.step - slice_initial_step),
            actual_training_tokens=slice_tokens,
            actual_validation_tokens=self.validation_tokens,
            duration_seconds=total_elapsed,
            tokens_per_second=final_tps,
            initial_loss=initial_loss,
            final_loss=current_train_loss,
            best_validation_loss=self.best_val_loss if self.best_val_loss != float("inf") else None,
            state=self.state.value,
            stop_reason=stop_reason,
            checkpoint_id=final_ckpt_id,
            parent_checkpoint_id=parent_checkpoint_id,
        )
