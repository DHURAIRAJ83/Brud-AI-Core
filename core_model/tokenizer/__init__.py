"""Tokenizer interface for Tamil, English, Tanglish, and mixed-language text."""


class TokenizerManager:
    """Will configure, train, load, and validate the Brud tokenizer."""

    def build(self) -> None:
        """Build a tokenizer in a future model-development phase."""

        raise NotImplementedError("Tokenizer creation is not available in Phase 1")
