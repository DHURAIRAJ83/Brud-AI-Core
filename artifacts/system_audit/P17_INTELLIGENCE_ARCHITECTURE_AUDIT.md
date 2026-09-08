# P17 Intelligence Architecture Audit: Brud Mini Brain Intelligence 2.0

**Audit Date**: 2026-09-06  
**Auditor**: Antigravity AI Assistant & Engineering Runtime  
**System**: Brud AI Mini Brain / Admin Assistant Runtime  
**Current Baseline**: Phase 16 Production Go-Live Ready (163/163 Tests Passing, G1–G14 Active)

---

## 1. Executive Summary

An exhaustive audit of the Brud AI codebase was conducted to inspect the current architecture across the runtime service, provider resolution, conversation service, memory system, RAG pipeline, tool/action registry, audit system, and configuration system.

The audit evaluates the readiness of the Mini Brain to be upgraded into **"BRUD MINI BRAIN — INTELLIGENCE 2.0"** while strictly maintaining backward compatibility, zero mock leakage, zero citation hallucination, zero secret leakage, and full preservation of architectural guardrails G1–G14.

---

## 2. Complete Capability Classification Matrix

Every capability required for Intelligence 2.0 has been classified according to the required 5-state taxonomy: `EXISTING`, `PARTIAL`, `MISSING`, `UNSAFE`, `DUPLICATED`.

| # | Capability Dimension | Status | Current Component / File | Gap / Audit Finding |
|---|----------------------|--------|--------------------------|---------------------|
| 1 | **Context Intelligence** | `PARTIAL` | `core_model/conversation/context_orchestrator.py`, `context_budget.py`, `context_window_manager.py` | Window budgeting exists; active topic tracking, topic change detection, unresolved question tracking, and cross-lingual reference/anaphora resolution ("அது", "இதில்", "முந்தையது", "அந்த file", "the previous one") are missing. |
| 2 | **Memory Intelligence** | `PARTIAL` | `backend/services/memory_service.py`, `backend/database/repositories/conversation_memory.py` | Storage, consent, and vector search exist; lacks 7-category taxonomy (`EPISODIC`, `SEMANTIC`, `PROCEDURAL`, `TASK`, `PREFERENCE`, `SYSTEM`, `ADMIN`), lifecycle scoring (importance, freshness, confidence, decay), promotion/demotion, and semantic compression. |
| 3 | **Duplicate Knowledge Control** | `PARTIAL` | `core_model/conversation/memory_deduplication.py` | Exact text equality check exists; semantic similarity clustering, near-duplicate canonical selection, and evidence count reinforcement (`evidence_count += 1`) are missing. |
| 4 | **Conflict Detection** | `PARTIAL` | `core_model/conversation/memory_deduplication.py` | Primitive category collision check exists; deep contradiction detection, structured `ConflictRecord` (`DETECTED`, `REVIEW_REQUIRED`, `RESOLVED`, `SUPERSEDED`), and admin governance for system knowledge changes are missing. |
| 5 | **Intent Intelligence** | `PARTIAL` | `core_model/admin_assistant/intent.py`, `core_model/mini_brain/intelligence/intent_engine.py` | Basic keyword-based navigation matching exists; 15-class intent classification with provider grounding and contextual awareness is missing. |
| 6 | **Task Understanding** | `MISSING` | `core_model/mini_brain/llm_runtime/next_action_planner.py` | Static templates exist; dynamic decomposition into structured tasks (`Goal` -> `Inspect` -> `Collect Evidence` -> `Analyze` -> `Rank Problems` -> `Recommend` -> `Explain Evidence`) with advisory-only enforcement is missing. |
| 7 | **Multi-Step Reasoning** | `PARTIAL` | `backend/services/mini_brain_llm_runtime_service.py` | Single-step execution exists; bounded reasoning orchestrator (`Understand` -> `Retrieve` -> `Analyze` -> `Validate` -> `Respond`) with step accounting, token limits, and infinite loop protection is missing. |
| 8 | **RAG-Grounded Reasoning** | `PARTIAL` | `backend/services/rag_retrieval_service.py`, `core_model/mini_brain/llm_runtime/citation_formatter.py` | Retrieval and formatting exist; explicit partitioning of model inference vs verified chunks, conflicting source detection, and freshness consideration are missing. |
| 9 | **Confidence & Uncertainty** | `MISSING` | `core_model/mini_brain/intelligence/confidence.py` (disconnected heuristic) | Calibrated 4-state classification (`HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`) based on retrieval quality, source verification, and contradiction signals is missing from the active chat pipeline. |
| 10 | **Self-Verification** | `MISSING` | None | Pre-response factual claim checking against retrieved evidence, contradiction checking, and bounded single-revision pass are missing. |
| 11 | **Admin Decision Support** | `PARTIAL` | `core_model/mini_brain/llm_runtime/admin_explainer_templates.py` | Explainer strings exist; structured diagnostic synthesis cleanly separating `FACT`, `OBSERVATION`, `INFERENCE`, and `RECOMMENDATION` is missing. |
| 12 | **Learning Governance** | `PARTIAL` | `backend/services/mini_brain_continuous_learning_service.py` | Dataset learning exists; conversation-derived candidate knowledge lifecycle (`Observation` -> `Candidate` -> `Validation` -> `Admin Review` -> `Approval` -> `Store`) is missing. |
| 13 | **Response Quality Gate** | `PARTIAL` | `core_model/instruction_tuning/language_checks.py`, `core_model/mini_brain/llm_runtime/message_sanitizer.py` | Language check and redaction exist; holistic pre-response quality gate (relevance, grounding, citation integrity, secret leakage, single retry) is missing. |
| 14 | **Observability & Tracing** | `EXISTING` | `backend/database/repositories/mini_brain_llm_runtime.py`, `backend/services/mini_brain_llm_runtime_service.py` | Structured runtime event logging exists in `mini_brain_llm_runtime_events` with trace propagation, requiring extension for Intelligence 2.0 fields. |
| 15 | **Resource & Budget Limits** | `EXISTING` | `core_model/mini_brain/llm_runtime/token_budget.py`, `core_model/conversation/context_budget.py` | Hard token budgets exist and need unified enforcement across all reasoning stages. |

---

## 3. Duplicate & Overlapping Intelligence Logic Detection

1. **Intent Classification Overlap**:
   - `core_model/admin_assistant/intent.py` (`classify_intent`) handles Phase 8 dashboard navigation.
   - `core_model/mini_brain/intelligence/intent_engine.py` contains standalone keyword rules.
   - `core_model/mini_brain/llm_runtime/tool_intent_classifier.py` classifies plugin/tool actions.
   - *Resolution*: Unify under a single layered `IntelligenceIntentClassifier` that evaluates deterministic navigation/tool rules first, then semantic/LLM intent classification, preserving existing Phase 8 routes without breaking changes.

2. **Context Budgeting Overlap**:
   - `core_model/conversation/context_orchestrator.py` builds context items.
   - `core_model/mini_brain/llm_runtime/context_window_manager.py` trims prompt history.
   - *Resolution*: Retain `context_orchestrator` as the canonical context item assembler and enhance `ContextIntelligenceManager` with bounded budgeting, topic tracking, and reference resolution.

3. **Memory Deduplication vs Knowledge Storage**:
   - `core_model/conversation/memory_deduplication.py` does exact match string comparisons.
   - *Resolution*: Extend `memory_deduplication.py` into a full `MemoryDeduplicationEngine` supporting semantic similarity clustering, canonical selection, and evidence reinforcement.

---

## 4. Security, Resilience, and Performance Risk Assessment

1. **Infinite Reasoning Loop Risk**:
   - *Risk*: Multi-step reasoning or self-verification could enter recursive cycles under complex queries.
   - *Mitigation*: Enforce `MAX_REASONING_STEPS = 5`, `MAX_SELF_VERIFICATION_PASSES = 1`, and strict wall-clock timeouts (10s total).

2. **Autonomous Execution Risk**:
   - *Risk*: Intelligence 2.0 might infer destructive actions or auto-execute tool modifications.
   - *Mitigation*: Hard-lock all admin assistant outputs to `ADVISORY_ONLY`. Any actionable change must pass through the existing Phase-8 / Phase-16 `AdminAssistantService.propose()` governance pathway requiring explicit admin human review and approval.

3. **Memory Explosion & Database Bloat**:
   - *Risk*: Unbounded capture of repetitive memory items could degrade SQLite performance.
   - *Mitigation*: Lifecycle enforcement: Canonical deduplication with evidence counter, exponential decay for unreinforced memories, and hard bounds on retrieved memory items (`MAX_RETRIEVED_MEMORIES = 10`).

4. **Secret Leakage & Egress Risk (G8)**:
   - *Risk*: Context intelligence, reasoning traces, or diagnostic explainers might reflect credentials or API keys.
   - *Mitigation*: Re-run `message_sanitizer.sanitize()` and regex scrubbing across all prompt inputs, reasoning traces, conflict records, candidate knowledge, and final responses.

---

## 5. Architectural Guardrail Invariants (G1–G14)

All Intelligence 2.0 implementations must strictly preserve:
- **G1 (Zero Autonomous Execution)**: Assistant remains advisory-only; proposals require human approval.
- **G2 (Deterministic Gateways)**: Pure rule/read-only paths run without LLM dependence.
- **G3 (Model Path Confinement)**: Model weights remain locked to allowed directory.
- **G4 (Zero Mock Leakage)**: `MockMiniBrainAdapter` is strictly forbidden in production resolution.
- **G5 (Tenant Isolation)**: Participant and admin scopes strictly isolated.
- **G8 (Zero Secret Leakage)**: Secret scrubbing across all logging, events, and traces.
- **G9 (Citation Integrity)**: Ungrounded citations = `[]`; no hallucinated sources or URLs.
- **G10 (Session Persistence)**: Turn ordering and exact-once session state preserved in SQLite.
- **G11 (WAL Durability)**: SQLite WAL mode with synchronous=NORMAL intact.
- **G14 (Fail-Closed Configuration)**: System fails closed on unconfigured or invalid providers.
