"""MB-29: Storage Estimator -- pure. Estimates RAM/disk footprint from
a parameter count and a GGUF quantization label, using well-known
approximate bits-per-parameter figures for each quant level.
"""

from __future__ import annotations

_BYTES_PER_PARAM_BY_QUANT: dict[str, float] = {
    "Q2_K": 0.35, "Q3_K_M": 0.45, "Q4_0": 0.55, "Q4_K_M": 0.5625, "Q4_K_S": 0.55,
    "Q5_0": 0.65, "Q5_K_M": 0.6875, "Q6_K": 0.75, "Q8_0": 1.0625, "F16": 2.0, "F32": 4.0,
}
_DEFAULT_BYTES_PER_PARAM = 0.6
_RUNTIME_OVERHEAD_FACTOR = 1.2  # KV cache + runtime overhead on top of raw weight size


def _bytes_per_param(quantization: str | None) -> float:
    return _BYTES_PER_PARAM_BY_QUANT.get((quantization or "").upper(), _DEFAULT_BYTES_PER_PARAM)


def estimate_disk_usage_gb(*, params_billions: float, quantization: str | None) -> float:
    return round(params_billions * _bytes_per_param(quantization), 2)


def estimate_ram_usage_gb(*, params_billions: float, quantization: str | None) -> float:
    return round(estimate_disk_usage_gb(params_billions=params_billions, quantization=quantization) * _RUNTIME_OVERHEAD_FACTOR, 2)
