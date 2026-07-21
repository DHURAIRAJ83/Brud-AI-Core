"""Model inference interface."""


class InferenceEngine:
    """Will load a registered model and generate validated multilingual responses."""

    def generate(self, prompt: str) -> str:
        """Generate model output in a future phase; no fake output is returned."""

        raise NotImplementedError("Model inference is not available in Phase 1")
