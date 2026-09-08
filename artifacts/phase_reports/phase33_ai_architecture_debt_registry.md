# Phase 33 — AI Architecture Debt Registry

| ID | Severity | File | Function / Class | Problem | Evidence | Impact | Recommendation |
|----|----------|------|------------------|---------|----------|--------|----------------|
| `DEBT-AI-1` | **Low** | [`backend/services/mini_brain_llm_adapter.py`](file:///home/dhurai/Projects/brud-ai/backend/services/mini_brain_llm_adapter.py#L117) | `LlamaCppMiniBrainAdapter.is_available()` | GGUF model binary file is absent in production repo root by default. | `resolved_model_path()` returns `None` unless `.gguf` path is provided in `settings.allowed_model_dir`. | Local GGUF inference requires placing a `.gguf` file in `allowed_model_dir`. | Document model path configuration in deployment documentation. |
| `DEBT-AI-2` | **Info** | [`backend/services/mini_brain_llm_adapter.py`](file:///home/dhurai/Projects/brud-ai/backend/services/mini_brain_llm_adapter.py#L166) | `MockMiniBrainAdapter` | Canned response adapter used in unit tests. | `MockMiniBrainAdapter` returns hash-seeded Tamil/English responses. | Used strictly for test isolation and dry-run verification. | Keep mock provider isolated for test seams. |
