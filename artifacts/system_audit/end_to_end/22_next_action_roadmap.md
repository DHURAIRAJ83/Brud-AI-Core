# Master Brud AI End-to-End Audit — 22: Next-Action Roadmap & Technical Sequence

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect & Technical Director  
**Confidence Rating:** HIGH CONFIDENCE (Derived directly from empirical audit findings)  

---

## 1. The Definitive Top 5 Technical Actions in Priority Order

```
[ ACTION 1 ] ──► Phase 60 WS07 Stage C: E4 Context Window Scaling (T=128 → T=512)
      │
      ▼
[ ACTION 2 ] ──► Phase 60 WS07 Stage C: E5 Architecture Capacity Scaling (528k → 3.2M params)
      │
      ▼
[ ACTION 3 ] ──► Wire Repetition-Controlled Decoding (θ=1.25) into Default Inference Runtime
      │
      ▼
[ ACTION 4 ] ──► Expand Admin Assistant Tamil-English Lexicon (10 → 250+ concepts)
      │
      ▼
[ ACTION 5 ] ──► Standardize Production Packaging (Author Dockerfile & docker-compose.yml)
```

---

## 2. Detailed Technical Action Specifications

### ACTION 1: Phase 60 WS07 Stage C — E4 Context Window Scaling ($T=128 \to T=512$)
- **Why this is first:** A 128-token context window is the physical bottleneck preventing dialogue retention and document RAG. No amount of additional training at $T=128$ can solve multi-turn forgetting (`CAP-08`).
- **What it will solve:** Expands the transformer attention buffer and positional encoding to $T=512$, enabling 4x longer conversational history and complete RAG chunk synthesis.
- **Success Criteria:** Verification that the attention mask and position embeddings process 512 tokens with zero out-of-bounds index errors.

### ACTION 2: Phase 60 WS07 Stage C — E5 Architecture Capacity Scaling ($528\text{k} \to \sim 3.2\text{M}$ params)
- **Why this is second:** 2 layers and 128 hidden dimensions have hit a physical capacity ceiling (4.17% pass rate). Adding parameters ($L=4, d=256, h=8$) provides the expressivity needed for Tamil grammar and factual retention.
- **What it will solve:** Increases model representational power by 6x while staying comfortably within CPU memory budgets (< 1.5 GB RAM).
- **Success Criteria:** Pass rate on 24 CAP probes improves from 4.17% to $\ge 25.0\%$.

### ACTION 3: Formalize Repetition-Controlled Decoding in Default Inference Runtime
- **Why this is third:** WS07 E3 proved that setting $\theta=1.25$ and `no_repeat_ngram_size=3` drops 3-gram repetition from 0.90 to 0.0000. This must be wired as default parameters in `InferenceRuntimeService`.
- **What it will solve:** Eliminates repetitive loops for all runtime inference without retraining.
- **Success Criteria:** Runtime regression tests confirm 0.0000 repetition on benchmark prompts.

### ACTION 4: Expand Admin Assistant Lexicon from 10 to 250+ Concepts
- **Why this is fourth:** The current deterministic translation and Tanglish expansion engine covers only 10 core concepts.
- **What it will solve:** Enables the Admin Assistant to generate rich, diverse bilingual training candidates across a broad operational domain.
- **Success Criteria:** 250 verified Tamil root words with disambiguated English translations and phonetic Tanglish mappings.

### ACTION 5: Standardize Production Packaging (Docker Containerization)
- **Why this is fifth:** Once model capability and runtime decoding are validated, single-command container orchestration ensures reproducible deployment across Linux servers.
- **What it will solve:** Eliminates host environment dependencies (Node/Python versions).
- **Success Criteria:** `docker compose up -d` brings up backend, frontend, and database services with health check passing.

---

## 3. What Should NOT Be Done Yet (Strict Constraints)
- ❌ **DO NOT promote any candidate to production.**
- ❌ **DO NOT enable candidate traffic (keep 0.0%).**
- ❌ **DO NOT bypass the Two-Person Review Gate.**
- ❌ **DO NOT proceed to WS08 Independent Evaluation until Stage C produces a qualified scaled candidate.**
