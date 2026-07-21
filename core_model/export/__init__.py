"""Model export interface."""


class ModelExporter:
    """Will export verified model artifacts with metadata and compatibility checks."""

    def export(self) -> None:
        """Export a model artifact in a future model-development phase."""

        raise NotImplementedError("Model export is not available in Phase 1")
