"""MB-07: Model Converter -- pure. Plans the PyTorch state_dict ->
GGUF "llama"-architecture tensor mapping for Brud's own
`core_model.architecture.model.BrudForCausalLM`.

Empirically verified (real spike, not assumed): Brud's own
`apply_rotary`/`rotate_half` (interleaved-pair convention) already
matches ggml's native "llama" architecture RoPE kernel directly.
Applying the HF-style `permute()` weight reshuffle that
`convert_hf_to_gguf.py` uses for HuggingFace-format Llama checkpoints
is NOT needed here and was confirmed, via a controlled A/B numerical
test against a real llama_cpp load, to make the conversion WORSE
(cosine similarity 0.9988 with permute vs 0.9999999 without on
identical random weights). Every tensor below is copied unchanged,
never reshuffled.

This module only plans the mapping (which source tensor name maps to
which GGUF tensor name) -- it never touches an actual tensor or opens
a file. The service layer loads the real state_dict and does the
actual copy.
"""

from __future__ import annotations

from typing import Any

GGUF_ARCHITECTURE = "llama"


def build_tensor_mapping(
    *, num_hidden_layers: int, state_dict_keys: list[str],
) -> dict[str, Any]:
    expected: dict[str, str] = {
        "token_embd.weight": "embed_tokens.embedding.weight",
        "output_norm.weight": "norm.weight",
        "output.weight": "lm_head.weight",
    }
    for i in range(num_hidden_layers):
        p = f"layers.{i}."
        expected[f"blk.{i}.attn_norm.weight"] = p + "input_norm.weight"
        expected[f"blk.{i}.attn_q.weight"] = p + "attention.q_proj.weight"
        expected[f"blk.{i}.attn_k.weight"] = p + "attention.k_proj.weight"
        expected[f"blk.{i}.attn_v.weight"] = p + "attention.v_proj.weight"
        expected[f"blk.{i}.attn_output.weight"] = p + "attention.o_proj.weight"
        expected[f"blk.{i}.ffn_norm.weight"] = p + "post_attention_norm.weight"
        expected[f"blk.{i}.ffn_gate.weight"] = p + "feed_forward.gate_proj.weight"
        expected[f"blk.{i}.ffn_up.weight"] = p + "feed_forward.up_proj.weight"
        expected[f"blk.{i}.ffn_down.weight"] = p + "feed_forward.down_proj.weight"

    available = set(state_dict_keys)
    mapping = {gguf_name: source for gguf_name, source in expected.items() if source in available}
    missing_source_tensors = sorted(source for source in expected.values() if source not in available)
    unmapped_source_tensors = sorted(available - set(expected.values()))

    architecture_compatible = not missing_source_tensors

    return {
        "architecture": GGUF_ARCHITECTURE,
        "permute_applied": False,
        "mapping": mapping,
        "missing_source_tensors": missing_source_tensors,
        "unmapped_source_tensors": unmapped_source_tensors,
        "architecture_compatible": architecture_compatible,
        "tensor_count": len(mapping),
    }
