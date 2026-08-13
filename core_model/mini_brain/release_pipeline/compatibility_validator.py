"""MB-07: Compatibility Validation -- pure. Decides whether the
produced GGUF file is compatible with MB-04 Runtime, from a real
load-and-generate test the service layer already ran.

Honest scope: MB-04's Prompt Builder, Response Quality, and Capability
Engine components never inspect a model file directly -- they all call
`MiniBrainInMemoryModelLoader.generate_response()`, which is already
format-agnostic (it works the same way regardless of which GGUF file
is loaded underneath it). Those three components are therefore
reported `compatible_by_construction` with the reason stated, rather
than re-tested individually -- a second, redundant load-and-generate
test against the same loaded model would prove nothing additional.
"""

from __future__ import annotations

from typing import Any

_FORMAT_AGNOSTIC_COMPONENTS = {
    "prompt_builder": "constructs prompt text; never inspects model file internals",
    "response_quality": "scores already-generated text; never inspects model file internals",
    "capability_engine": "selects a generation strategy; calls the same Runtime interface regardless of model file",
}


def validate_compatibility(
    *,
    load_succeeded: bool,
    load_error: str | None,
    vocabulary_size_matches: bool,
    context_length_matches: bool,
    generation_smoke_test_passed: bool,
    generation_smoke_test_error: str | None,
) -> dict[str, Any]:
    components: dict[str, dict[str, Any]] = {
        "mb04_runtime": {
            "compatible": load_succeeded,
            "reason": load_error if not load_succeeded else "GGUF file loaded successfully via the Runtime's LlamaCppBackend",
        },
        "tokenizer": {
            "compatible": vocabulary_size_matches,
            "reason": "vocabulary size matches" if vocabulary_size_matches else "vocabulary size mismatch between GGUF file and configured tokenizer",
        },
        "context_window": {
            "compatible": context_length_matches,
            "reason": "context length matches" if context_length_matches else "context length mismatch between GGUF file and model config",
        },
        "generation_smoke_test": {
            "compatible": generation_smoke_test_passed,
            "reason": generation_smoke_test_error if not generation_smoke_test_passed else "a real generation call completed without error",
        },
    }
    for name, why in _FORMAT_AGNOSTIC_COMPONENTS.items():
        components[name] = {"compatible": True, "compatible_by_construction": True, "reason": why}

    overall_compatible = all(c["compatible"] for c in components.values())
    return {
        "status": "Compatible" if overall_compatible else "Incompatible",
        "components": components,
    }
