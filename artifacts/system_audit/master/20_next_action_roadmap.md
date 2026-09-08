# Master Brud AI System Audit — 20: Next-Action Roadmap & Prioritization

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect & Technical Project Analyst  
**Confidence Rating:** HIGH CONFIDENCE (Derived directly from empirical audit findings)  

---

## 1. Prioritized Engineering Roadmap

```
   ┌──────────────────────────────────────────────────────────────────┐
   │ P0: CRITICAL BLOCKERS (Must be maintained / enforced right now) │
   └──────────────────────────────────┬───────────────────────────────┘
                                      │
   ┌──────────────────────────────────▼───────────────────────────────┐
   │ P1: REQUIRED FOR FUNCTIONAL AI (WS07 Stage C: E4 & E5 Scaling)   │
   └──────────────────────────────────┬───────────────────────────────┘
                                      │
   ┌──────────────────────────────────▼───────────────────────────────┐
   │ P2: REQUIRED FOR ADVANCED AI (Dense RAG & Expanded Lexicon)      │
   └──────────────────────────────────┬───────────────────────────────┘
                                      │
   ┌──────────────────────────────────▼───────────────────────────────┐
   │ P3: PRODUCTION HARDENING (Containerization & Reverse Proxy)      │
   └──────────────────────────────────┬───────────────────────────────┘
                                      │
   ┌──────────────────────────────────▼───────────────────────────────┐
   │ P4: FUTURE ENHANCEMENTS (GPU Distributed Acceleration)           │
   └──────────────────────────────────────────────────────────────────┘
```

### P0 — Critical Governance Blockers (Maintain Existing Invariants)
- **Invariant 1:** Maintain `training_execution_authorized = false` until explicit human authorization is granted.
- **Invariant 2:** Keep `candidate_traffic_share = 0.0` and `production_promotion = BLOCKED`.
- **Invariant 3:** Preserve frozen WS05 baseline checkpoint and production database immutability.

### P1 — Required for Functional AI (Direct Next Milestone: WS07 Stage C)
- **P1.1 — E4 Context Scaling ($T=128 \to T=512$):** Upgrade the sinusoidal positional encoding or integrate RoPE to allow conversational turns and RAG context beyond 128 tokens.
- **P1.2 — E5 Architecture Capacity Scaling ($528\text{k} \to 3\text{M}$ params):** Scale layers ($L=4$) and hidden dimension ($d=256$) to provide the representational capacity necessary for Tamil grammatical fluency and factual retention.
- **P1.3 — Integration of Controlled Decoding into Active Runtime:** Formalize the inference-assisted decoding parameters ($\theta=1.25$ + no-repeat 3-gram) inside `InferenceRuntimeService` to eliminate repetition loops permanently.

### P2 — Required for Advanced AI
- **P2.1 — Dense Semantic Embeddings for RAG:** Replace the n-gram character hashing trick with a trained lightweight bi-encoder for semantic similarity search.
- **P2.2 — Expansion of Admin Assistant Lexicon:** Broaden `TAMIL_ENGLISH_LEXICON` from 10 concepts to 250+ essential Tamil-English operational concepts.
- **P2.3 — ANN Vector Indexing:** Integrate a lightweight local approximate nearest neighbor index (e.g. SQLite-VSS or HNSWlib).

### P3 — Production Hardening
- **P3.1 — Production Containerization:** Author clean `Dockerfile` and `docker-compose.yml` for unified single-command backend/frontend launch.
- **P3.2 — Database RBAC Schema Migration:** Migrate admin roles from environment variables into a dedicated `admin_roles` database table.

### P4 — Future Enhancements
- **P4.1 — Multi-GPU / CUDA Acceleration:** Add optional CUDA support for accelerated training of models $> 10\text{M}$ parameters.

---

## 2. Definitive Next Best Action: Phase 60 WS07 Stage C

### Selected Action: **PHASE 60 WS07 STAGE C — ARCHITECTURE & CONTEXT SCALING (E4 & E5)**

### WHY this is the Correct Next Step:
1. **WS07 Stage B (E3) has completed its mission:**
   - E3 proved that dataset expansion improves EOS termination (from 0% to 100% in E3-E) and cross-lingual balance.
   - It also proved that repetition loops are solved at decoding time ($\theta=1.25 \to 0.0000$ repetition).
2. **The remaining failure modes (FM-02 context forgetting & low functional pass rate) are architectural bottlenecks:**
   - A 528k parameter model with a 128-token context window has hit a physical capacity ceiling. No amount of additional data curation at 528k parameters will solve multi-turn conversation retention without expanding the context window ($T=512$) and scaling capacity ($L=4, d=256$).

### What Should NOT Be Done Yet:
- ❌ **DO NOT promote any candidate to production.**
- ❌ **DO NOT enable candidate traffic (keep 0.0%).**
- ❌ **DO NOT attempt external web scraping or uncurated data dumps.**
- ❌ **DO NOT proceed to WS08 Independent Evaluation until Stage C produces a qualified scaled candidate.**

### Success Criteria for WS07 Stage C:
1. Context window successfully expanded to $T=512$ with verified attention mask.
2. Architecture scaled to ~3.2M parameters ($L=4, d=256, h=8$).
3. Peak training memory remains $< 1.5\text{ GB}$ on dual-core CPU with zero swap usage.
4. Pass rate on 24 CAP probes improves from $4.17\%$ to $\ge 25.0\%$.
5. Kumar multi-turn context retention probe (`CAP-08`) passes cleanly.
