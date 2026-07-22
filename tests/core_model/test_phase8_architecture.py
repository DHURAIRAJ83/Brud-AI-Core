import pytest
import torch

from core_model.architecture.attention import CausalSelfAttention
from core_model.architecture.config import BrudModelConfig, micro_preset, tiny_preset
from core_model.architecture.model import BrudForCausalLM
from core_model.architecture.rope import RotaryEmbedding
from core_model.architecture.transformer_block import RMSNorm
from core_model.evaluation.architecture_checks import (
    actual_parameter_count,
    causal_isolation_check,
    estimate_memory,
    estimate_parameters,
    weights_checksum,
)
from core_model.training.batch import pad_sequences


def small_config(**overrides) -> BrudModelConfig:
    data = {
        "vocabulary_size": 128,
        "context_length": 32,
        "hidden_size": 32,
        "intermediate_size": 64,
        "num_hidden_layers": 2,
        "num_attention_heads": 4,
        "num_key_value_heads": 4,
    }
    data.update(overrides)
    config = BrudModelConfig(**data)
    config.validate()
    return config


def test_micro_and_tiny_presets_validate() -> None:
    assert micro_preset(1000).hidden_size == 128
    assert tiny_preset(1000).num_hidden_layers == 6


def test_invalid_head_dimension_rejected() -> None:
    with pytest.raises(ValueError, match="divisible"):
        small_config(hidden_size=30)


def test_rmsnorm_rope_attention_shapes_and_gradients() -> None:
    config = small_config()
    x = torch.randn(2, 8, config.hidden_size, requires_grad=True)
    normed = RMSNorm(config.hidden_size)(x)
    assert normed.shape == x.shape
    normed.sum().backward(retain_graph=True)
    assert x.grad is not None
    rope = RotaryEmbedding(config.head_dimension, config.context_length)
    cos, sin = rope(torch.randn(2, 4, 8, config.head_dimension), torch.arange(8).repeat(2, 1))
    assert cos.shape == (2, 1, 8, config.head_dimension // 2)
    attention = CausalSelfAttention(config)
    assert attention(x.detach(), torch.ones(2, 8, dtype=torch.long)).shape == x.shape


def test_model_forward_loss_backward_and_invalid_ids() -> None:
    config = small_config()
    model = BrudForCausalLM(config)
    ids, mask, labels = pad_sequences([[2, 5, 6, 3], [2, 7, 3]], pad_token_id=0, max_length=8)
    output = model(ids, attention_mask=mask, labels=labels)
    assert output.logits.shape == (2, 4, config.vocabulary_size)
    assert output.loss is not None and torch.isfinite(output.loss)
    output.loss.backward()
    assert all(p.grad is None or torch.isfinite(p.grad).all() for p in model.parameters())
    with pytest.raises(ValueError, match="outside vocabulary"):
        model(torch.tensor([[config.vocabulary_size]]))


def test_causal_mask_isolation_and_parameter_estimates() -> None:
    config = small_config()
    assert causal_isolation_check(config)["status"] == "pass"
    estimate = estimate_parameters(config)
    actual = actual_parameter_count(config)
    assert estimate == actual
    memory = estimate_memory(config)
    assert memory["training_adamw"] > memory["inference"]


def test_deterministic_initialization_checksums() -> None:
    config = small_config()
    torch.manual_seed(123)
    first = weights_checksum(BrudForCausalLM(config))
    torch.manual_seed(123)
    second = weights_checksum(BrudForCausalLM(config))
    torch.manual_seed(124)
    third = weights_checksum(BrudForCausalLM(config))
    assert first == second
    assert first != third
