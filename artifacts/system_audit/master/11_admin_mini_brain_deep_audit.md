# Master Brud AI System Audit — 11: Admin Assistant Mini Brain Deep Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal AI Systems Architect, ML Engineer & Scientific Auditor  
**Confidence Rating:** HIGH CONFIDENCE (Verified by source code, database tables, and execution traces)  

---

## 1. Subsystem Identity: What Exactly IS the Admin Assistant Mini Brain?

Tracing the actual execution path through `core_model/mini_brain/` and `backend/services/admin_assistant_chat_service.py` reveals the true technical identity of the Mini Brain:

### Technical Verdict:
The Admin Assistant Mini Brain is **NOT** a standalone monolithic large language model, nor is it an ungrounded autonomous agent.

It is a **modular, hybrid governance and orchestration framework** consisting of four distinct layers:
1. **Deterministic Expert System (Primary Intelligence Layer):**
   - Pure Python rule engines, state machines, regular expression matchers, and curated FAQs (`core_model/admin_assistant/*_help.py`, `dashboard_registry.py`, `action_registry.py`).
2. **Tool-Assisted Service Gateway (System Awareness Layer):**
   - 108 read-only inspection tools (`backend/services/admin_assistant_tools.py`) directly querying the SQLite database, model registry, RAG spaces, and system metrics.
3. **Controlled Local LLM Fallback (Optional Generation Layer):**
   - When an open-ended question is asked, it queries the Phase 15 inference runtime under the `admin_diagnostic` scope (`BrudSmallV2Model` or configured local GGUF).
   - If no model is assigned or if the local model is offline, it gracefully falls back to deterministic assistance with zero downtime.
4. **Governed Dataset Expansion Engine (WS07 E3 Layer):**
   - Deterministic lexicon, phonetic transliterator, and template generator (`core_model/admin_assistant/dataset_expansion_engine.py`) creating proposed training records for human review.

---

## 2. Implemented Intelligence vs Documented Capabilities

| Capability Domain | Implemented / Partial / Documented / Missing | Actual Code Implementation | Evidence / File Path |
|---|---|---|---|
| **System Understanding** | ✅ **IMPLEMENTED** | Reads live database state, table counts, and schema health | `admin_assistant_tools.py::_tool_get_system_health` |
| **Project & Repo Inspection**| ✅ **IMPLEMENTED** | Reads registered pages, configs, and active feature flags | `dashboard_registry.py`, `config.py` |
| **Code Analysis** | 🔵 **DOCUMENTED ONLY** | No static code analysis or AST parser wired into runtime | None |
| **Architecture Analysis** | 🟡 **PARTIAL** | Inspects parameter counts, layer counts, and checkpoint metadata | `model_loader.py`, `phase60_ws07_e3_training.py` |
| **Dataset Analysis** | ✅ **IMPLEMENTED** | Record counting, split ratios, language distribution, quarantine audit | `curate_and_seal_phase60_v001.py`, `dataset_cli.py` |
| **RAG Management** | ✅ **IMPLEMENTED** | Chunks inspection, retrieval scoring, injection checks in sandbox | `rag_sandbox.py`, `backend/services/rag_service.py` |
| **Training Planning** | ✅ **IMPLEMENTED** | Hyperparameter configuration, resource ceilings, stop conditions | `phase60_ws04_training_config.json`, `run_controlled_training_ws05.py` |
| **Training Monitoring** | ✅ **IMPLEMENTED** | Real-time step logging, loss tracking, gradient norm, RSS checks | `training_log.jsonl`, `phase60_ws05_execution_summary.json` |
| **Model Evaluation** | ✅ **IMPLEMENTED** | Evaluates 24 CAP probes, computes repetition ratios and EOS rates | `run_capability_evaluation_ws06.py`, `run_e3_experiments.py` |
| **Failure Analysis** | ✅ **IMPLEMENTED** | Failure matrix synthesis (FM-01 through FM-04) | `phase60_ws07_e3_failure_matrix.md` |
| **Security Analysis** | ✅ **IMPLEMENTED** | CSRF validation, secret redaction, audit trail persistence | `admin_assistant_write_governance.py`, `json_utils.py` |
| **Deployment Assistance** | 🟡 **PARTIAL** | Verifies canary criteria and rollback tripwires, but no cloud deployment | `core_model/release/phase44_canary_monitor.py` |
| **Provider Management** | 🟡 **PARTIAL** | SQLite tables and configuration for local GGUF, but no live cloud API routing | `mini_brain_provider_settings` table, `config.py` |
| **Memory Management** | ✅ **IMPLEMENTED** | Purpose-bound declarative memory items with explicit consent | `backend/services/memory_service.py` |
| **Tool Usage** | ✅ **IMPLEMENTED** | 108 read-only tools and 3 deterministic public math/unit tools | `admin_assistant_tools.py`, `deterministic_tool_registry.py` |
| **Task Planning** | 🟡 **PARTIAL** | Rule-based ranked action list from status snapshot | `core_model/mini_brain/llm_runtime/next_action_planner.py` |
| **Reasoning** | 🔴 **WEAK / MISSING** | The 528k neural model cannot perform multi-step deduction | CAP-09 arithmetic probe fail (WS06 / WS07) |
| **Report Generation** | ✅ **IMPLEMENTED** | Automated markdown report synthesis for training and evaluations | `job_report_generator.py`, `run_e3_experiments.py` |
| **Tamil Understanding** | 🟡 **PARTIAL** | Keyword and intent matching; neural semantic comprehension is shallow | `classify_language()`, `classify_intent()` |
| **English Understanding** | 🟡 **PARTIAL** | Keyword and intent matching; neural semantic comprehension is shallow | `classify_language()`, `classify_intent()` |
| **Tanglish Understanding** | ✅ **IMPLEMENTED** | 32-word conversational lexicon + canonical phonetic normalizer | `DEFAULT_TANGLISH_LEXICON`, `tanglish_normalizer.py` |
| **Translation** | 🟡 **PARTIAL** | Rule-based bidirectional lexicon covering 10 core concepts | `TAMIL_ENGLISH_LEXICON` in `dataset_expansion_engine.py` |
| **Dataset Generation** | ✅ **IMPLEMENTED** | Deterministic expansion into 7 generation modes | `dataset_expansion_engine.py` (88 records sealed) |
| **Experiment Planning** | ✅ **IMPLEMENTED** | Multi-experiment sequential matrix design (E3-A through E3-E) | `phase60_ws07_e3_experiment_matrix.md` |
| **Experiment Comparison**| ✅ **IMPLEMENTED** | Multi-dimensional comparison matrix (Loss, Repetition, EOS, Safety) | `phase60_ws07_e3_comparative_final.md` |
| **Governance Enforcement**| ✅ **IMPLEMENTED** | Two-person rule, blocked substrings, immutable audit log | `admin_assistant_write_governance.py`, `phase44_runtime_governance.py`|

---

## 3. Admin Assistant Authority Boundary: Enforced vs Blocked

The system enforces strict separation of privileges in code:

| Action Class | Authority Level | Enforced Mechanism | Code Location |
|---|---|---|---|
| **READ** | ✅ **ALLOWED** | 108 read-only tools permitted for authenticated admins (`tool.read`) | `backend/services/admin_assistant_tools.py` |
| **PROPOSE** | ✅ **ALLOWED** | Can create proposal rows with status `PENDING` (`tool.propose`) | `backend/services/admin_assistant_write_governance.py` |
| **VALIDATE** | ✅ **ALLOWED** | Deterministic quality gates validate proposals automatically | `core_model/admin_assistant/dataset_expansion_validator.py` |
| **EDIT** | 🟡 **HUMAN ONLY** | Only human admin on Dashboard can edit pending proposal payloads | `backend/services/admin_assistant_service.py::edit_proposal` |
| **APPROVE** | 🟡 **HUMAN ONLY** | Only authenticated human admin can approve proposals (2-person for High) | `backend/services/admin_assistant_service.py::review_proposal` |
| **EXECUTE** | 🟡 **HUMAN-TRIGGERED**| Assistant cannot self-execute; execution requires approved proposal | `backend/services/admin_assistant_write_governance.py` |
| **DEPLOY** | 🔒 **STRICTLY BLOCKED**| Production promotion is hard-blocked (`production_promotion = BLOCKED`) | `core_model/release/phase44_runtime_governance.py` |
| **TRAIN** | 🔒 **STRICTLY BLOCKED**| Any proposal containing `"train"` or `"pretrain"` is rejected by code | `core_model/admin_assistant/action_registry.py::BLOCKED_ACTION_SUBSTRINGS` |
| **PROMOTE**| 🔒 **STRICTLY BLOCKED**| Candidate traffic ceiling locked to `0.0%` | `core_model/release/phase44_runtime_governance.py` |

---

## 4. Deep Inspection of WS07 E3 Dataset Expansion

- **Generation Types Supported (7 Modes):**
  1. `WORD_LEVEL`: Direct lexical translation pairs (`அம்மா` $\leftrightarrow$ `mother`).
  2. `PHRASE_LEVEL`: Noun and verb phrase expansions (`என் அம்மா` $\leftrightarrow$ `my mother`).
  3. `SENTENCE_LEVEL`: Simple grammatical sentences (`என் அம்மா வீட்டில் இருக்கிறார்.` $\leftrightarrow$ `My mother is at home.`).
  4. `TRANSLATION_DIRECTION`: Explicit directional translation prompts (`Translate to English: ...`).
  5. `MIXED_BILINGUAL`: Code-switched conversational Tamil-English sentences.
  6. `CONVERSATIONAL`: Multi-turn question-answer dialogue pairs.
  7. `INSTRUCTION`: Single-turn instruction-response pairs.
- **Polysemy Disambiguation:**
  - Context-aware disambiguation rules for `பால்` (milk vs gender), `படி` (study vs stair vs measure), and `திங்கள்` (Monday vs moon/month).
- **Administrative Review Lifecycle:**
  - `run_e3_expansion_proposals.py` generated 88 candidate records.
  - All 88 passed quality gates (`dataset_expansion_validator.py`).
  - All 88 were reviewed and sealed into `artifacts/candidates/phase60/ws07/e3/data/phase60_ws07_e3_dataset_v001.jsonl` (SHA-256: `cb1387ebc92c6554fa0bd6a3b076728142b295c7e3b334670a2f5547da17c391`).
- **Real vs Test Implementation:**
  - This is a **REAL, executable production-grade subsystem**. It is not a mock or test fixture.

---

## 5. End-to-End Admin Assistant Learning Loop Status

```
[ Admin Source Data ]                ──► ✅ IMPLEMENTED (Phase 55 & Phase 60 Curated Sources)
        │
        ▼
[ Admin Assistant Proposal ]         ──► ✅ IMPLEMENTED (dataset_expansion_engine.py)
        │
        ▼
[ Automated Validation ]             ──► ✅ IMPLEMENTED (dataset_expansion_validator.py)
        │
        ▼
[ Admin Review Queue ]               ──► ✅ IMPLEMENTED (admin_assistant_dataset_expansion_service.py)
        │
        ▼
[ Approved Dataset Sealing ]         ──► ✅ IMPLEMENTED (SHA-256 Cryptographic Sealing)
        │
        ▼
[ Dataset Versioning ]               ──► ✅ IMPLEMENTED (Immutable JSONL + Manifest)
        │
        ▼
[ Training Candidate Config ]        ──► ✅ IMPLEMENTED (Isolated Candidate Directories)
        │
        ▼
[ Controlled Training ]              ──► ✅ IMPLEMENTED (run_e3_experiments.py with Hard Stops)
        │
        ▼
[ Dual Capability Evaluation ]       ──► ✅ IMPLEMENTED (Raw Weights vs Repetition-Controlled Decoding)
        │
        ▼
[ Failure Analysis Synthesis ]       ──► ✅ IMPLEMENTED (FM-01 through FM-04 Matrix Reports)
        │
        ▼
[ Next-Step Recommendation ]         ──► ✅ IMPLEMENTED (Comparative Final Audit Report)
        │
        ▼
[ Human Authorization Gate ]         ──► 🔒 ENFORCED (Hard Stop; Execution Halted)
```

**Verdict:** The end-to-end learning loop is **100% architecturally and functionally complete in code**, operating under strict human governance.
