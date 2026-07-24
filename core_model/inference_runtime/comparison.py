"""Structural comparison between a placeholder response and a model
response — never a quality judgment, only bounded structural facts."""

from __future__ import annotations

from typing import Any


def compare_placeholder_and_model(placeholder_text: str, model_text: str) -> dict[str, Any]:
    return {
        "placeholder_non_empty": bool(placeholder_text.strip()),
        "model_non_empty": bool(model_text.strip()),
        "placeholder_length": len(placeholder_text),
        "model_length": len(model_text),
        "identical": placeholder_text == model_text,
    }
