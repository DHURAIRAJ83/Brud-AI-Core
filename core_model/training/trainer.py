"""Bounded CPU pretraining loop."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import torch

from core_model.architecture.model import BrudForCausalLM
from core_model.training.batch import pad_sequences
from core_model.training.metrics import available_memory_bytes, process_memory_bytes
from core_model.training.optimizer import adamw
from core_model.training.pretraining_config import PretrainingConfig
from core_model.training.scheduler import build_scheduler
from core_model.training.validation import validation_loss


@dataclass
class TrainerResult:
    status: str
    initial_loss: float
    final_loss: float
    validation_loss: float | None
    processed_tokens: int
    completed_steps: int
    block_index: int
    optimizer_state: dict[str, Any] | None = None
    scheduler_state: dict[str, Any] | None = None
    rng_state: torch.Tensor | None = None


def run_pretraining(
    *,
    model: BrudForCausalLM,
    train_blocks: list[list[int]],
    validation_blocks: list[list[int]],
    config: PretrainingConfig,
    pad_token_id: int,
    start_step: int = 0,
    start_processed_tokens: int = 0,
    start_block_index: int = 0,
    optimizer_state: dict[str, Any] | None = None,
    scheduler_state: dict[str, Any] | None = None,
    rng_state: torch.Tensor | None = None,
    on_step: Callable[[dict], None] | None = None,
    should_pause: Callable[[], bool] | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> TrainerResult:
    if not train_blocks:
        raise ValueError("training split is empty")
    torch.manual_seed(config.initialization_seed)
    optimizer = adamw(
        model,
        lr=config.learning_rate,
        weight_decay=config.weight_decay,
        betas=(config.beta1, config.beta2),
        eps=config.epsilon,
    )
    scheduler = build_scheduler(
        optimizer,
        config.scheduler,
        total_steps=config.total_steps,
        warmup_steps=config.warmup_steps,
    )
    if optimizer_state is not None:
        optimizer.load_state_dict(optimizer_state)
    if scheduler_state is not None:
        scheduler.load_state_dict(scheduler_state)
    if rng_state is not None:
        torch.random.set_rng_state(rng_state)
    processed = start_processed_tokens
    losses: list[float] = []
    block_index = start_block_index
    for step in range(start_step + 1, config.total_steps + 1):
        if should_cancel and should_cancel():
            return TrainerResult(
                "cancelled",
                losses[0] if losses else float("nan"),
                losses[-1] if losses else float("nan"),
                None,
                processed,
                step - 1,
                block_index,
                optimizer.state_dict(),
                scheduler.state_dict(),
                torch.random.get_rng_state(),
            )
        if should_pause and should_pause():
            return TrainerResult(
                "paused",
                losses[0] if losses else float("nan"),
                losses[-1] if losses else float("nan"),
                None,
                processed,
                step - 1,
                block_index,
                optimizer.state_dict(),
                scheduler.state_dict(),
                torch.random.get_rng_state(),
            )
        step_started = time.perf_counter()
        optimizer.zero_grad(set_to_none=True)
        step_loss = 0.0
        for _ in range(config.gradient_accumulation_steps):
            block = train_blocks[block_index % len(train_blocks)]
            block_index += 1
            ids, mask, labels = pad_sequences(
                [block],
                pad_token_id=pad_token_id,
                max_length=config.sequence_length,
                truncate=False,
            )
            output = model(ids, attention_mask=mask, labels=labels)
            if output.loss is None or not torch.isfinite(output.loss):
                raise ValueError("non-finite training loss")
            (output.loss / config.gradient_accumulation_steps).backward()
            step_loss += float(output.loss.detach()) / config.gradient_accumulation_steps
            processed += int((labels[:, 1:] != -100).sum().item())
        grad_norm = torch.nn.utils.clip_grad_norm_(model.parameters(), config.gradient_clip_norm)
        if not torch.isfinite(grad_norm):
            raise ValueError("non-finite gradient norm")
        optimizer.step()
        scheduler.step()
        losses.append(step_loss)
        duration_ms = int((time.perf_counter() - step_started) * 1000)
        if on_step and step % config.metric_interval_steps == 0:
            on_step(
                {
                    "step": step,
                    "processed_tokens": processed,
                    "training_loss": step_loss,
                    "learning_rate": optimizer.param_groups[0]["lr"],
                    "gradient_norm": float(grad_norm),
                    "tokens_per_second": processed / max(0.001, time.perf_counter() - step_started),
                    "step_duration_ms": duration_ms,
                    "process_memory_bytes": process_memory_bytes(),
                    "system_available_memory_bytes": available_memory_bytes(),
                }
            )
    validation = validation_loss(
        model,
        validation_blocks,
        pad_token_id=pad_token_id,
        max_batches=10,
    )
    return TrainerResult(
        "completed",
        losses[0],
        losses[-1],
        validation["loss"],
        processed,
        config.total_steps,
        block_index,
        optimizer.state_dict(),
        scheduler.state_dict(),
        torch.random.get_rng_state(),
    )
