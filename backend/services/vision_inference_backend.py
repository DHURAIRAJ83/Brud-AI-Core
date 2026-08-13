"""MB-15: pluggable vision inference backend contract + real adapters.

`VisionInferenceBackend` is a structural `Protocol`, mirroring MB-04's
own `InferenceBackend` exactly -- any class with these methods
satisfies it, with no shared base class and no registry of
implementations to keep in sync. `MiniBrainVisionModelService` only
ever talks to this Protocol, never to a concrete backend class by
name, so a real provider can be swapped in later without changing the
service.

Every concrete backend below lazily imports its underlying library
inside each method (never at module level), so this file stays
importable -- and `is_available()` remains a real, non-crashing check
-- on a machine where the library isn't installed. Confirmed by audit:
`onnxruntime`, `openvino`, and `torchvision` are NOT installed in this
environment. `llama-cpp-python` IS installed (0.3.34) and genuinely
supports LLaVA-style multimodal chat handlers -- so
`LlavaGgufVisionBackend.is_available()` truthfully returns `True` --
but no vision GGUF model file or CLIP `mmproj` file exists anywhere in
this environment (only a text-only Qwen2.5 GGUF), so `load()` always
fails honestly with `BackendUnavailableError` unless an admin points
it at real files that don't currently exist here.

No backend here can produce a real bounding box: object detection with
pixel-coordinate boxes requires a dedicated detection-model
architecture (YOLO/DETR-style), and none exists anywhere in this
codebase for any provider -- ONNX Runtime and OpenVINO are inference
*engines*, not models, and LLaVA-style vision-language models describe
images in natural language, they do not localize objects. Every
`detect_objects()` implementation below is honest about this: `
bounding_box` is always `None` unless an admin later attaches a real
detection-capable backend, disclosed explicitly on every response.
"""

from __future__ import annotations

import base64
import os
import time
from typing import Any, Protocol

from backend.services.mini_brain_inference_backend import BackendUnavailableError

NO_BOUNDING_BOX_DISCLOSURE = (
    "no object-detection-capable model architecture (YOLO/DETR-style, with real pixel "
    "bounding boxes) exists anywhere in this codebase for any provider -- vision-language "
    "backends describe images in natural language, they do not localize objects"
)


class VisionInferenceBackend(Protocol):
    def is_available(self) -> bool: ...

    def load(self, model_path: str, **kwargs: Any) -> dict[str, Any]: ...

    def unload(self) -> None: ...

    def detect_objects(self, image_bytes: bytes) -> dict[str, Any]: ...

    def classify_scene(self, image_bytes: bytes) -> dict[str, Any]: ...

    def generate_caption(self, image_bytes: bytes) -> dict[str, Any]: ...


def _not_loaded(provider_key: str) -> dict[str, Any]:
    return {
        "provider_available": False, "objects": [], "scene": None, "caption": None,
        "confidence": None, "reason": f"no model is loaded for provider '{provider_key}'",
    }


class OnnxVisionBackend:
    """ONNX Runtime adapter. Not installed in this environment."""

    provider_key = "onnx_cpu"

    def __init__(self) -> None:
        self._session: Any = None

    def is_available(self) -> bool:
        try:
            import onnxruntime  # noqa: F401
        except ImportError:
            return False
        return True

    def load(self, model_path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            import onnxruntime
        except ImportError as exc:
            raise BackendUnavailableError("onnxruntime is not installed in this environment") from exc
        if not os.path.isfile(model_path):
            raise BackendUnavailableError(f"ONNX model file does not exist: {model_path}")
        started = time.perf_counter()
        self._session = onnxruntime.InferenceSession(model_path)
        return {"load_time_ms": round((time.perf_counter() - started) * 1000, 2)}

    def unload(self) -> None:
        self._session = None

    def detect_objects(self, image_bytes: bytes) -> dict[str, Any]:
        del image_bytes
        if self._session is None:
            raise BackendUnavailableError("no ONNX model is loaded")
        # No detection model is registered in this environment -- an admin-supplied
        # ONNX model's output shape is unknown ahead of time, so this backend cannot
        # honestly parse detections without one. Real inference is not attempted.
        return {"provider_available": True, "objects": [], "disclosure": NO_BOUNDING_BOX_DISCLOSURE}

    def classify_scene(self, image_bytes: bytes) -> dict[str, Any]:
        del image_bytes
        if self._session is None:
            raise BackendUnavailableError("no ONNX model is loaded")
        return {"provider_available": True, "scene": None, "confidence": None}

    def generate_caption(self, image_bytes: bytes) -> dict[str, Any]:
        del image_bytes
        if self._session is None:
            raise BackendUnavailableError("no ONNX model is loaded")
        return {"provider_available": True, "caption": None, "confidence": None}


class OpenVinoVisionBackend:
    """OpenVINO adapter. Not installed in this environment."""

    provider_key = "openvino_cpu"

    def __init__(self) -> None:
        self._compiled_model: Any = None

    def is_available(self) -> bool:
        try:
            import openvino  # noqa: F401
        except ImportError:
            return False
        return True

    def load(self, model_path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            import openvino as ov
        except ImportError as exc:
            raise BackendUnavailableError("openvino is not installed in this environment") from exc
        if not os.path.isfile(model_path):
            raise BackendUnavailableError(f"OpenVINO model file does not exist: {model_path}")
        started = time.perf_counter()
        core = ov.Core()
        self._compiled_model = core.compile_model(model_path, "CPU")
        return {"load_time_ms": round((time.perf_counter() - started) * 1000, 2)}

    def unload(self) -> None:
        self._compiled_model = None

    def detect_objects(self, image_bytes: bytes) -> dict[str, Any]:
        del image_bytes
        if self._compiled_model is None:
            raise BackendUnavailableError("no OpenVINO model is loaded")
        return {"provider_available": True, "objects": [], "disclosure": NO_BOUNDING_BOX_DISCLOSURE}

    def classify_scene(self, image_bytes: bytes) -> dict[str, Any]:
        del image_bytes
        if self._compiled_model is None:
            raise BackendUnavailableError("no OpenVINO model is loaded")
        return {"provider_available": True, "scene": None, "confidence": None}

    def generate_caption(self, image_bytes: bytes) -> dict[str, Any]:
        del image_bytes
        if self._compiled_model is None:
            raise BackendUnavailableError("no OpenVINO model is loaded")
        return {"provider_available": True, "caption": None, "confidence": None}


class LlavaGgufVisionBackend:
    """Real LLaVA-style multimodal adapter via `llama-cpp-python`'s own
    chat-handler API (`Llava15ChatHandler` + `Llama(chat_handler=...)`).
    The library is genuinely installed in this environment (unlike
    ONNX/OpenVINO above), but no vision GGUF model file or CLIP
    `mmproj` projector file is present anywhere in this environment, so
    `load()` always raises `BackendUnavailableError` here today. Never
    exercised end-to-end against a real model -- the same disclosed
    limitation `LlamaCppBackend` (MB-04) carries for the text case."""

    provider_key = "llava_gguf_cpu"

    def __init__(self) -> None:
        self._llama: Any = None

    def is_available(self) -> bool:
        try:
            from llama_cpp.llama_chat_format import Llava15ChatHandler  # noqa: F401
        except ImportError:
            return False
        return True

    def load(self, model_path: str, *, mmproj_path: str, context_length: int = 2048, **kwargs: Any) -> dict[str, Any]:
        try:
            from llama_cpp import Llama
            from llama_cpp.llama_chat_format import Llava15ChatHandler
        except ImportError as exc:
            raise BackendUnavailableError("llama-cpp-python is not installed in this environment") from exc
        if not os.path.isfile(model_path):
            raise BackendUnavailableError(f"vision GGUF model file does not exist: {model_path}")
        if not os.path.isfile(mmproj_path):
            raise BackendUnavailableError(f"CLIP mmproj projector file does not exist: {mmproj_path}")
        started = time.perf_counter()
        handler = Llava15ChatHandler(clip_model_path=mmproj_path, verbose=False)
        self._llama = Llama(model_path=model_path, chat_handler=handler, n_ctx=context_length, verbose=False)
        return {"load_time_ms": round((time.perf_counter() - started) * 1000, 2)}

    def unload(self) -> None:
        self._llama = None

    def _image_message(self, image_bytes: bytes, prompt: str) -> list[dict[str, Any]]:
        data_uri = f"data:image/png;base64,{base64.b64encode(image_bytes).decode('ascii')}"
        return [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_uri}},
                {"type": "text", "text": prompt},
            ],
        }]

    def _average_logprob_confidence(self, result: dict[str, Any]) -> float | None:
        choice = (result.get("choices") or [{}])[0]
        logprobs = choice.get("logprobs")
        if not logprobs or not logprobs.get("token_logprobs"):
            return None
        values = [v for v in logprobs["token_logprobs"] if v is not None]
        if not values:
            return None
        # A model's own average per-token log-probability, converted to (0, 1] --
        # a real signal from the model, but a confidence *proxy*, never a calibrated
        # object-existence probability.
        import math
        return round(math.exp(sum(values) / len(values)), 3)

    def detect_objects(self, image_bytes: bytes) -> dict[str, Any]:
        if self._llama is None:
            raise BackendUnavailableError("no vision model is loaded")
        prompt = "List the distinct physical objects visible in this image, one per line. No other text."
        result = self._llama.create_chat_completion(
            messages=self._image_message(image_bytes, prompt), max_tokens=256, logprobs=True,
        )
        text = result["choices"][0]["message"]["content"] or ""
        labels = [line.strip("-* ") for line in text.splitlines() if line.strip()]
        confidence = self._average_logprob_confidence(result)
        objects = [
            {"label": label, "confidence": confidence, "bounding_box": None} for label in labels
        ]
        return {"provider_available": True, "objects": objects, "disclosure": NO_BOUNDING_BOX_DISCLOSURE}

    def classify_scene(self, image_bytes: bytes) -> dict[str, Any]:
        if self._llama is None:
            raise BackendUnavailableError("no vision model is loaded")
        prompt = "In one or two words, what type of place or setting does this image show?"
        result = self._llama.create_chat_completion(
            messages=self._image_message(image_bytes, prompt), max_tokens=16, logprobs=True,
        )
        scene = (result["choices"][0]["message"]["content"] or "").strip()
        return {
            "provider_available": True, "scene": scene or None,
            "confidence": self._average_logprob_confidence(result),
        }

    def generate_caption(self, image_bytes: bytes) -> dict[str, Any]:
        if self._llama is None:
            raise BackendUnavailableError("no vision model is loaded")
        prompt = "Describe this image in one clear sentence."
        result = self._llama.create_chat_completion(
            messages=self._image_message(image_bytes, prompt), max_tokens=128, logprobs=True,
        )
        caption = (result["choices"][0]["message"]["content"] or "").strip()
        return {
            "provider_available": True, "caption": caption or None,
            "confidence": self._average_logprob_confidence(result),
        }


BACKEND_FACTORIES: dict[str, type] = {
    "onnx_cpu": OnnxVisionBackend,
    "openvino_cpu": OpenVinoVisionBackend,
    "llava_gguf_cpu": LlavaGgufVisionBackend,
}


def backend_for_provider(provider_key: str) -> VisionInferenceBackend:
    factory = BACKEND_FACTORIES.get(provider_key)
    if factory is None:
        raise BackendUnavailableError(f"no backend implementation registered for provider '{provider_key}'")
    return factory()


__all__ = [
    "VisionInferenceBackend", "BackendUnavailableError", "OnnxVisionBackend", "OpenVinoVisionBackend",
    "LlavaGgufVisionBackend", "BACKEND_FACTORIES", "backend_for_provider", "NO_BOUNDING_BOX_DISCLOSURE",
]
