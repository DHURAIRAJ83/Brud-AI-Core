"""MB-07: Quantization Manager -- pure. Decides which quantization
levels are genuinely encodable in this environment, and which are not.

Honest scope, verified directly against the installed `gguf` Python
library (the same reference implementation llama.cpp's own converters
use): it ships real, working ENCODERS for the legacy per-block formats
(Q8_0, Q5_1, Q5_0, Q4_1, Q4_0) plus F16/F32 -- confirmed by a real
export + llama_cpp load-and-compare spike (cosine similarity 0.999+
for Q8_0, degrading gracefully through Q4_0, exactly the expected
pattern for correct quantization). It does NOT ship an encoder for the
super-block "K-quant" formats (Q2_K, Q3_K, Q4_K, Q5_K, Q6_K) -- only a
DEQUANTIZER (`gguf.quants.<Type>.quantize_blocks` raises
`NotImplementedError` for every K-quant class; only the legacy classes
define it). The task's requested "Q2 / Q3 / Q4_K_M / Q5 / Q6" levels
map onto exactly these unencodable K-quant formats. Rather than fabricate
support, every K-quant level is reported NOT SUPPORTED with that exact
reason -- encoding them for real would require porting llama.cpp's C++
k-quant kernels, out of scope for this phase.
"""

from __future__ import annotations

from typing import Any

# (gguf.GGMLQuantizationType name, block_size, type_size_bytes)
SUPPORTED_LEVELS: dict[str, dict[str, Any]] = {
    "f32": {"gguf_type": "F32", "block_size": 1, "type_size_bytes": 4, "lossy": False},
    "f16": {"gguf_type": "F16", "block_size": 1, "type_size_bytes": 2, "lossy": True},
    "q8_0": {"gguf_type": "Q8_0", "block_size": 32, "type_size_bytes": 34, "lossy": True},
    "q5_1": {"gguf_type": "Q5_1", "block_size": 32, "type_size_bytes": 24, "lossy": True},
    "q5_0": {"gguf_type": "Q5_0", "block_size": 32, "type_size_bytes": 22, "lossy": True},
    "q4_1": {"gguf_type": "Q4_1", "block_size": 32, "type_size_bytes": 20, "lossy": True},
    "q4_0": {"gguf_type": "Q4_0", "block_size": 32, "type_size_bytes": 18, "lossy": True},
}

_K_QUANT_UNSUPPORTED_REASON = (
    "the installed gguf Python library has no quantize encoder for this K-quant "
    "format (dequantize-only) -- real encoding would require porting llama.cpp's "
    "C++ k-quant kernels"
)

UNSUPPORTED_LEVELS: dict[str, dict[str, Any]] = {
    "q2": {"requested_as": "Q2_K", "reason": _K_QUANT_UNSUPPORTED_REASON},
    "q3": {"requested_as": "Q3_K", "reason": _K_QUANT_UNSUPPORTED_REASON},
    "q4_k_m": {"requested_as": "Q4_K (uniform, not the mixed-per-tensor '_M' strategy)", "reason": _K_QUANT_UNSUPPORTED_REASON},
    "q5": {"requested_as": "Q5_K", "reason": _K_QUANT_UNSUPPORTED_REASON},
    "q6": {"requested_as": "Q6_K", "reason": _K_QUANT_UNSUPPORTED_REASON},
}


def describe_quantization_level(level: str) -> dict[str, Any]:
    key = level.lower()
    if key in SUPPORTED_LEVELS:
        return {"level": key, "supported": True, **SUPPORTED_LEVELS[key]}
    if key in UNSUPPORTED_LEVELS:
        return {"level": key, "supported": False, **UNSUPPORTED_LEVELS[key]}
    return {"level": key, "supported": False, "reason": f"unknown quantization level {level!r}"}


def plan_quantization(levels: list[str]) -> dict[str, Any]:
    plans = [describe_quantization_level(level) for level in levels]
    supported = [p for p in plans if p["supported"]]
    unsupported = [p for p in plans if not p["supported"]]
    return {
        "requested_levels": levels,
        "plans": plans,
        "supported_count": len(supported),
        "unsupported_count": len(unsupported),
        "all_supported": not unsupported,
    }


def available_levels() -> list[str]:
    return sorted(SUPPORTED_LEVELS)
