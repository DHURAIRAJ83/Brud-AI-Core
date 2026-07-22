"""Token embedding layer for Brud Core."""

import torch
from torch import nn

from core_model.architecture.config import BrudModelConfig


class TokenEmbeddings(nn.Module):
    def __init__(self, config: BrudModelConfig) -> None:
        super().__init__()
        self.embedding = nn.Embedding(
            config.vocabulary_size,
            config.hidden_size,
            padding_idx=config.pad_token_id,
        )
        self.dropout = nn.Dropout(config.embedding_dropout)

    def forward(self, input_ids: torch.Tensor) -> torch.Tensor:
        return self.dropout(self.embedding(input_ids))
