# PHASE 40 INITIAL READ-ONLY AUDIT REPORT

**Date:** 2026-08-29  
**Branch:** `phase-5-performance-polish`  
**Git HEAD:** `df054cb100b58d99acf42a72d18dcbcb7dcbd5f8`  
**Stash:** `stash@{0}: On phase-5-performance-polish: Phase 7C-1 pilot: async->def conversion (inconclusive, not adopted)`  
**Audit Purpose:** Workstream 1 read-only baseline capture before any Phase 40 modifications.  

---

## 1. Safety & Production Database Invariants

| Property | Value / Status | Verification Method |
| :--- | :--- | :--- |
| **Database Path** | `/home/dhurai/Projects/brud-ai/data/database/brud_ai.db` | Verified path existence |
| **Database SHA-256** | `34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729` | `sha256sum` checksum |
| **Database Size** | `11,096,064 bytes` | `stat -c "%s"` |
| **WAL File State** | Inactive / None (`brud_ai.db-wal` does not exist) | Direct directory listing |
| **SHM File State** | Inactive / None (`brud_ai.db-shm` does not exist) | Direct directory listing |
| **Write Status** | Read-only audit; 0 bytes modified | Strictly preserved |

---

## 2. Hardware & Resource Environment

| Resource | Capacity / Baseline | Headroom / Limit |
| :--- | :--- | :--- |
| **Total Memory (RAM)** | 12 GB | ~5.6 GB Available |
| **Swap Space** | 6.0 GB | Unused / Minimal |
| **CPU Cores** | 2 Physical Cores | Bound to single-process CPU execution |
| **Available Disk** | ~107 GB on root filesystem | >100 GB available for checkpoints |
| **Execution Precision** | CPU-compatible FP32 | Safe FP32 fallback preserved |

---

## 3. Architecture & Subsystem State

### A. Model Architecture & Active Deployment
- **Model Class:** `BrudForCausalLM` (`core_model/architecture/model.py`)
  - Features: RoPE (rotary positional embeddings), RMSNorm, SwiGLU activations, Multi-Head Attention.
- **Active Release Checkpoint:** `0.1.0-synthetic-test`
  - Parameters: 24,352 (2 layers, 32 hidden size, 2 heads, vocabulary 128, context length 64).
  - Status: Synthetic/untrained test checkpoint.
  - Public Chat: Unassigned (routes through safe fallback with `insufficient_evidence: true`).
  - Diagnostic Scope Isolation: Public chat resolver strictly blocks `admin_diagnostic` models.

### B. Ingestion & Dataset Registry
- **Corpus Modules:** Located in `core_model/corpus/`:
  - `exact_deduplication.py`, `near_deduplication.py`, `unicode_normalization.py`, `tamil_normalization.py`, `pii_detection.py`, `secret_detection.py`, `safety_filter.py`, `provenance.py`, `licence_policy.py`, `partitioning.py`.
- **Pretraining Dataset Pipeline:** `core_model/training/dataset_pipeline.py` provides deterministic token packing and train/val/test splitting.
- **Database Tables:** `corpus_sources`, `corpus_documents`, `dataset_records`, `dataset_versions`, `dataset_version_items`.

### C. Tokenizer Registry
- **Engine:** SentencePiece BPE (`backend/services/tokenizer_registry.py`).
- **Target Vocabulary:** ~32,000 tokens (SentencePiece BPE).
- **Special Tokens:** `<pad>`, `<bos>`, `<eos>`, `<unk>`, `<system>`, `<user>`, `<assistant>`.
- **Integrity Validation:** SHA-256 artifact manifest verification (`manifest.json`).

### D. Training Engine & Checkpointing
- **Trainer:** `core_model/training/trainer.py`
  - PyTorch forward pass, `torch.nn.CrossEntropyLoss`, backpropagation, `torch.optim.AdamW`, `CosineAnnealingLR`.
- **Checkpoint Manager:** `core_model/checkpoints/training_checkpoint.py` (`TrainingCheckpointManager`).
  - Supports periodic, latest, and best checkpoints with multi-file SHA-256 manifests.
  - Interruption and resume recovery tested.

### E. Inference Runtime & Safety
- **Generation Engine:** `run_bounded_generation()` (`core_model/inference_runtime/generation_engine.py`).
- **Resource Guard:** `assess_resource_guard()` (`core_model/inference_runtime/resource_guard.py`).
- **Injection Guard:** `assess_context_item_injection()` (`core_model/conversation/injection_guard.py`).
- **Memory Isolation:** Scoped by `conversation_id` in SQLite; strict isolation between sessions.
- **AST Security:** 0 occurrences of `eval`, `exec`, `subprocess`, `os.system`.

---

## 4. Phase 39 Verified Baseline & Remaining Limitations

### Phase 39 Verdict:
**B — VERIFIED WITH LIMITATIONS**

### Phase 39 Verified Properties:
1. Real PyTorch training loop and weight parameter mutation verified ($W_{t+1} \neq W_t$).
2. Checkpoint serialization, SHA-256 manifest verification, and clean state restoration verified.
3. Resource Guard dynamic memory bounds verified.
4. RAG injection quarantine and missing evidence refusal verified.
5. Scoped public chat assignment and admin diagnostic model isolation verified.
6. 16/16 Phase 39 dedicated tests passed.
7. Full regression suite (1,596/1,596 tests) passed.
8. Production database remained 100% byte-identical.

### Limitations Requiring Phase 40 Execution:
1. **Corpus Scale:** The production-scale sovereign corpus has not been ingested.
2. **Tokenizer:** The production ~32K SentencePiece tokenizer has not been trained on the expanded sovereign corpus.
3. **Model Configuration:** Target production configuration (`BrudModelConfig`: 512 hidden, 8 layers, 8 heads, 1024 context) has not been instantiated as a pretrained candidate.
4. **Pretraining Execution:** Genuine multi-epoch pretraining on sovereign text has not yet been executed at candidate scale.
5. **Quality Gates:** Tamil fluency, English fluency, and advanced reasoning remain at `WARN` status.
6. **Canary Qualification:** The candidate model has not undergone controlled canary staging and governance approval.

---

## 5. Phase 40 Mandatory Directives

1. Production database `data/database/brud_ai.db` must remain **100% byte-identical** (SHA-256 `34376318d92febf1dbbea10f5106220d37cfe6f0a1ab7b1489f0e01767d4f729`, size `11,096,064 bytes`).
2. Public Chat must continue rejecting models with `scope_key = "admin_diagnostic"`.
3. Candidate model must remain strictly non-public until explicit governance approval.
4. No fake mocks or simulated outputs: all training, loss reduction, and tokenization metrics must be genuine.
5. CPU resource limits must be enforced via `ResourceGuard` throughout all stages.
