"""MB-29: Model Scanner -- real, read-only, confined directory listing
for `.gguf`/`.GGUF` files. This is the second disclosed real-I/O
module in this package (see `__init__.py`) -- it only ever lists
filenames and stats (size, mtime) already known to be inside a
declared root; it never reads file content, never writes, never
executes a subprocess, never makes a network call.

Confinement is real, not cosmetic: every discovered path is fully
resolved (`Path.resolve()`, which follows symlinks) and then checked
with `Path.is_relative_to(root)` (genuine parent-path comparison) --
never `str.startswith()`, which a sibling directory sharing a name
prefix (e.g. `models_evil/` vs `models/`) would defeat. A file
discovered via a symlink that resolves outside the declared root is
silently skipped, not surfaced.

Family/quantization/parameter-count inference is pure filename
parsing (regex only, no I/O) -- best-effort and honestly disclosed as
such; an unrecognized filename shape yields `None` fields rather than
a guess presented as fact.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_QUANT_PATTERN = re.compile(r"(Q[2-8][_.](?:K[_.](?:[SML])|0)|F16|F32)", re.IGNORECASE)
_PARAMS_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*[bB](?:illion)?(?:[-_.]|$)")
_KNOWN_FAMILIES = (
    "qwen2.5", "qwen2", "qwen", "tinyllama", "smollm2", "smollm", "phi-3", "phi3",
    "mistral", "llama-3", "llama3", "llama-2", "llama2", "gemma2", "gemma",
)


def _infer_family(filename: str) -> str | None:
    lowered = filename.lower()
    for family in _KNOWN_FAMILIES:
        if family.replace("-", "").replace(".", "") in lowered.replace("-", "").replace(".", ""):
            return family
    return None


def _infer_quantization(filename: str) -> str | None:
    match = _QUANT_PATTERN.search(filename)
    if not match:
        return None
    return match.group(1).upper().replace(".", "_")


def _infer_params(filename: str) -> float | None:
    match = _PARAMS_PATTERN.search(filename)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _resolve_within_root(root: Path, candidate: Path) -> Path | None:
    try:
        resolved = candidate.resolve()
    except OSError:
        return None
    if not resolved.is_relative_to(root):
        return None
    return resolved


def scan_directory(root: Path) -> list[dict[str, Any]]:
    """Lists every real, confined `.gguf`/`.GGUF` file under `root`.
    `root` must already exist and be a real directory -- callers
    resolve and validate the root itself before calling this
    (mirrors `resolve_confined_model_path`'s own contract in
    `backend/services/mini_brain_llm_adapter.py`)."""
    resolved_root = root.resolve()
    if not resolved_root.is_dir():
        return []

    results: list[dict[str, Any]] = []
    for pattern in ("*.gguf", "*.GGUF"):
        for candidate in resolved_root.rglob(pattern):
            resolved = _resolve_within_root(resolved_root, candidate)
            if resolved is None or not resolved.is_file():
                continue
            try:
                stat = resolved.stat()
            except OSError:
                continue
            filename = resolved.name
            results.append({
                "filename": filename,
                "absolute_path": str(resolved),
                "size_gb": round(stat.st_size / (1024 ** 3), 3),
                "modified_at": stat.st_mtime,
                "inferred_family": _infer_family(filename),
                "inferred_quantization": _infer_quantization(filename),
                "inferred_params": _infer_params(filename),
            })

    # de-duplicate in case a case-insensitive filesystem matched both
    # glob patterns for the same real file
    seen: set[str] = set()
    deduped = []
    for entry in results:
        if entry["absolute_path"] in seen:
            continue
        seen.add(entry["absolute_path"])
        deduped.append(entry)
    return deduped
