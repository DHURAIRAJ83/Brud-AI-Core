"""Validated Brud decoder-only Transformer configuration."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class BrudModelConfig:
    vocabulary_size: int
    context_length: int
    hidden_size: int
    intermediate_size: int
    num_hidden_layers: int
    num_attention_heads: int
    num_key_value_heads: int
    rope_theta: float = 10000.0
    rms_norm_epsilon: float = 1e-6
    attention_dropout: float = 0.0
    residual_dropout: float = 0.0
    embedding_dropout: float = 0.0
    initializer_range: float = 0.02
    tie_word_embeddings: bool = True
    use_bias: bool = False
    pad_token_id: int = 0
    bos_token_id: int = 2
    eos_token_id: int = 3
    unk_token_id: int = 1
    ignore_index: int = -100

    @property
    def head_dimension(self) -> int:
        return self.hidden_size // self.num_attention_heads

    def validate(self) -> None:
        if self.vocabulary_size <= 0:
            raise ValueError("vocabulary_size must be positive")
        if self.context_length <= 1:
            raise ValueError("context_length must be greater than 1")
        if self.hidden_size <= 0 or self.intermediate_size <= 0:
            raise ValueError("hidden and intermediate sizes must be positive")
        if self.num_hidden_layers <= 0:
            raise ValueError("num_hidden_layers must be positive")
        if self.num_attention_heads <= 0 or self.num_key_value_heads <= 0:
            raise ValueError("attention head counts must be positive")
        if self.num_key_value_heads != self.num_attention_heads:
            raise ValueError("Phase 8 supports standard MHA: key/value heads must match heads")
        if self.hidden_size % self.num_attention_heads:
            raise ValueError("hidden_size must be divisible by num_attention_heads")
        if self.head_dimension % 2:
            raise ValueError("RoPE requires an even head dimension")
        if not 0 <= self.attention_dropout <= 1:
            raise ValueError("attention_dropout must be between 0 and 1")
        if not 0 <= self.residual_dropout <= 1:
            raise ValueError("residual_dropout must be between 0 and 1")
        if not 0 <= self.embedding_dropout <= 1:
            raise ValueError("embedding_dropout must be between 0 and 1")
        if self.rms_norm_epsilon <= 0:
            raise ValueError("rms_norm_epsilon must be positive")
        for token_id in (
            self.pad_token_id,
            self.bos_token_id,
            self.eos_token_id,
            self.unk_token_id,
        ):
            if token_id < 0 or token_id >= self.vocabulary_size:
                raise ValueError("special token id outside vocabulary")

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def micro_preset(vocabulary_size: int, **overrides: object) -> BrudModelConfig:
    data = {
        "vocabulary_size": vocabulary_size,
        "context_length": 256,
        "hidden_size": 128,
        "intermediate_size": 384,
        "num_hidden_layers": 4,
        "num_attention_heads": 4,
        "num_key_value_heads": 4,
    }
    data.update(overrides)
    config = BrudModelConfig(**data)
    config.validate()
    return config


def tiny_preset(vocabulary_size: int, **overrides: object) -> BrudModelConfig:
    data = {
        "vocabulary_size": vocabulary_size,
        "context_length": 512,
        "hidden_size": 256,
        "intermediate_size": 768,
        "num_hidden_layers": 6,
        "num_attention_heads": 8,
        "num_key_value_heads": 8,
    }
    data.update(overrides)
    config = BrudModelConfig(**data)
    config.validate()
    return config
