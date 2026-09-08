# Phase 33 — Model Provider Audit Report

## 1. Provider Inventory & Matrix

| Provider | Adapter Class | Registry | Routing | Real Inference Code | Config | Error Handling | Status |
|----------|---------------|----------|---------|---------------------|--------|----------------|--------|
| **Brud Causal LM (PyTorch)** | `InferenceRuntimeService` | `ModelReleaseRepository` | `ModelAssignmentService` | `BrudForCausalLM` / `run_bounded_generation()` | `BrudModelConfig` | Exception safe / rollback | **REAL** (Requires checkpoint assignment) |
| **LlamaCpp** | `LlamaCppMiniBrainAdapter` | `MiniBrainProviderSettingsService` | `RuntimeManagerService` | `llama_cpp.Llama` | `allowed_model_dir` | Exception safe / fallback | **REAL** (Requires `.gguf` file) |
| **OpenAI** | `ExternalProviderMiniBrainAdapter` | `MiniBrainProviderSettingsService` | `RuntimeManagerService` | HTTP (`httpx`) to OpenAI API | `api_key` | Timeout / HTTP status error | **REAL** (Requires API Key) |
| **Anthropic** | `ExternalProviderMiniBrainAdapter` | `MiniBrainProviderSettingsService` | `RuntimeManagerService` | HTTP (`httpx`) to Anthropic API | `api_key` | Timeout / HTTP status error | **REAL** (Requires API Key) |
| **Gemini** | `ExternalProviderMiniBrainAdapter` | `MiniBrainProviderSettingsService` | `RuntimeManagerService` | HTTP (`httpx`) to Gemini API | `api_key` | Timeout / HTTP status error | **REAL** (Requires API Key) |
| **OpenRouter** | `ExternalProviderMiniBrainAdapter` | `MiniBrainProviderSettingsService` | `RuntimeManagerService` | HTTP (`httpx`) to OpenRouter API | `api_key` | Timeout / HTTP status error | **REAL** (Requires API Key) |
| **Mock Provider** | `MockMiniBrainAdapter` | Seam only | Test Seam | Deterministic canned responses | N/A | Always available | **MOCK** (Test coverage only) |

---

## 2. Detailed Ollama & Mini Brain LLM Findings
- **Ollama Integration**: Not configured as a standalone service endpoint; integrated via llama-cpp-python and GGUF model loading in `LlamaCppMiniBrainAdapter`.
- **Brud Mini LLM Integration**: Fully wired via `MiniBrainLlmRuntimeService` and `RuntimeManagerService` (`backend/services/runtime_manager_service.py`).
- **CPU Optimization**: `LlamaCppMiniBrainAdapter` defaults to `threads=4`, `context_length=2048`, `temperature=0.3`. CPU memory guards assess `/proc/meminfo` dynamically via `_read_available_memory_bytes()`.
