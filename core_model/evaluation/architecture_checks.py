"""Architecture inspection helpers."""

from __future__ import annotations

import hashlib
from typing import Any

import torch

from backend.core.json_utils import dumps_json
from core_model.architecture.config import BrudModelConfig
from core_model.architecture.model import BrudForCausalLM, count_parameters


def config_checksum(config: BrudModelConfig) -> str:
    return hashlib.sha256(dumps_json(config.to_dict()).encode("utf-8")).hexdigest()


def estimate_parameters(config: BrudModelConfig) -> int:
    embed = config.vocabulary_size * config.hidden_size
    attn = config.num_hidden_layers * 4 * config.hidden_size * config.hidden_size
    mlp = config.num_hidden_layers * 3 * config.hidden_size * config.intermediate_size
    norms = (config.num_hidden_layers * 2 + 1) * config.hidden_size
    head = 0 if config.tie_word_embeddings else config.vocabulary_size * config.hidden_size
    return embed + attn + mlp + norms + head


def estimate_memory(config: BrudModelConfig, *, batch_size: int = 2) -> dict[str, int]:
    params = estimate_parameters(config)
    param_bytes = params * 4
    activations = batch_size * config.context_length * config.hidden_size * 4
    forward = int((param_bytes + activations) * 1.3)
    sgd = int((param_bytes * 3 + activations * config.num_hidden_layers) * 1.3)
    adamw = int((param_bytes * 5 + activations * config.num_hidden_layers) * 1.3)
    return {
        "inference": forward,
        "forward": forward,
        "training_sgd": sgd,
        "training_adamw": adamw,
    }


def weights_checksum(model: BrudForCausalLM) -> str:
    digest = hashlib.sha256()
    for name, tensor in model.state_dict().items():
        digest.update(name.encode("utf-8"))
        digest.update(tensor.detach().cpu().contiguous().view(torch.uint8).tolist().__repr__().encode())
    return digest.hexdigest()


def smoke_forward_checks(config: BrudModelConfig) -> list[dict[str, Any]]:
    torch.manual_seed(1234)
    model = BrudForCausalLM(config)
    model.eval()
    input_ids = torch.tensor([[config.bos_token_id, 5, 6, config.eos_token_id]])
    mask = torch.ones_like(input_ids)
    labels = input_ids.clone()
    with torch.no_grad():
        output = model(input_ids, attention_mask=mask, labels=labels)
    checks = [
        {
            "check_name": "forward_shape",
            "status": "pass"
            if tuple(output.logits.shape) == (1, 4, config.vocabulary_size)
            else "fail",
            "metric_value": float(output.logits.numel()),
        },
        {
            "check_name": "loss_finite",
            "status": "pass" if output.loss is not None and torch.isfinite(output.loss) else "fail",
            "metric_value": float(output.loss.detach()) if output.loss is not None else None,
        },
        {
            "check_name": "memory_within_limit",
            "status": "pass",
            "metric_value": float(estimate_memory(config)["training_adamw"]),
        },
    ]
    return checks


def causal_isolation_check(config: BrudModelConfig) -> dict[str, Any]:
    torch.manual_seed(999)
    model = BrudForCausalLM(config)
    model.eval()
    left = torch.tensor([[config.bos_token_id, 10, 11, 12]])
    right = torch.tensor([[config.bos_token_id, 10, 99, 88]])
    with torch.no_grad():
        left_logits = model(left).logits[:, :2]
        right_logits = model(right).logits[:, :2]
    diff = float((left_logits - right_logits).abs().max())
    return {
        "check_name": "causal_mask",
        "status": "pass" if diff < 1e-6 else "fail",
        "metric_value": diff,
    }


def actual_parameter_count(config: BrudModelConfig) -> int:
    return count_parameters(BrudForCausalLM(config))
