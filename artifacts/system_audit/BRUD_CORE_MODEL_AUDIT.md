# BRUD AI — CORE MODEL AUDIT (WS04)
**Audit Date:** 2026-09-07

---

## ARCHITECTURE MODULE

### `core_model/architecture/` (9 files)

| File | Class/Function | Status | Notes |
|------|----------------|--------|-------|
| `config.py` | BrudModelConfig (dataclass) | ACTIVE | Validated transformer config |
| `model.py` | BrudModel | ACTIVE | Top-level transformer |
| `attention.py` | BrudAttention | ACTIVE | Multi-head attention with RoPE |
| `transformer_block.py` | BrudTransformerBlock | ACTIVE | Decoder block |
| `embeddings.py` | BrudEmbeddings | ACTIVE | Token + position embeddings |
| `feed_forward.py` | BrudFeedForward | ACTIVE | FFN with SwiGLU |
| `rope.py` | RotaryEmbedding | ACTIVE | RoPE implementation |
| `outputs.py` | BrudModelOutput | ACTIVE | Output dataclass |
| `brud_small_v2.py` | BRUD_SMALL_V2_CONFIG | ACTIVE | Preset config for BrudSmallV2 |

**Model Architecture:** Decoder-only Transformer (Llama-style)
- GQA: Phase 8 note: "Phase 8 supports standard MHA: key/value heads must match heads"
- RoPE positional encoding
- SwiGLU FFN
- RMSNorm

---

## INFERENCE RUNTIME

### `core_model/inference_runtime/` (12 files)

| File | Status | Purpose |
|------|--------|---------|
| `model_loader.py` | ACTIVE | Model loading + verification |
| `generation_engine.py` | ACTIVE | Bounded text generation loop |
| `generation_config.py` | ACTIVE | Generation hyperparameters |
| `runtime_config.py` | ACTIVE | Runtime profile validation |
| `runtime_health.py` | ACTIVE | Health aggregation |
| `resource_guard.py` | ACTIVE | CPU/memory resource assessment |
| `context_builder.py` | ACTIVE | Context window construction |
| `fallback.py` | ACTIVE | Fallback policy |
| `assignment_policy.py` | ACTIVE | Model assignment policy |
| `canary.py` | ACTIVE | Canary deployment |
| `comparison.py` | ACTIVE | Model comparison |
| `manifest.py` | ACTIVE | Manifest reading |

### `core_model/inference/` (1 file)
- `__init__.py` — empty — **DEAD** — vestigial module

---

## MODEL PROVIDERS

### Phase 15 — Brud Core Model (Local Inference)
- Entry: `InferenceRuntimeService` (`backend/services/inference_runtime_service.py`)
- Loads `BrudModel` from checkpoint via `model_loader.py`
- Uses `generation_engine.py` for bounded generation
- Status: **ACTIVE** — full implementation

### MB-28 — Mini Brain LLM Adapter (External/Local)
- Entry: `MiniBrainLlmRuntimeService`
- Uses `MiniBrainLlmAdapterProtocol` with implementations:
  - `LlamaCppMiniBrainAdapter` — local llama.cpp inference
  - `ExternalProviderMiniBrainAdapter` — OpenAI/Anthropic/Gemini/OpenRouter
  - `MockMiniBrainAdapter` — test mock
- Status: **ACTIVE** — parallel system

### Provider Connection Adapters (provider_settings_connection_adapters.py)
| Adapter | Status |
|---------|--------|
| OpenAiConnectionAdapter | ACTIVE |
| AnthropicConnectionAdapter | ACTIVE |
| GeminiConnectionAdapter | ACTIVE |
| OpenRouterConnectionAdapter | ACTIVE |
| LocalLlmConnectionAdapter | ACTIVE |
| LocalBackendConnectionAdapter | ACTIVE |
| MockConnectionAdapter | ACTIVE (test) |

---

## TRAINING PIPELINE

### Pre-training
- `backend/services/pretraining_service.py` (74 KB) — ACTIVE
- `backend/services/base_training_service.py` (50 KB) — ACTIVE
- `core_model/training/` — training loops

### Instruction Tuning
- `backend/services/instruction_tuning_service.py` (74 KB) — ACTIVE

### Incremental Training
- `backend/services/incremental_training_*` — multiple services — ACTIVE

### Tokenizer
- `core_model/tokenizer/` — custom tokenizer — ACTIVE
- `backend/services/tokenizer_registry.py` (51 KB) — ACTIVE

---

## MODEL CHECKPOINT MANAGEMENT

- `core_model/checkpoints/` — 7 files — ACTIVE
- `backend/services/core_model_service.py` (38 KB) — ACTIVE
- `artifacts/` — multiple phase checkpoint directories — ACTIVE

---

## RUNTIME PATH ANALYSIS

**Single Authoritative Brud Model Inference Path:**
```
InferenceRuntimeService.generate()
    ↓
_LOADED_MODELS cache check (in-process dict)
    ↓
model_loader.py → BrudModel.forward()
    ↓
generation_engine.py bounded loop
    ↓
TokenizerService.decode()
    ↓
Response text
```

**Alternative Path (MB-28):**
```
MiniBrainLlmRuntimeService.chat()
    ↓
MiniBrainLlmAdapterProtocol.generate()
    ↓ [LlamaCpp | ExternalProvider | Mock]
Response text
```

---

## FINDINGS

1. **COMPLETE:** Transformer architecture fully implemented (BrudSmallV2)
2. **COMPLETE:** Local inference runtime fully implemented
3. **COMPLETE:** Tokenizer system fully implemented
4. **ACTIVE:** Training pipelines (pretraining, SFT, incremental)
5. **DUAL RUNTIME:** Both Brud core inference AND MB-28 LLM adapter exist as separate paths — architectural choice, not bug, but requires documentation
6. **DEAD:** `core_model/inference/` — empty, vestigial

---
*WS04 Complete*
