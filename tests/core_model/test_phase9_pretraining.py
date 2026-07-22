import numpy as np
import torch

from core_model.architecture.config import BrudModelConfig
from core_model.architecture.model import BrudForCausalLM
from core_model.training.dataset_stream import packed_blocks
from core_model.training.optimizer import adamw
from core_model.training.pretraining_config import from_mapping
from core_model.training.scheduler import build_scheduler
from core_model.training.trainer import run_pretraining
from core_model.training.validation import validation_loss


def test_numpy_and_torch_interop() -> None:
    tensor = torch.from_numpy(np.array([1, 2, 3]))
    assert tensor.tolist() == [1, 2, 3]


def test_deterministic_packing_padding_and_validation_isolated() -> None:
    sequences = [[2, 5, 6, 3], [2, 7, 8, 9, 3]]
    first = packed_blocks(sequences, sequence_length=6, pad_token_id=0, policy="split_oversized")
    second = packed_blocks(sequences, sequence_length=6, pad_token_id=0, policy="split_oversized")
    assert first == second
    assert all(len(block) == 6 for block in first)
    assert first[-1][-1] == 0


def test_bounded_training_loop_persists_finite_result() -> None:
    config = BrudModelConfig(
        vocabulary_size=32,
        context_length=16,
        hidden_size=16,
        intermediate_size=32,
        num_hidden_layers=1,
        num_attention_heads=2,
        num_key_value_heads=2,
    )
    torch.manual_seed(7)
    model = BrudForCausalLM(config)
    pretraining = from_mapping(
        {
            "batch_size": 1,
            "gradient_accumulation_steps": 1,
            "sequence_length": 8,
            "total_steps": 3,
            "metric_interval_steps": 1,
            "learning_rate": 0.01,
        }
    )
    metrics: list[dict] = []
    result = run_pretraining(
        model=model,
        train_blocks=[[2, 5, 6, 7, 8, 9, 10, 3]],
        validation_blocks=[[2, 5, 6, 7, 3, 0, 0, 0]],
        config=pretraining,
        pad_token_id=0,
        on_step=metrics.append,
    )
    assert result.status == "completed"
    assert result.processed_tokens > 0
    assert torch.isfinite(torch.tensor(result.final_loss))
    assert len(metrics) == 3
    assert result.optimizer_state and result.scheduler_state and result.rng_state is not None


def test_optimizer_scheduler_and_validation_helpers() -> None:
    model = BrudForCausalLM(
        BrudModelConfig(
            vocabulary_size=24,
            context_length=8,
            hidden_size=16,
            intermediate_size=32,
            num_hidden_layers=1,
            num_attention_heads=2,
            num_key_value_heads=2,
        )
    )
    optimizer = adamw(model, lr=0.001, weight_decay=0.01, betas=(0.9, 0.95), eps=1e-8)
    param_ids = [id(param) for group in optimizer.param_groups for param in group["params"]]
    assert len(param_ids) == len(set(param_ids))
    scheduler = build_scheduler(optimizer, "linear_warmup_decay", total_steps=4, warmup_steps=1)
    optimizer.step()
    scheduler.step()
    result = validation_loss(model, [[2, 5, 6, 3]], pad_token_id=0, max_batches=1)
    assert result["tokens"] > 0
    assert result["loss"] is not None
