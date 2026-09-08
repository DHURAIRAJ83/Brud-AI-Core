# Master Brud AI End-to-End Audit — 23: Master Brud End-to-End State & Q&A

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect, ML Pipeline Auditor & Chief Technical Auditor  
**Audit Location:** `artifacts/system_audit/end_to_end/`  
**Mode:** STRICT READ-ONLY, EVIDENCE-BACKED  

---

## 1. Master Subsystem State Summaries

```
====================================================================================================
                              MASTER BRUD END-TO-END STATE SUMMARY
====================================================================================================

CURRENT BRUD STATE:
  A hybrid AI system pairing a highly mature, enterprise-grade backend and governance platform
  (FastAPI, SQLite WAL, React 19, 108 tools, 1,774 endpoints) with an experimental small causal
  transformer (Brud-Small v2: 528,128 parameters, L=2, d=128, T=128). The infrastructure is
  production-grade; the neural model is an early-stage prototype requiring architectural scaling.

ADMIN ASSISTANT MINI BRAIN STATE:
  Level 2.5 (Advanced Tool-Using Assistant with Governed Proposal Mechanics). Operates via a 4-layer
  hybrid architecture: deterministic rules/FAQs, 108 read-only inspection tools, governed dataset
  expansion engine, and safe local model fallback. Actions containing "train" or "pretrain" are
  strictly barred in code; cannot retrain itself or promote models autonomously.

TRAINING LIFECYCLE STATE:
  Fully functional and bounded CPU training pipeline (AdamW, Cosine, 15 hardware & divergence guards,
  RSS < 513 MB, 0 swap). Proven across 5 controlled remediation runs (E3-A through E3-E). Currently
  HALTED under mandatory human governance (training_execution_authorized = false).

PUBLIC CHAT STATE:
  Operational under safe degradation. Real user queries are intercepted by the 13-stage routing
  pipeline. Deterministic math/unit queries are executed accurately by local Python tools. General
  text queries degrade gracefully to an honest, polite "service unavailable" message because zero
  models are assigned to the public scope. Unvetted models are never exposed.

END-TO-END LEARNING LOOP STATE:
  100% architecturally and functionally complete in code from diagnosis -> proposal -> validation ->
  admin review -> cryptographic sealing -> training -> evaluation -> comparative reporting. Enforces
  mandatory human authorization between evaluation and promotion.

DUPLICATE CODE STATE:
  53 duplicate class names identified across production and candidate test runners (most notably
  BrudSmallV2Model copied across 4 runner scripts, and CreateSessionRequest across 12 Mini Brain models).
  0 duplicate API route endpoints (FastAPI router prefixing prevents collisions).

DEAD CODE STATE:
  Contains placeholder files (empty core_model/inference/ directory, 4 dummy GGUF stubs from Phase 1,
  and 1,200+ legacy integration test adapters taking ~150 MB). None affect runtime performance or security.

SECURITY / GOVERNANCE STATE:
  Enterprise-grade. Bcrypt password hashing, CSRF double-cookie tokens, parameter-scrubbed SQL queries,
  zero RCE vectors, two-person verification drill for high-risk proposals, immutable append-only audit
  logs, and SHA-256 air-gap verification against held-out benchmarks.

PRODUCTION READINESS STATE:
  Platform & Governance: 80%–95% (Production Ready).
  Core Neural Model: 35.0% (Prototype).
  Overall System: 56.4% (Functional Candidate).
  Deployment Gate: STRICTLY BLOCKED until model capacity and context scaling (Stage C) are executed.
====================================================================================================
```

---

## 2. Direct Answers to Questions Q1 through Q12

### Q1: Can Admin provide Tamil data and have the system automatically create English + Tanglish data?
**Answer: YES, for concepts covered by the expansion lexicon.**  
The admin provides a Tamil concept or source record. The `DatasetExpansionEngine` (`core_model/admin_assistant/dataset_expansion_engine.py`) deterministically expands it into English translations, phonetic Tanglish mappings, bilingual code-switched phrases, conversations, and instructions. The resulting proposals enter the Admin Review Queue.

### Q2: Can Admin Assistant use an external AI provider to improve/translate the data?
**Answer: PARTIALLY IMPLEMENTED IN CODE; CURRENTLY DISABLED IN LOCAL RUNTIME.**  
The `MiniBrainExternalAiGatewayService` (`backend/services/mini_brain_external_ai_gateway_service.py`) and `OpenRouterProviderClient` implement real HTTP dispatch via `httpx` to OpenRouter. However, no API key is configured in this local environment (`is_available() = False`), so external provider calls fall back to local mock or deterministic engines.

### Q3: Does external AI output always go through validation + human approval?
**Answer: YES, STRICTLY ENFORCED IN CODE.**  
There is zero direct path from external provider output to training datasets. External outputs are marked `status='pending_admin_review'`. The bridge service (`ExternalGatewayDatasetBridgeService`) explicitly rejects exporting any session unless `session.status == "admin_accepted"`.

### Q4: Can approved data automatically enter the training engine?
**Answer: YES, PROGRAMMATICALLY; NO AUTONOMOUS DAEMON.**  
Once proposals are reviewed and approved, `seal_dataset()` outputs an immutable JSONL file bound by SHA-256. The training script reads this sealed file directly. However, the system intentionally does not launch training automatically without an explicit human command.

### Q5: Can the Brud model actually train from that approved dataset?
**Answer: YES, EMPIRICALLY VERIFIED.**  
In Phase 60 WS07 Stage B, the training engine successfully trained 5 separate candidates (`E3-A` through `E3-E`) directly from `phase60_ws07_e3_dataset_v001.jsonl` across 100 steps per model on CPU without a single runtime failure.

### Q6: Can the trained candidate automatically go through independent evaluation?
**Answer: YES, FULLY AUTOMATED.**  
The evaluation script (`run_capability_evaluation_ws06.py`) automatically evaluates checkpoints across 24 standard capability probes, computing loss, repetition ratios, EOS emission, and safety adherence.

### Q7: Can only a human-approved candidate reach Public Chat?
**Answer: YES, STRICTLY ENFORCED IN CODE.**  
The runtime governance module (`phase44_runtime_governance.py`) locks `candidate_traffic_share = 0.0` and enforces a maximum governance ceiling of `INTERNAL_CANARY_QUALIFIED`. The code strictly bars transition to `PUBLIC_PRODUCTION` without a recorded Two-Person administrative approval token.

### Q8: When a user asks a question in Public Chat, does the correct Brud inference/RAG/tool/provider pipeline actually answer it?
**Answer: YES, WITH FAIL-SAFE DEGRADATION.**  
- If the user asks a calculation or conversion (e.g. `2 + 2 = ?`), the deterministic tool pipeline executes and returns the correct result (`4`).
- If the user asks a general conversational or Tamil question, the pipeline queries `PublicModelAssignmentResolver`. Because zero models are assigned to production, it returns an honest, polite system message that AI generation is currently unavailable.

### Q9: What parts are REAL and operational today?
**Answer:**
1. Complete FastAPI backend (1,774 endpoints, bcrypt auth, CSRF, audit logging).
2. SQLite database with 139 tables in WAL mode.
3. React 19 Admin Dashboard and Public Chatbot UI.
4. Tokenizer v2 (1024 BPE vocab with byte fallback).
5. PyTorch causal transformer training engine with 15 resource stop conditions.
6. 108 read-only Admin Assistant inspection tools.
7. WS07 E3 deterministic dataset expansion engine (7 generation modes, polysemy handling).
8. Admin Review Queue and cryptographic dataset sealing.
9. Repetition-controlled inference decoding engine ($\theta=1.25$ + no-repeat 3-gram).
10. Deterministic public calculator, unit converter, and date arithmetic tools.
11. 1,894 / 1,894 passing automated regression and evaluation tests.

### Q10: What parts are only architectural/documented intentions?
**Answer:**
1. **Desktop Electron App:** Documented in past phase plans, but only playwright-core testing libraries exist; no application wrapper exists.
2. **Autonomous Retraining Mini Brain:** Documented in early concept designs, but strictly blocked in code (`BLOCKED_ACTION_SUBSTRINGS = ("train", "pretrain")`).
3. **Open-Domain Neural AI Translation:** Documented in high-level vision, but implemented as a 10-concept deterministic dictionary with phonetic mapping rules.
4. **Dense Bi-Encoder Semantic RAG:** Documented in architecture specs, but currently implemented using an n-gram character hashing trick.

### Q11: What duplicate folders/files/classes/services exist?
**Answer:**
- 53 duplicate class names across the codebase (e.g. `BrudSmallV2Model` in 4 runner files, `CreateSessionRequest` across 12 Mini Brain models, `FeedbackRepository` in 2 files).
- Parallel directories: `core_model/mini_brain/research_center/` vs `continuous_learning_center/`.
- 1,200+ tiny integration test adapter checkpoints under `data/core_models/checkpoints/`.

### Q12: What MUST be completed before Brud can become the intended self-improving governed AI system?
**Answer:**
1. **Context Window Scaling (WS07 Stage C: E4 Scaling):** Expand context from $T=128 \to T=512$ tokens to enable multi-turn dialogue retention and document RAG.
2. **Architecture Capacity Scaling (WS07 Stage C: E5 Scaling):** Scale transformer parameters from $528\text{k} \to \sim 3.2\text{M}$ ($L=4, d=256, h=8$) to provide semantic representation capacity.
3. **Inference Runtime Wiring:** Formalize repetition-controlled decoding ($\theta=1.25$ + no-repeat 3-gram) as default parameters in `InferenceRuntimeService`.
4. **Lexicon Expansion:** Expand the Admin Assistant bilingual dictionary from 10 to 250+ root concepts.
5. **Production Containerization:** Author production `Dockerfile` and `docker-compose.yml` for unified single-command deployment.
