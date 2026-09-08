# Phase 34 — Architecture Debt Registry

| ID | Severity | File | Function / Class | Problem | Evidence | Status | Recommendation |
|----|----------|------|------------------|---------|----------|--------|----------------|
| `DEBT-AI-1` | **Low** | [`backend/services/mini_brain_llm_adapter.py`](file:///home/dhurai/Projects/brud-ai/backend/services/mini_brain_llm_adapter.py#L117) | `LlamaCppMiniBrainAdapter.is_available()` | Local `.gguf` model binary file is absent by default in repository root. | `resolved_model_path()` returns `None` unless `.gguf` file is placed in `allowed_model_dir`. | **MAINTAINED BY DESIGN** | Keep large model weight binaries outside Git repository. |
| `DEBT-AI-2` | **Info** | [`backend/services/mini_brain_llm_adapter.py`](file:///home/dhurai/Projects/brud-ai/backend/services/mini_brain_llm_adapter.py#L166) | `MockMiniBrainAdapter` | Canned response adapter used for unit test isolation. | `MockMiniBrainAdapter` returns hash-seeded responses. | **MAINTAINED BY DESIGN** | Retain mock adapter for isolated test seams. |
