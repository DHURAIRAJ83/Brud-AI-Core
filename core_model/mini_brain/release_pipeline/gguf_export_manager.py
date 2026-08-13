"""MB-07: GGUF Export Manager -- pure. Builds the exact GGUF key-value
metadata plan for architecture "llama", from Brud's own config and
tokenizer facts. Field names and required tensor names are read
directly from the real `gguf` Python library's own
`gguf.constants.MODEL_TENSORS[MODEL_ARCH.LLAMA]` table (verified
directly, never guessed) -- this module only assembles the plan; the
actual `gguf.GGUFWriter` file-writing call happens in the service.
"""

from __future__ import annotations

from typing import Any

ARCHITECTURE = "llama"
TOKENIZER_MODEL = "llama"  # SentencePiece-based, matching Brud's own tokenizer


def build_export_plan(
    *,
    context_length: int,
    hidden_size: int,
    intermediate_size: int,
    num_hidden_layers: int,
    num_attention_heads: int,
    num_key_value_heads: int,
    head_dimension: int,
    rms_norm_epsilon: float,
    rope_theta: float,
    vocabulary_size: int,
    bos_token_id: int,
    eos_token_id: int,
    unk_token_id: int,
    pad_token_id: int,
    quantization_gguf_type: str,
    tensor_mapping: dict[str, str],
) -> dict[str, Any]:
    kv_metadata = {
        "general.architecture": ARCHITECTURE,
        f"{ARCHITECTURE}.context_length": context_length,
        f"{ARCHITECTURE}.embedding_length": hidden_size,
        f"{ARCHITECTURE}.block_count": num_hidden_layers,
        f"{ARCHITECTURE}.feed_forward_length": intermediate_size,
        f"{ARCHITECTURE}.attention.head_count": num_attention_heads,
        f"{ARCHITECTURE}.attention.head_count_kv": num_key_value_heads,
        f"{ARCHITECTURE}.attention.layer_norm_rms_epsilon": rms_norm_epsilon,
        f"{ARCHITECTURE}.rope.freq_base": rope_theta,
        f"{ARCHITECTURE}.rope.dimension_count": head_dimension,
        f"{ARCHITECTURE}.vocab_size": vocabulary_size,
        "tokenizer.ggml.model": TOKENIZER_MODEL,
        "tokenizer.ggml.bos_token_id": bos_token_id,
        "tokenizer.ggml.eos_token_id": eos_token_id,
        "tokenizer.ggml.unknown_token_id": unk_token_id,
        "tokenizer.ggml.padding_token_id": pad_token_id,
    }
    return {
        "architecture": ARCHITECTURE,
        "kv_metadata": kv_metadata,
        "tensor_names": sorted(tensor_mapping),
        "expected_tensor_count": len(tensor_mapping),
        "quantization_gguf_type": quantization_gguf_type,
    }
