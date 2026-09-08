"""Phase 45 — Sovereign Capability Scaling & Pretraining Accumulation Engine.

Implements Workstreams 2, 3, 4:
- Long-duration pretraining accumulation with genuine PyTorch computation
- Enforces strict 2-thread CPU bounding (num_threads=2) for Pentium G2030
- Exact step and token accounting without fabrication
- AdamW optimizer with Cosine Annealing learning rate schedule
- Resumable training checkpoints with SHA-256 manifest verification
- Rigorous convergence monitoring:
  - Rolling loss tracking
  - Loss slope calculation
  - Plateau detection
  - Overfitting/divergence detection
- Resource Guard monitoring RAM and disk headroom
- Structured telemetry logging to phase45_training_telemetry.jsonl
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR

from core_model.architecture.config import BrudModelConfig
from core_model.architecture.model import BrudForCausalLM
from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager



@dataclass
class TrainingTelemetryRecord:
    timestamp: str
    global_step: int
    epoch: int
    train_loss: float
    rolling_train_loss: float
    validation_loss: float | None
    learning_rate: float
    tokens_processed: int
    tokens_per_second: float
    elapsed_seconds: float
    ram_available_mb: float
    disk_available_mb: float
    checkpoint_id: str | None
    model_hash: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ConvergenceReport:
    initial_loss: float
    rolling_loss: float
    min_train_loss: float
    validation_loss: float
    best_validation_loss: float
    train_val_gap: float
    loss_slope: float
    plateau_detected: bool
    divergence_detected: bool
    overfitting_detected: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CapabilityScaler:
    """Scales pretraining accumulation with rigorous step/token accounting and convergence analysis."""

    def __init__(
        self,
        config: BrudModelConfig,
        checkpoint_dir: Path,
        learning_rate: float = 1e-3,
        min_lr: float = 1e-5,
        weight_decay: float = 0.01,
        gradient_accumulation_steps: int = 1,
        max_threads: int = 2,
        telemetry_file: Path | None = None,
    ) -> None:
        self.config = config
        self.checkpoint_dir = Path(checkpoint_dir)
        self.gradient_accumulation_steps = max(1, gradient_accumulation_steps)
        self.max_threads = max_threads

        # Enforce CPU thread bounding
        torch.set_num_threads(self.max_threads)
        try:
            torch.set_num_interop_threads(self.max_threads)
        except RuntimeError:
            pass

        self.model = BrudForCausalLM(config)
        self.optimizer = AdamW(self.model.parameters(), lr=learning_rate, weight_decay=weight_decay)
        self.scheduler = CosineAnnealingLR(self.optimizer, T_max=1000, eta_min=min_lr)
        self.checkpoint_manager = TrainingCheckpointManager(self.checkpoint_dir, max_bytes=500 * 1024 * 1024)

        self.telemetry_file = telemetry_file or (self.checkpoint_dir / "phase45_training_telemetry.jsonl")

        self.global_step = 0
        self.tokens_processed = 0
        self.best_validation_loss = float("inf")
        self.rolling_losses: list[float] = []
        self.loss_history: list[float] = []
        self.val_loss_history: list[float] = []

    def resume_from_checkpoint(self, checkpoint_dir: Path) -> dict[str, Any]:
        """Restores model, optimizer, scheduler, step, and token state from checkpoint."""
        self.checkpoint_manager.verify(checkpoint_dir)
        states = self.checkpoint_manager.load_states(checkpoint_dir)
        self.model.load_state_dict(states["model"])
        self.optimizer.load_state_dict(states["optimizer"])
        self.scheduler.load_state_dict(states["scheduler"])
        trainer_state = json.loads((checkpoint_dir / "trainer_state.json").read_text(encoding="utf-8"))
        self.global_step = trainer_state.get("step", 0)
        self.tokens_processed = trainer_state.get("tokens_processed", 0)
        return trainer_state


    def _get_system_resources(self) -> tuple[float, float]:
        """Returns available RAM and disk in MB."""
        try:
            # Memory
            with open("/proc/meminfo", "r") as f:
                mem_avail_kb = next(int(line.split()[1]) for line in f if "MemAvailable:" in line)
            ram_mb = mem_avail_kb / 1024.0
        except Exception:
            ram_mb = 4096.0

        try:
            # Disk
            st = os.statvfs(str(self.checkpoint_dir if self.checkpoint_dir.exists() else "/"))
            disk_mb = (st.f_bavail * st.f_frsize) / (1024.0 * 1024.0)
        except Exception:
            disk_mb = 50000.0

        return ram_mb, disk_mb

    def compute_model_hash(self) -> str:
        """Computes deterministic SHA-256 of model parameter weights."""
        hasher = hashlib.sha256()
        for p in self.model.parameters():
            hasher.update(p.detach().cpu().numpy().tobytes())
        return hasher.hexdigest()

    def compute_loss(self, logits: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """Computes cross entropy loss ignoring padding."""
        vocab_size = logits.size(-1)
        loss_fn = nn.CrossEntropyLoss(ignore_index=self.config.ignore_index)
        return loss_fn(logits.view(-1, vocab_size), targets.view(-1))

    def evaluate_validation(self, val_batches: Sequence[tuple[torch.Tensor, torch.Tensor]]) -> float:
        """Evaluates model on held-out validation batches with torch.no_grad()."""
        if not val_batches:
            return 0.0

        self.model.eval()
        total_loss = 0.0
        with torch.no_grad():
            for x, y in val_batches:
                out = self.model(x)
                logits = out.logits if hasattr(out, "logits") else out
                loss = self.compute_loss(logits, y)
                total_loss += loss.item()

        self.model.train()
        return total_loss / len(val_batches)


    def analyze_convergence(self) -> ConvergenceReport:
        """Analyzes loss convergence slope, plateaus, and divergence."""
        if not self.loss_history:
            return ConvergenceReport(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False, False, False)

        init_loss = self.loss_history[0]
        cur_rolling = sum(self.rolling_losses[-10:]) / max(1, len(self.rolling_losses[-10:]))
        min_train = min(self.loss_history)
        cur_val = self.val_loss_history[-1] if self.val_loss_history else cur_rolling
        best_val = self.best_validation_loss if self.best_validation_loss != float("inf") else cur_val

        # Slope: delta loss over last 10 steps
        if len(self.loss_history) >= 10:
            loss_slope = (self.loss_history[-1] - self.loss_history[-10]) / 10.0
        else:
            loss_slope = (self.loss_history[-1] - self.loss_history[0]) / max(1, len(self.loss_history))

        # Plateau: absolute slope < 0.001 over last 10 steps
        plateau = len(self.loss_history) >= 10 and abs(loss_slope) < 0.001

        # Divergence / Overfitting
        divergence = False
        overfitting = False
        if self.val_loss_history:
            train_val_gap = cur_val - cur_rolling
            if cur_val > best_val + 2.0:
                divergence = True
            if train_val_gap > 1.5:
                overfitting = True
        else:
            train_val_gap = 0.0

        return ConvergenceReport(
            initial_loss=init_loss,
            rolling_loss=cur_rolling,
            min_train_loss=min_train,
            validation_loss=cur_val,
            best_validation_loss=best_val,
            train_val_gap=train_val_gap,
            loss_slope=loss_slope,
            plateau_detected=plateau,
            divergence_detected=divergence,
            overfitting_detected=overfitting,
        )

    def train_accumulation(
        self,
        train_batches: Sequence[tuple[torch.Tensor, torch.Tensor]],
        val_batches: Sequence[tuple[torch.Tensor, torch.Tensor]],
        target_steps: int = 50000,
        checkpoint_interval: int = 10,
        eval_interval: int = 5,
        max_duration_seconds: float = 60.0,
    ) -> dict[str, Any]:
        """Executes long-duration training accumulation within hardware constraints."""
        t_start = time.time()
        self.model.train()

        batch_idx = 0
        n_batches = len(train_batches)
        if n_batches == 0:
            return {"status": "NO_BATCHES", "completed_steps": 0, "tokens": 0}

        accumulated_loss = 0.0
        last_ckpt_id = None
        stopped_reason = "TARGET_STEPS_COMPLETED"

        while self.global_step < target_steps:
            elapsed = time.time() - t_start
            if elapsed >= max_duration_seconds:
                stopped_reason = f"TIME_LIMIT_REACHED ({max_duration_seconds:.1f}s bound)"
                break

            ram_mb, disk_mb = self._get_system_resources()
            if ram_mb < 500.0:
                stopped_reason = f"RESOURCE_GUARD_RAM_LIMIT ({ram_mb:.1f} MB remaining)"
                break
            if disk_mb < 1000.0:
                stopped_reason = f"RESOURCE_GUARD_DISK_LIMIT ({disk_mb:.1f} MB remaining)"
                break

            x, y = train_batches[batch_idx % n_batches]
            batch_idx += 1

            batch_tokens = x.numel()
            out = self.model(x)
            logits = out.logits if hasattr(out, "logits") else out
            loss = self.compute_loss(logits, y)
            loss_val = loss.item()


            loss = loss / self.gradient_accumulation_steps
            loss.backward()
            accumulated_loss += loss_val

            if batch_idx % self.gradient_accumulation_steps == 0:
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
                self.optimizer.step()
                self.scheduler.step()
                self.optimizer.zero_grad()

                self.global_step += 1
                self.tokens_processed += batch_tokens * self.gradient_accumulation_steps
                step_loss = accumulated_loss / self.gradient_accumulation_steps
                accumulated_loss = 0.0

                self.loss_history.append(step_loss)
                self.rolling_losses.append(step_loss)
                if len(self.rolling_losses) > 100:
                    self.rolling_losses.pop(0)

                rolling_loss = sum(self.rolling_losses) / len(self.rolling_losses)

                # Validation
                val_loss = None
                if self.global_step % eval_interval == 0 and val_batches:
                    val_loss = self.evaluate_validation(val_batches)
                    self.val_loss_history.append(val_loss)
                    if val_loss < self.best_validation_loss:
                        self.best_validation_loss = val_loss

                # Checkpoint
                if self.global_step % checkpoint_interval == 0:
                    last_ckpt_id = f"checkpoint_step_{self.global_step}"
                    ckpt_target = self.checkpoint_dir / last_ckpt_id
                    if not ckpt_target.exists():
                        self.checkpoint_manager.save(
                            ckpt_target,
                            model=self.model,
                            optimizer=self.optimizer,
                            scheduler=self.scheduler,
                            trainer_state={
                                "step": self.global_step,
                                "train_loss": step_loss,
                                "rolling_train_loss": rolling_loss,
                                "val_loss": val_loss,
                                "tokens_processed": self.tokens_processed,
                            },
                            config=self.config.to_dict(),
                            references={"model_version": "0.4.0-candidate"},
                        )


                # Telemetry
                tokens_per_sec = self.tokens_processed / max(0.001, time.time() - t_start)
                telem = TrainingTelemetryRecord(
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    global_step=self.global_step,
                    epoch=1 + (self.global_step // n_batches),
                    train_loss=step_loss,
                    rolling_train_loss=rolling_loss,
                    validation_loss=val_loss,
                    learning_rate=self.scheduler.get_last_lr()[0],
                    tokens_processed=self.tokens_processed,
                    tokens_per_second=tokens_per_sec,
                    elapsed_seconds=time.time() - t_start,
                    ram_available_mb=ram_mb,
                    disk_available_mb=disk_mb,
                    checkpoint_id=last_ckpt_id,
                    model_hash=self.compute_model_hash(),
                )

                self.telemetry_file.parent.mkdir(parents=True, exist_ok=True)
                with self.telemetry_file.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(telem.to_dict()) + "\n")

        total_elapsed = time.time() - t_start
        conv = self.analyze_convergence()

        return {
            "status": "COMPLETED",
            "target_steps": target_steps,
            "actual_steps": self.global_step,
            "actual_tokens": self.tokens_processed,
            "actual_runtime_seconds": total_elapsed,
            "actual_train_loss": self.loss_history[-1] if self.loss_history else 0.0,
            "actual_validation_loss": self.val_loss_history[-1] if self.val_loss_history else None,
            "best_validation_loss": self.best_validation_loss if self.best_validation_loss != float("inf") else None,
            "actual_throughput_tokens_per_sec": self.tokens_processed / max(0.001, total_elapsed),
            "limitation_reason": stopped_reason if self.global_step < target_steps else None,
            "convergence": conv.to_dict(),
            "last_checkpoint_id": last_ckpt_id,
        }
