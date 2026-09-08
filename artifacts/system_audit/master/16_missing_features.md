# Master Brud AI System Audit — 16: Missing Features & Architectural Gaps

**Audit Date:** 2026-09-01  
**Auditor:** Principal Technical Project Analyst  
**Confidence Rating:** HIGH CONFIDENCE (Verified by absence in source code and filesystem)  

---

## 1. Missing Architectural Features

### 1. Extended Context Attention ($T > 128$) [CRITICAL BLOCKER FOR DIALOGUE]
- **Current State:** The transformer positional buffer and attention mask are hardcoded to $T=128$ tokens.
- **Missing:** Rotary Position Embeddings (RoPE) or ALiBi for context scaling to $T=512$ or $T=1024$.
- **Impact:** Multi-turn dialogue (`CAP-08`) and document RAG question answering fail because inputs exceed 128 tokens.

### 2. Deep Neural Vector Embeddings (Bi-Encoder)
- **Current State:** RAG uses a character n-gram hashing trick (`local_custom_embedding`).
- **Missing:** A trained dense sentence-transformer model (e.g. IndicBERT, MiniLM, or custom Tamil bi-encoder).
- **Impact:** Semantic search cannot understand conceptual paraphrases or deep synonyms.

### 3. Approximate Nearest Neighbor (ANN) Vector DB
- **Current State:** Vector retrieval performs an in-memory brute-force NumPy dot product over SQLite BLOBs.
- **Missing:** Dedicated vector index library (FAISS, HNSW, or sqlite-vss).
- **Impact:** Inefficient at scale (> 50,000 document chunks).

### 4. Containerization & Production Packaging (Docker)
- **Current State:** Zero `Dockerfile` or `docker-compose.yml` files exist in the repository.
- **Missing:** Standardized container builds for backend and frontend services.
- **Impact:** System deployment requires manual environment configuration on host OS.

### 5. Automated GPU Acceleration (CUDA / MPS DDP)
- **Current State:** Training loop in `run_controlled_training_ws05.py` and `run_e3_experiments.py` explicitly sets `torch.device("cpu")` and `torch.set_num_threads(2)`.
- **Missing:** CUDA device detection, mixed precision (FP16/BF16), and multi-GPU DistributedDataParallel.
- **Impact:** Scaling models to 3M or 7M parameters on CPU will be prohibitively slow.

---

## 2. Features Documented in Previous Markdown Reports But Not Fully Implemented

1. **"Electron Desktop App"**:
   - *Documentation Claim:* Mentioned in past phase specifications as an intended desktop packaging target.
   - *Actual Code State:* Zero Electron runtime files exist in `apps/`. Only playwright-core server dependencies exist in `node_modules`.
2. **"Autonomous Self-Training Mini Brain"**:
   - *Documentation Claim:* High-level vision documents described the Mini Brain autonomously monitoring performance and kicking off retraining runs.
   - *Actual Code State:* Strictly blocked in code (`BLOCKED_ACTION_SUBSTRINGS = ("train", "pretrain")`). Training can only be initiated via explicit human command.
3. **"Open-Domain AI Translation"**:
   - *Documentation Claim:* Mentioned as part of the multilingual translation engine.
   - *Actual Code State:* Implemented as a 10-concept rule-based dictionary with phonetic mapping rules, not an open-domain neural translation model.
