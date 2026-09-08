# Master Brud AI End-to-End Audit — 20: Critical Missing Features

**Audit Date:** 2026-09-01  
**Auditor:** Principal Technical Product Architect  
**Confidence Rating:** HIGH CONFIDENCE (Derived from empirical capability and architectural gaps)  

---

## 1. Prioritized Gap Taxonomy

### P0 — Critical Governance Invariants (Must Be Maintained Today)
*These are not missing features, but mandatory governance constraints that must NOT be removed:*
- **P0.1: Maintain `training_execution_authorized = false`** until explicit human authorization is recorded.
- **P0.2: Enforce `candidate_traffic_share = 0.0`** and `is_public_chat_eligible = false` to prevent unvetted model exposure.
- **P0.3: Retain Frozen Baseline Checkpoints** (`checkpoint_best.pt` SHA-256: `30dbb892...`) and the production database in read-only states.

---

### P1 — Required Before Production AI Usage (The Functional Core Gaps)
*These represent the true technical blockers preventing Brud from delivering acceptable AI quality:*
- **P1.1: Context Window Scaling ($T=128 \to T=512$):**
  - *Gap:* The current 128-token attention buffer causes severe context truncation, breaking multi-turn dialogue (`CAP-08`) and RAG document ingestion.
  - *Remediation:* Implement WS07 Stage C (E4 Context Scaling).
- **P1.2: Architecture Capacity Scaling ($528\text{k} \to \sim 3.2\text{M}$ parameters):**
  - *Gap:* 2 layers with 128 hidden dimension cannot store open-domain semantic representations, leading to the 4.17% functional pass rate.
  - *Remediation:* Implement WS07 Stage C (E5 Architecture Scaling: $L=4, d=256, h=8$).
- **P1.3: Wiring Repetition-Controlled Decoding into Public Inference:**
  - *Gap:* The active `InferenceRuntimeService` currently defaults to greedy decoding. The decoding controls proven in WS07 E3 ($\theta=1.25$ + no-repeat 3-gram) must be formalized as default runtime parameters.

---

### P2 — Important Capability Improvements
- **P2.1: Dense Semantic Bi-Encoder for RAG:**
  - *Gap:* Character n-gram hashing cannot understand semantic paraphrases or conceptual similarity.
  - *Remediation:* Train or integrate a lightweight dense bi-encoder.
- **P2.2: Expansion of Translation Lexicon:**
  - *Gap:* `TAMIL_ENGLISH_LEXICON` covers only 10 core concepts.
  - *Remediation:* Expand the dictionary to 250+ essential Tamil concepts.
- **P2.3: Production Containerization (Docker):**
  - *Gap:* Zero `Dockerfile` or `docker-compose.yml` exists in the repository.
  - *Remediation:* Author container definitions for backend, frontend, and database services.

---

### P3 — Optimization & Future Architecture
- **P3.1: GPU / CUDA Multi-Device Acceleration:** Add optional CUDA support for accelerated training of larger models.
- **P3.2: Database Role Table Migration:** Migrate admin roles from environment variables into a dedicated database table.
- **P3.3: Prometheus Metrics Exporter:** Export real-time training and inference metrics to Prometheus/Grafana.
