"""MB-01: Brud Mini Brain runtime skeleton.

This is the "Independent Runtime" MB-01 requires -- it does not import
`InferenceRuntimeService`, does not touch `_LOADED_MODELS`, and does
not talk to Ollama or any other provider. It is intentionally a
lifecycle shell with no model behind it yet: `start()`/`stop()` only
move the stored `runtime_status` through the state machine in
`core_model.mini_brain.status`, and every "do the actual AI thing"
method raises `NotImplementedError` with a clear message rather than
faking a result.

Future model integration point: `run_inference()`,
`retrieve_knowledge()`, `recall_memory()`, `suggest()`, and
`provide_context()` below are the five seams a later phase implements
against -- their signatures are meant to stay stable while their
bodies change from "raise NotImplementedError" to real calls into a
small local model (or, for `provide_context()`, into MB-02's Brud
Context Interface once it exists).
"""

from __future__ import annotations

from typing import Any

from core_model.mini_brain.status import decide_health, is_valid_transition


class MiniBrainNotImplementedError(RuntimeError):
    """Raised by every placeholder interface -- MB-01 ships no model."""


class MiniBrainRuntime:
    """In-process representation of the Mini Brain runtime's lifecycle.
    Holds no model weights and starts no background process in MB-01;
    `status` here is the same string persisted to `mini_brain_settings.
    runtime_status` by the service layer."""

    def __init__(self, *, config: dict[str, Any]) -> None:
        self.config = config
        self.status = "stopped"

    def start(self) -> dict[str, Any]:
        """Startup validation + transition to `running`. There is no
        model to load in MB-01, so "starting" only validates
        configuration shape before flipping to `running`."""

        if not is_valid_transition(self.status, "starting"):
            raise MiniBrainNotImplementedError(
                f"cannot start runtime from status {self.status!r}"
            )
        self.status = "starting"
        if self.config.get("runtime_backend") != "none":
            self.status = "error"
            raise MiniBrainNotImplementedError(
                "MB-01 supports no runtime backend other than 'none'"
            )
        self.status = "running"
        return {"status": self.status, "model_loaded": False}

    def stop(self) -> dict[str, Any]:
        if not is_valid_transition(self.status, "stopping"):
            raise MiniBrainNotImplementedError(
                f"cannot stop runtime from status {self.status!r}"
            )
        self.status = "stopping"
        self.status = "stopped"
        return {"status": self.status}

    def health_check(self, *, enabled: bool) -> dict[str, Any]:
        return decide_health(
            enabled=enabled, runtime_status=self.status, config_valid=True
        )

    # -- future model integration seams (MB-01: not implemented) -----

    def run_inference(self, prompt: str) -> dict[str, Any]:
        raise MiniBrainNotImplementedError(
            "Mini Brain inference is not implemented in MB-01 (framework only)"
        )

    def provide_context(self, area: str) -> dict[str, Any]:
        """Future seam for MB-02's Brud Context Interface -- the
        provider that will tell Mini Brain what it needs to know about
        the Admin Dashboard, dataset rules, training workflow, and RAG
        workflow it is operating alongside. MB-01 ships no context
        source, so this stays a placeholder like the other four."""

        raise MiniBrainNotImplementedError(
            "Mini Brain context is not implemented in MB-01 (framework only)"
        )

    def retrieve_knowledge(self, query: str) -> dict[str, Any]:
        raise MiniBrainNotImplementedError(
            "Mini Brain knowledge retrieval is not implemented in MB-01 (framework only)"
        )

    def recall_memory(self, scope_key: str) -> dict[str, Any]:
        raise MiniBrainNotImplementedError(
            "Mini Brain memory is not implemented in MB-01 (framework only)"
        )

    def suggest(self, context: dict[str, Any]) -> dict[str, Any]:
        raise MiniBrainNotImplementedError(
            "Mini Brain suggestions are not implemented in MB-01 (framework only)"
        )
