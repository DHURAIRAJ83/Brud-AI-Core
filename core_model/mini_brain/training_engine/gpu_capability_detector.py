"""MB-22: GPU Capability Detector -- pure. Classifies an already-
determined GPU availability fact (the service layer calls the real
`torch.cuda.is_available()` and passes the boolean in -- this module
never imports torch itself, keeping it pure and importable with no
dependency on the underlying library being installed).
"""

from __future__ import annotations

from typing import Any


def detect_gpu_capability(*, cuda_available: bool, device_count: int = 0, device_name: str | None = None) -> dict[str, Any]:
    if not cuda_available or device_count == 0:
        return {
            "gpu_available": False, "device_count": 0, "device_name": None,
            "recommended_execution_mode": "cpu",
            "disclosure": "no CUDA-capable device was detected by the real torch.cuda.is_available() check",
        }
    return {
        "gpu_available": True, "device_count": device_count, "device_name": device_name,
        "recommended_execution_mode": "gpu",
        "disclosure": "a CUDA-capable device was genuinely detected -- this does not guarantee sufficient VRAM for any specific job",
    }
