"""Training orchestration interface."""


class ModelTrainer:
    """Will train reproducible checkpoints from approved, versioned datasets."""

    def train(self) -> None:
        """Start training in a future model-development phase."""

        raise NotImplementedError("Model training is not available in Phase 1")
