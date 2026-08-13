"""Model Validation -- pure rules over already-gathered file facts
(the service layer does the actual `os.stat`/path check; this module
only decides what those facts mean). Deliberately conservative: a
missing file, wrong extension, zero-byte file, or an oversized file
are all rejected outright, never a warning-only pass-through.
"""

from __future__ import annotations

REQUIRED_EXTENSION = ".gguf"
DEFAULT_MAX_MODEL_BYTES = 8 * 1024 * 1024 * 1024  # 8 GiB -- generous but bounded


def validate_model_file(
    *, path: str, exists: bool, size_bytes: int, max_size_bytes: int = DEFAULT_MAX_MODEL_BYTES,
) -> list[str]:
    issues: list[str] = []
    if not path.lower().endswith(REQUIRED_EXTENSION):
        issues.append(f"model file must have a {REQUIRED_EXTENSION} extension")
    if not exists:
        issues.append(f"model file does not exist: {path}")
        return issues  # size checks are meaningless against a missing file
    if size_bytes <= 0:
        issues.append("model file is empty")
    elif size_bytes > max_size_bytes:
        issues.append(
            f"model file ({size_bytes} bytes) exceeds the maximum allowed size ({max_size_bytes} bytes)"
        )
    return issues


def validate_registration_payload(*, name: str, path: str, quantization: str, context_length: int) -> list[str]:
    issues: list[str] = []
    if not name.strip():
        issues.append("model name is required")
    if not path.strip():
        issues.append("model path is required")
    if context_length <= 0:
        issues.append("context_length must be positive")
    if not quantization.strip():
        issues.append("quantization label is required (e.g. Q4_K_M)")
    return issues
