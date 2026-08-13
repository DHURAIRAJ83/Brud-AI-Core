"""MB-30: Model Catalog -- pure, but the one module in this package
the phase spec itself names as the exception permitted to hold static
download metadata (a URL is just a string constant here; the actual
HTTP GET happens entirely in the service layer).

Post-audit remediation (2026-08-09): all three `sha256`/
`expected_size_bytes` values below are now the real, published LFS
digests, fetched directly from each repo's own Hugging Face API
(`https://huggingface.co/api/models/<repo>?blobs=true`, the file's
`lfs.sha256`/`lfs.size` fields) and independently cross-checked via a
second, separate raw HTTP fetch before being written here -- not
downloaded-and-hashed locally (still consistent with "never download a
model automatically"), but these are the real digests the file at each
`download_url` will genuinely hash to, not placeholders. Each entry's
own comment carries the exact source URL and verification date so a
future re-check knows exactly what to re-fetch.

MB-31A (2026-08-09): added Qwen2.5-0.5B-Instruct-Q4_K_M for genuinely
low-RAM machines (below the 1.5B model's real load-time footprint).
Its digest/size were verified the same way as the three entries above,
plus a second independent cross-check against the `resolve/main` URL's
own `x-linked-etag`/`x-linked-size` headers (not just the API's
`?blobs=true` response) -- both agree exactly. `tier` stays "optional";
the single Runtime-Manager-level `recommended_model_id()` pick is left
untouched (still Qwen2.5-1.5B) -- this entry only changes which models
a genuinely RAM-constrained machine has available to actually load.
"""

from __future__ import annotations

from typing import Any

CATALOG: dict[str, dict[str, Any]] = {
    "qwen2.5-1.5b-instruct-q4_k_m": {
        "display_name": "Qwen2.5-1.5B-Instruct-Q4_K_M",
        "family": "qwen2.5",
        "quantization": "Q4_K_M",
        "file_name": "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "download_url": "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        # Source: https://huggingface.co/api/models/Qwen/Qwen2.5-1.5B-Instruct-GGUF?blobs=true
        # (lfs.sha256 for qwen2.5-1.5b-instruct-q4_k_m.gguf) -- verified 2026-08-09.
        "sha256": "6a1a2eb6d15622bf3c96857206351ba97e1af16c30d7a74ee38970e434e9407e",
        "expected_size_bytes": 1_117_320_736,
        "recommended_ram_gb": 6,
        "expected_ram_usage_gb": 2.5,  # matches MB-29's own curated real-world figure for this exact model
        "tamil_support": "good",
        "speed_tier": "excellent",
        "tier": "recommended",
    },
    "tinyllama-1.1b-chat-q4_k_m": {
        "display_name": "TinyLlama-1.1B-Chat-Q4_K_M",
        "family": "tinyllama",
        "quantization": "Q4_K_M",
        "file_name": "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        "download_url": "https://huggingface.co/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF/resolve/main/tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf",
        # Source: https://huggingface.co/api/models/TheBloke/TinyLlama-1.1B-Chat-v1.0-GGUF?blobs=true
        # (lfs.sha256 for tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf) -- verified 2026-08-09.
        "sha256": "9fecc3b3cd76bba89d504f29b616eedf7da85b96540e490ca5824d3f7d2776a0",
        "expected_size_bytes": 668_788_096,
        "recommended_ram_gb": 4,
        "expected_ram_usage_gb": 1.2,
        "tamil_support": "limited",
        "speed_tier": "excellent",
        "tier": "optional",
    },
    "qwen2.5-3b-instruct-q4_k_m": {
        "display_name": "Qwen2.5-3B-Instruct-Q4_K_M",
        "family": "qwen2.5",
        "quantization": "Q4_K_M",
        "file_name": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "download_url": "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        # Source: https://huggingface.co/api/models/Qwen/Qwen2.5-3B-Instruct-GGUF?blobs=true
        # (lfs.sha256 for qwen2.5-3b-instruct-q4_k_m.gguf) -- verified 2026-08-09.
        "sha256": "626b4a6678b86442240e33df819e00132d3ba7dddfe1cdc4fbb18e0a9615c62d",
        "expected_size_bytes": 2_104_932_768,
        "recommended_ram_gb": 8,
        "expected_ram_usage_gb": 3.5,
        "tamil_support": "good",
        "speed_tier": "good",
        "tier": "optional",
    },
    "qwen2.5-0.5b-instruct-q4_k_m": {
        "display_name": "Qwen2.5-0.5B-Instruct-Q4_K_M",
        "family": "qwen2.5",
        "quantization": "Q4_K_M",
        "file_name": "qwen2.5-0.5b-instruct-q4_k_m.gguf",
        "download_url": "https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF/resolve/main/qwen2.5-0.5b-instruct-q4_k_m.gguf",
        # Source: https://huggingface.co/api/models/Qwen/Qwen2.5-0.5B-Instruct-GGUF?blobs=true
        # (lfs.sha256 for qwen2.5-0.5b-instruct-q4_k_m.gguf) -- verified 2026-08-09,
        # cross-checked against the resolve URL's x-linked-etag/x-linked-size headers.
        "sha256": "74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db",
        "expected_size_bytes": 491_400_032,
        "recommended_ram_gb": 4,
        "expected_ram_usage_gb": 1.0,  # curated: smaller footprint than TinyLlama's 1.2GB
        "tamil_support": "fair",
        "speed_tier": "excellent",
        "tier": "optional",
    },
}


def known_model_ids() -> tuple[str, ...]:
    return tuple(CATALOG.keys())


def catalog_entry(model_id: str) -> dict[str, Any] | None:
    return CATALOG.get(model_id)


def is_known_model(model_id: str) -> bool:
    return model_id in CATALOG


def recommended_model_id() -> str:
    return next(model_id for model_id, entry in CATALOG.items() if entry["tier"] == "recommended")


def optional_model_ids() -> tuple[str, ...]:
    return tuple(model_id for model_id, entry in CATALOG.items() if entry["tier"] == "optional")


def full_catalog() -> dict[str, Any]:
    return {"models": [{"model_id": model_id, **entry} for model_id, entry in CATALOG.items()]}
