# Phase 34 — Model Artifact Audit Report

## 1. Artifact Strategy Analysis
- **Principle**: Source code repositories must remain separate from heavy model weight binaries.
- **Model Storage Root**: `settings.resolved_allowed_model_dir` / `settings.resolved_pretraining_dir`.
- **Confined Path Resolution**: [`backend/services/mini_brain_llm_adapter.py`](file:///home/dhurai/Projects/brud-ai/backend/services/mini_brain_llm_adapter.py#L58) enforces strict path confinement via `resolve_confined_model_path()` to prevent path traversal outside `allowed_model_dir`.

---

## 2. Checkpoint & Manifest Requirements
For PyTorch and LlamaCpp model weight loading, model artifacts require:
1. `checkpoint_dir` containing `model_state.pt`, `config.json`, `references.json`.
2. Checkpoint verification via SHA-256 manifest hash calculation.
3. Compatibility assessment via `assess_runtime_compatibility()`.
