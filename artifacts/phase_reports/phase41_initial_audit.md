# PHASE 41 INITIAL READ-ONLY BASELINE AUDIT REPORT

**Date:** 2026-08-29  
**Audit Role:** Principal ML Systems Engineer & Production Architecture Engineer  
**Git Branch:** `phase-5-performance-polish`  
**Git HEAD:** `df054cb100b58d99acf42a72d18dcbcb7dcbd5f8`  
**Git Stash:** `stash@{0}: On phase-5-performance-polish: Phase 7C-1 pilot: async->def conversion (inconclusive, not adopted)`  
**Audit Purpose:** Workstream 1 read-only baseline capture for Phase 41.  

---

## 1. Safety & Production Database Invariants

| Property | Measured Value | Target / Invariant | Status |
| :--- | :--- | :--- | :--- |
| **Database Path** | `/home/dhurai/Projects/brud-ai/data/database/brud_ai.db` | `data/database/brud_ai.db` | Verified |
| **Database SHA-256** | `34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729` | Exact Match | 100% Byte-Identical |
| **Database Size** | `11,096,064 bytes` | 11,096,064 bytes | 100% Byte-Identical |
| **WAL File** | None (`brud_ai.db-wal` does not exist) | Clean | Verified |
| **SHM File** | None (`brud_ai.db-shm` does not exist) | Clean | Verified |
| **Git Working Tree** | Clean tracked tree; stash@{0} intact | Untouched | Verified |

---

## 2. Hardware Resource Baseline

| Resource Dimension | Measured Capacity | Operating Constraint for Training |
| :--- | :--- | :--- |
| **CPU Architecture** | x86_64, GenuineIntel Pentium G2030 @ 3.00GHz | 2 Physical Cores (No AVX/AVX2) |
| **Concurrency Ceiling** | 2 Threads (`num_threads=2`) | Strict CPU core bounding |
| **Total System RAM** | 11 GiB (11,885,028 KiB) | Bounded micro-batch memory |
| **Available RAM** | ~5.9 GiB (6,183,936 KiB) | Safe working memory headroom |
| **Swap Space** | 5.9 GiB total (~4.3 GiB free) | Emergency safety margin |
| **Root Disk Available**| 107 GiB (323G used / 452G total, 76%) | >50 GiB available for checkpoints |
| **Execution Precision**| FP32 CPU fallback | Safe CPU execution |

---

## 3. Subsystem Readiness & Artifact Audit

### A. Pretraining Engine & Checkpointing
- **Pretrainer:** `SovereignPretrainer` (`core_model/training/sovereign_pretrainer.py`)
  - Supports AdamW optimizer, Cosine Annealing learning rate schedule, gradient accumulation, and held-out validation.
- **Checkpoint Manager:** `TrainingCheckpointManager` (`core_model/checkpoints/training_checkpoint.py`)
  - Validates `model_state.pt`, `optimizer_state.pt`, `scheduler_state.pt`, `rng_state.pt`, `trainer_state.json`, `config.json`, `references.json`.
  - Rejects corruption via SHA-256 manifests.
  - Supports clean resumption of weights, optimizer buffers, and step counters.

### B. Ingestion & Dataset Registry
- **Pipeline:** `ProductionIngestionPipeline` (`core_model/corpus/production_ingestion_pipeline.py`)
  - Streaming chunked JSONL processing without in-memory bloat.
  - Unicode NFC normalization, PII masking, secret quarantine, and prompt injection isolation (`assess_context_item_injection`).
  - Zero leakage policy: strictly excludes held-out benchmark fixtures (`TAMIL_SENTENCES`, `ENGLISH_SENTENCES`, `TANGLISH_SENTENCES`).
  - Deterministic 80% TRAIN / 10% VAL / 10% TEST splitting.

### C. Tokenizer Registry
- **Engine:** `SovereignTokenizerTrainer` (`core_model/tokenizer/sovereign_tokenizer_trainer.py`)
  - SentencePiece BPE model with target ~32,000 vocabulary.
  - Core special tokens: `<pad>` (0), `<unk>` (1), `<bos>` (2), `<eos>` (3).
  - Role symbols: `<system>`, `<user>`, `<assistant>`.
  - Thread concurrency bounded to 2 cores.
  - Manifest generation with SHA-256 digests.

### D. Model Architecture
- **Model Preset:** `production_preset(vocabulary_size)` in [`core_model/architecture/config.py`](file:///home/dhurai/Projects/brud-ai/core_model/architecture/config.py)
  - 1,024 context length, 512 hidden dimension, 1,536 intermediate dimension, 8 hidden layers, 8 attention heads, 8 key/value heads.
  - RoPE ($\theta=10,000$), RMSNorm ($\epsilon=10^{-6}$), SwiGLU activations, FP32 CPU precision.

### E. Evaluation & Canary Governance
- **Evaluation Engine:** `Phase40Evaluator` (`core_model/evaluation/phase40_evaluator.py`)
  - Multi-dimensional assessment: Tamil, English, Tanglish (Tamil-first policy), 8 deterministic reasoning dimensions, RAG security, memory isolation, and AST static security.
- **Canary Manager:** `CanaryManager` (`core_model/release/canary_manager.py`)
  - 9-stage lifecycle (`TRAINING` $\rightarrow$ `CANDIDATE` $\rightarrow$ `OFFLINE_EVAL` $\rightarrow$ `QUALITY_GATES` $\rightarrow$ `ADMIN_REVIEW` $\rightarrow$ `CANARY` $\rightarrow$ `CANARY_EVAL` $\rightarrow$ `GOVERNANCE_APPROVAL` $\rightarrow$ `PRODUCTION_RELEASE`).
  - 0.0% default traffic; isolated from Public Chat.
  - Atomic non-destructive rollback.

---

## 4. Verified Test Baseline

| Test Suite | Test Count | Status |
| :--- | :--- | :--- |
| `tests/evaluation/test_phase40_sovereign_production_pretraining.py` | 40 / 40 | **PASSED** |
| `tests/evaluation/test_phase39_sovereign_training.py` | 18 / 18 | **PASSED** |
| `tests/evaluation/test_phase38_model_quality.py` | 17 / 17 | **PASSED** |
| `tests/evaluation/test_full_system_verification.py` | 16 / 16 | **PASSED** |
| **Total Regressions** | **0** | **ALL GREEN** |

---

## 5. Phase 41 Identified Gaps & Target Scope

1. **Continuous Pretraining Execution:** Execute long-duration, resumable pretraining runs on sovereign bilingual text, recording real step telemetry, rolling train loss, and held-out validation loss.
2. **True Convergence Tracking:** Monitor loss trends over extended step sequences, guarding against overfitting and train/val divergence.
3. **Model Capability Deep-Dive:** Evaluate factual question answering, false premise handling, and deterministic multi-step reasoning.
4. **Controlled Canary Traffic Staging:** Maintain 0% default traffic in CANARY stage, requiring explicit administrative sign-off before any traffic ramp.
5. **Zero Mutation of Production Database:** Guarantee that `brud_ai.db` remains 100% byte-identical throughout all operations.
