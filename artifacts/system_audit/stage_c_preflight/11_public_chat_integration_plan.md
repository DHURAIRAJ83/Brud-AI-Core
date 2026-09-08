# Stage C Pre-Flight Audit — 11: Public Chat Integration Plan

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Executive Summary & Critical Blocker Remediation Plan

The WS08 Master End-to-End Audit identified one critical operational gap preventing scaled candidate models from serving public chat queries:

```text
CRITICAL BLOCKER = Repetition controls (θ=1.25 + no-repeat 3-gram) are NOT wired into the default execution path of InferenceRuntimeService.
IMPACT           = Raw model weights suffer from repetitive text generation if queried directly without decoding controls.
```

---

## 2. Public Chat 13-Stage Orchestration Trace

```text
User Message (POST /api/chat/message)
       ↓
Stage 1:  Safety Input Filter (Jailbreak / PII)
Stage 2:  Language Detection (Tamil / English / Tanglish / Mixed)
Stage 3:  Bilingual Normalization (NFC Unicode)
Stage 4:  Conversation Memory Retrieval (SQLite consent-gated)
Stage 5:  Intent Classification
Stage 6:  Tool Routing (Calculator / Date / Unit converter) → [Executes directly if tool match]
Stage 7:  RAG Context Retrieval (BM25 + n-gram search)
Stage 8:  Context Assembly (<user>{prompt}{context}<assistant>)
Stage 9:  Model Route Selection
Stage 10: ← INFERENCE GATE (InferenceRuntimeService._execute_evidence_route)
Stage 11: External Provider Fallback (OpenRouter API - disabled if no key)
Stage 12: Safety Output Filter (Secret scrubbing)
Stage 13: Response Formatting & Delivery
```

---

## 3. Repetition Controls Wiring Specification

To prepare for future model activation post-Stage C, `InferenceRuntimeService` must be updated to apply controlled decoding parameters by default when generating responses via neural models.

### Proposed Code Diff Plan (FOR FUTURE EXECUTION ONLY):

```python
# File: backend/services/inference_runtime_service.py

def _execute_evidence_route(self, prompt: str, assignment: dict) -> dict:
    # Build generation config with canonical repetition controls
    gen_config = GenerationConfig(
        max_new_tokens=48,
        temperature=0.7,
        top_k=20,
        repetition_penalty=1.25,     # Repetition penalty theta = 1.25
        no_repeat_ngram_size=3,     # Prevent 3-gram loops
        eos_token_id=3
    )
    
    # Execute generation with controlled decoding engine
    output = self.generation_engine.generate(
        model=assignment["model_instance"],
        tokenizer=self.tokenizer,
        prompt=prompt,
        config=gen_config
    )
    return output
```

---

## 4. Promotion Safety & Traffic Gating

Even after repetition controls are wired into `InferenceRuntimeService`, production traffic MUST remain strictly blocked:
- `candidate_traffic_share = 0.0`
- `is_public_chat_eligible = false`
- `production_promotion = BLOCKED`

Candidate models will undergo formal human sign-off before any traffic allocation.
