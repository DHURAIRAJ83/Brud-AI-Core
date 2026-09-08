"""Legacy Phase 1 model inference interface.

NOTE: This is a historical Phase 1 contractual stub preserved for
backward compatibility with `core_model.__init__` and `test_imports.py`.
The CANONICAL production inference runtime is located in:
`core_model.inference_runtime` and `backend.services.inference_runtime_service`.
"""


class InferenceEngine:
    """Historical Phase 1 interface preserved for contract compatibility."""

    def generate(self, prompt: str) -> str:
        """Raises NotImplementedError per Phase 1 contract -- use core_model.inference_runtime for live inference."""
        raise NotImplementedError("Model inference is not available in Phase 1 -- use core_model.inference_runtime")
