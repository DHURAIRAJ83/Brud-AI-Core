"""Brud decoder-only Transformer language-model architecture."""

import torch
from torch import nn

from core_model.architecture.config import BrudModelConfig
from core_model.architecture.embeddings import TokenEmbeddings
from core_model.architecture.outputs import CausalLMOutput
from core_model.architecture.transformer_block import RMSNorm, TransformerBlock
from core_model.training.loss import causal_lm_loss


class BrudForCausalLM(nn.Module):
    def __init__(self, config: BrudModelConfig) -> None:
        super().__init__()
        config.validate()
        self.config = config
        self.embed_tokens = TokenEmbeddings(config)
        self.layers = nn.ModuleList([TransformerBlock(config) for _ in range(config.num_hidden_layers)])
        self.norm = RMSNorm(config.hidden_size, config.rms_norm_epsilon)
        self.lm_head = nn.Linear(config.hidden_size, config.vocabulary_size, bias=False)
        if config.tie_word_embeddings:
            self.lm_head.weight = self.embed_tokens.embedding.weight
        self.apply(self._init_weights)

    def _init_weights(self, module: nn.Module) -> None:
        if isinstance(module, nn.Linear):
            nn.init.normal_(module.weight, mean=0.0, std=self.config.initializer_range)
            if module.bias is not None:
                nn.init.zeros_(module.bias)
        elif isinstance(module, nn.Embedding):
            nn.init.normal_(module.weight, mean=0.0, std=self.config.initializer_range)
            if module.padding_idx is not None:
                with torch.no_grad():
                    module.weight[module.padding_idx].zero_()

    def _validate_inputs(self, input_ids: torch.Tensor, labels: torch.Tensor | None) -> None:
        if input_ids.ndim != 2:
            raise ValueError("input_ids must be [batch, sequence]")
        if input_ids.shape[1] == 0:
            raise ValueError("empty sequences are not allowed")
        if input_ids.shape[1] > self.config.context_length:
            raise ValueError("sequence length exceeds configured context")
        if input_ids.min().item() < 0 or input_ids.max().item() >= self.config.vocabulary_size:
            raise ValueError("input token id outside vocabulary")
        if labels is not None:
            valid = labels != self.config.ignore_index
            if valid.any() and (
                labels[valid].min().item() < 0
                or labels[valid].max().item() >= self.config.vocabulary_size
            ):
                raise ValueError("label token id outside vocabulary")

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        labels: torch.Tensor | None = None,
        position_ids: torch.Tensor | None = None,
    ) -> CausalLMOutput:
        self._validate_inputs(input_ids, labels)
        batch, seq = input_ids.shape
        if attention_mask is None:
            attention_mask = (input_ids != self.config.pad_token_id).long()
        hidden = self.embed_tokens(input_ids)
        for layer in self.layers:
            hidden = layer(hidden, attention_mask, position_ids)
        hidden = self.norm(hidden)
        logits = self.lm_head(hidden)
        loss = causal_lm_loss(logits, labels, self.config.ignore_index) if labels is not None else None
        return CausalLMOutput(logits=logits, loss=loss, metadata={"batch_size": batch, "sequence_length": seq})


def count_parameters(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters())
