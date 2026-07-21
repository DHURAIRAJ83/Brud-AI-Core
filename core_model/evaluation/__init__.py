"""Model evaluation interface."""


class ModelEvaluator:
    """Will score model quality across Tamil, English, Tanglish, and mixed inputs."""

    def evaluate(self) -> None:
        """Run an evaluation suite in a future model-development phase."""

        raise NotImplementedError("Model evaluation is not available in Phase 1")
