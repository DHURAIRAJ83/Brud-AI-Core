# Phase 36 — Model Quality, Capability & Benchmark Validation Report

## 1. Initial Read-Only Architecture & Component Audit Findings

| Component / Parameter | Discovery & Audit Finding | Source File / Implementation |
|-----------------------|---------------------------|------------------------------|
| **Active Production Model** | `BrudForCausalLM` / PyTorch decoder Transformer architecture | [`core_model/architecture/model.py`](file:///home/dhurai/Projects/brud-ai/core_model/architecture/model.py#L13) |
| **Model Architecture** | Decoder-only Transformer with RMSNorm, RoPE, and KV-head Attention | [`core_model/architecture/model.py`](file:///home/dhurai/Projects/brud-ai/core_model/architecture/model.py) |
| **Model Parameters** | Synthetic/test configuration: 24,352 parameters (32 hidden size, 2 layers, 2 heads) | [`core_model/architecture/config.py`](file:///home/dhurai/Projects/brud-ai/core_model/architecture/config.py) |
| **Model Checkpoint** | `TrainingCheckpointManager` verified model state dict | [`core_model/checkpoints/training_checkpoint.py`](file:///home/dhurai/Projects/brud-ai/core_model/checkpoints/training_checkpoint.py) |
| **Tokenizer** | SentencePiece processor / TokenizerService registry | [`backend/services/tokenizer_registry.py`](file:///home/dhurai/Projects/brud-ai/backend/services/tokenizer_registry.py) |
| **Vocabulary Size** | Default 128 / Dynamic SentencePiece vocabulary | [`core_model/architecture/config.py`](file:///home/dhurai/Projects/brud-ai/core_model/architecture/config.py) |
| **Context Length** | Default sequence length 64 tokens | [`core_model/architecture/config.py`](file:///home/dhurai/Projects/brud-ai/core_model/architecture/config.py) |
| **Maximum Generation Length** | Configurable via `max_new_tokens` (default 32–64 tokens) | [`core_model/inference_runtime/generation_engine.py`](file:///home/dhurai/Projects/brud-ai/core_model/inference_runtime/generation_engine.py#L63) |
| **Sampling Config** | `greedy` and `top_k_sampling` (temperature scaling, top_k filtering) | [`core_model/inference_runtime/generation_engine.py`](file:///home/dhurai/Projects/brud-ai/core_model/inference_runtime/generation_engine.py#L100) |
| **EOS Handling** | Explicit token check for `eos_token_id` terminating generation loop | [`core_model/inference_runtime/generation_engine.py`](file:///home/dhurai/Projects/brud-ai/core_model/inference_runtime/generation_engine.py#L112) |
| **Repetition Controls** | `forbidden_role_token_ids` checks avoiding role-token leakage | [`core_model/inference_runtime/generation_engine.py`](file:///home/dhurai/Projects/brud-ai/core_model/inference_runtime/generation_engine.py#L117) |
| **Language Policy** | Tamil-first answer language policy via `resolve_answer_language()` | [`core_model/public_chat/language_policy.py`](file:///home/dhurai/Projects/brud-ai/core_model/public_chat/language_policy.py#L33) |
| **Tanglish Normalization** | Tanglish -> Tamil normalization via `process_text()` in `core_model.nlp` | [`core_model/nlp/__init__.py`](file:///home/dhurai/Projects/brud-ai/core_model/nlp/__init__.py) |
| **RAG Integration** | Document retrieval & context injection guard via `assess_context_item_injection()` | [`core_model/conversation/injection_guard.py`](file:///home/dhurai/Projects/brud-ai/core_model/conversation/injection_guard.py) |
| **Memory Integration** | Session-mode conversation memory via `ConversationSessionService` | [`backend/services/conversation_session_service.py`](file:///home/dhurai/Projects/brud-ai/backend/services/conversation_session_service.py) |
| **Safety Filtering** | Input safety (`evaluate_input_safety()`) and Output safety (`evaluate_output_safety()`) | [`core_model/public_chat/input_safety.py`](file:///home/dhurai/Projects/brud-ai/core_model/public_chat/input_safety.py) |
| **Output Post-Processing** | Response language formatting & PII/Secret leakage detection | [`core_model/public_chat/output_safety.py`](file:///home/dhurai/Projects/brud-ai/core_model/public_chat/output_safety.py) |
| **Provenance / Tracing** | Public Chat routing events, request IDs, inference IDs, token usage logging | [`backend/services/public_chat_routing_service.py`](file:///home/dhurai/Projects/brud-ai/backend/services/public_chat_routing_service.py) |

---

## 2. Model Identity Verification Report

- **MODEL NAME**: `BrudForCausalLM`
- **MODEL VERSION**: `0.1.0-synthetic-test`
- **MODEL FORMAT**: PyTorch `nn.Module` state dict / SentencePiece tokenizer
- **MODEL PARAMETERS**: 24,352 parameters (2 layers, 32 hidden size, 2 heads)
- **MODEL CHECKPOINT**: `core_model/checkpoints/`
- **MODEL CHECKSUM**: SHA-256 dynamic state dict hash verified via `TrainingCheckpointManager`
- **TOKENIZER**: SentencePiece / TokenizerRegistry
- **VOCABULARY SIZE**: 128 tokens
- **CONTEXT LENGTH**: 64 tokens
- **MODEL SOURCE**: Synthesized in-process for test suite isolation
- **TRAINING STATUS**: **UNTRAINED / SYNTHETIC TEST CHECKPOINT**
- **TRAINING DATA STATUS**: None assigned in production database
- **ACTIVE RELEASE**: Unassigned in production DB (`model_releases` count = 0)
- **ACTIVE PROVIDER**: `LlamaCppMiniBrainAdapter` / PyTorch native fallback

> [!WARNING]
> **Model Classification**: The currently active local model checkpoint is a **randomly initialized / synthetic test model** used for pipeline verification. It is **NOT** a production-trained model and will not generate fluent natural language text until a trained model weight release is loaded into `model_releases` and activated in `inference_model_assignments`.

---

## 3. Evaluation Framework & Verification Results

### Dedicated Quality Test Suite
- Path: [`tests/evaluation/test_phase36_model_quality.py`](file:///home/dhurai/Projects/brud-ai/tests/evaluation/test_phase36_model_quality.py)
- Executed Tests: **10 / 10 PASSED** (3.69s)

### Combined Regression Suite
- Total Executed: **1,516 tests**
- **1,516 / 1,516 PASSED** (0 failures, 195.93s runtime)

### Baseline Database & Safety Verification
- Production DB Path: `data/database/brud_ai.db`
- SHA-256: `34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729` (**100% MATCH**)
- Size: `11,096,064 bytes` (**100% MATCH**)
- Autonomous Execution: **NONE**
