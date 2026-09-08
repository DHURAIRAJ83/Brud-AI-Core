# WS08 DUPLICATE CODE FORENSIC AUDIT — FINAL EXECUTIVE REPORT

**Audit ID:** WS08-DUP-FORENSIC-2026-09-01  
**Audit Type:** INDEPENDENT READ-ONLY EVIDENCE-BASED FORENSIC AUDIT  
**Repository:** /home/dhurai/Projects/brud-ai  
**Auditor:** Principal AI Systems Architect & Repository Forensics Analyst  
**Zero mutations performed: TRUE**

---

## EXECUTIVE SUMMARY

The previously reported **"53 duplicate class names"** was an undercount due to scope exclusion of test files.

**Independent full-repository AST scan result:**
```
TOTAL DUPLICATE CLASS NAMES   = 71   (previous report: 53 — UNDERCOUNT)
TOTAL DUPLICATE OCCURRENCES   = 215  (previous report: ~150 — UNDERCOUNT)
```

**The majority are NOT dangerous duplicates.** Only 8 are true implementation duplicates, and none of them cause a runtime conflict today. The most important finding is a **forward-looking P0 architectural gap** — not a current bug.

---

## Q1: Are the reported 53 duplicates actually duplicates?

**Partially.** The count of 53 was a scope undercount. The correct total is 71 duplicate class names across 215 occurrences. Of these 71:

- 31 (44%) are **Intentional Specializations** — same name, domain-specific schemas (correct by design)
- 14 (20%) are **Versioned Implementations** — phase-progression artifacts preserved for audit traceability
- 11 (15%) are **Test Fixtures / Mocks** — local test helpers defined per-test-file
- 8 (11%) are **True Duplicates** — same name AND same implementation (consolidation candidates)
- 1 (1%) is an **Experimental Candidate** (BrudSmallV2Model — most important finding)
- 1 (1%) is **Legacy Compatibility** (FeedbackRepository phase2.py — dead code)
- 5 (7%) are **Uncertain** (require deeper human review)

---

## Q2: How many are true duplicates?

**8 duplicate class names (19 total occurrences):**
1. `HardwareProbeResponse` × 2 (identical)
2. `IngestProviderResultsRequest` × 2 (identical)
3. `ProviderOutput` × 2 (identical)
4. `RagAdminReviewRequest` × 2 (identical)
5. `RecordExposureTelemetry` × 2 (identical — phase-versioned)
6. `VoiceAudioDecodeError` × 2 (identical)
7. `FakeUploadFile` × 15 (identical test helper)
8. `Out` × 2 (identical test helper)

None of these 8 cause runtime confusion because each is isolated to its own import namespace.

---

## Q3: How many are intentional?

**31 class names (74 occurrences)** are intentional specializations (Classification B).  
Notable examples: `CreateSessionRequest` × 12, `AdminReviewRequest` × 14.  
These are correct by design — each carries domain-specific fields for its Mini Brain subsystem.

---

## Q4: How many are legacy?

**1 true legacy class** (C): `FeedbackRepository` in `phase2.py` — a Phase 2 snapshot file that was superseded by `feedback.py`.

**14 additional phase-versioned classes** (F): `GuardAction`, `GovernedRecord`, `OpenDomainStatus`, `CausalityVerdict`, etc. — retained as phase audit trail, not for runtime use.

---

## Q5: How many are dead/orphan?

**Classification G (dead/orphan): 0** formal dead classes detected.

However, these items are **functionally dead** despite being syntactically present:
- `InferenceEngine` in `core_model/inference/__init__.py` — raises `NotImplementedError`, never called
- `FeedbackRepository` in `phase2.py` — not imported by any production code
- 6,017 `adapter-it-at-*` checkpoint directories — not loaded by production code
- ~40 `phase59_ws*.md` root-level files — historical reports, no runtime use

---

## Q6: Which duplicate code is actually used by the Brud runtime?

**Production runtime uses ZERO duplicate class instances in ambiguous ways.** The active runtime paths:

| Path | Class Used | Which Instance |
|---|---|---|
| Public Chat → Inference | None of the duplicated classes | `GenerationEngine` (no duplicates) |
| Admin → Mini Brain Sessions | `CreateSessionRequest` | Each route uses its OWN module's definition |
| Admin → Dataset Pipeline | `AdminReviewRequest` | Each service uses its OWN module's definition |
| Training (E3) | `BrudSmallV2Model` | P4 — `run_e3_experiments.py` local definition |
| Evaluation (WS06) | `BrudSmallV2Model` | P2 — `run_capability_evaluation_ws06.py` local definition |

---

## Q7: Which code is the canonical implementation?

All 10 canonical implementations are resolved:

| Subsystem | Canonical |
|---|---|
| Model | `run_e3_experiments.py` — `BrudSmallV2Model` (local, E3 canonical) |
| Inference Runtime | `core_model/inference_runtime/` — `GenerationEngine` |
| Dataset Engine | `core_model/mini_brain/dataset_expansion/dataset_expansion_engine.py` |
| Translation | Same file — `_translate_to_english()` |
| Admin Assistant | `backend/services/admin_assistant_service.py` |
| Training Engine | `run_e3_experiments.py` — `run_training_experiment()` |
| RAG | `backend/services/rag_service.py` |
| Memory | `backend/services/conversation_memory_service.py` |
| Provider Gateway | `backend/services/mini_brain_external_ai_gateway_service.py` |
| Public Chat Orchestrator | `backend/services/public_chat_routing_service.py` |

---

## Q8: Is any duplicate dangerous?

**No currently dangerous duplicates.**

The only **forward-looking risk** (DRSK-01, P0):  
WS05 runner saves PE buffer in checkpoint (`persistent=True` default).  
WS06/WS07/E3 runners use `persistent=False`.  
**If E4/E5 loads the WS05 checkpoint with `strict=True` → RuntimeError.**  
Mitigated by using `strict=False` (already done in WS06) or stripping the `pe` key.

---

## Q9: What can safely be archived?

| Item | When |
|---|---|
| `data/core_models/checkpoints/adapter-it-at-*` (3.8GB) | After E6 |
| `phase59_ws*.md` root-level reports (~40 files) | After E6 |
| `core_model/inference/__init__.py` stub | After E6 (after removing import from `core_model/__init__.py`) |
| `backend/database/repositories/phase2.py` | After verification + E6 |
| Phase-versioned training guards (phase53/54) | After E6 |

---

## Q10: What MUST NOT be removed?

| Item | Reason |
|---|---|
| All 4 BrudSmallV2Model production runners | Each serves a distinct phase execution role; cryptographic baseline for audit |
| All 5 BrudSmallV2Model test copies | Required for test suite integrity |
| `CreateSessionRequest` × 12 | Each is the correct domain-specific schema for its Mini Brain module |
| `models/*.gguf` stub files (18–21 bytes) | Required path fixtures for security tests |
| `models/qwen2.5-*.gguf` (1.6GB total) | Real Qwen2.5 GGUF models for external provider |
| Phase 59 manifest JSON files | Cryptographic baselines for test suite |
| WS04 training config | SHA-256 locked baseline for E3 training |
| `phase44_runtime_governance.py` | Governance enforcement — MUST NOT be touched |

---

## Q11: Will E4/E5 architecture scaling be affected by these duplicates?

**YES — one specific risk:**

The WS05 runner checkpoint includes `pe` in `state_dict` (unexpected key for E4/E5 loaders using `persistent=False`).

**Mandatory action before E4/E5 training begins:**
```
Either:
  a) Explicitly use strict=False when loading any WS05-era checkpoint in E4/E5 runners, OR
  b) Pre-process the WS05 checkpoint to strip the 'pe' key before E4/E5 starts
```

No other duplicate causes direct E4/E5 impact.

---

## Q12: Does Admin Assistant Mini Brain have conflicting implementations?

**No.** Zero conflicts found. All Admin Assistant components use their own isolated schema classes. No cross-module confusion is possible.

---

## Q13: Does the Dataset → Review → Training pipeline have duplicate/conflicting implementations?

**No.** The pipeline is cleanly sequential:
```
DatasetExpansionEngine (no duplicates)
  → AdminReviewRequest (domain-specific per module, no cross-contamination)
  → Dataset Sealing (no duplicates)
  → BrudSmallV2Model in E3 runner (canonical P4 version)
```

---

## Q14: Does Public Chat have duplicate/conflicting model routing?

**No.** `PublicChatRoutingService` has no duplicates. Model routing uses `InferenceRuntimeService` which loads via file path — it does not instantiate `BrudSmallV2Model` from any of the duplicate runner files.

---

## Q15: What should be cleaned before E4/E5?

```
MANDATORY (P0):
  1. Verify E4/E5 runners use strict=False when loading WS05 checkpoint OR strip 'pe' key
  2. Create core_model/architecture/brud_small_v2.py as shared model module
  3. Create core_model/training/brud_training_engine.py as shared training engine

RECOMMENDED (P1):
  4. Consolidate HardwareProbeResponse, IngestProviderResultsRequest, ProviderOutput,
     RagAdminReviewRequest, AdminReviewRequest (11-group) into backend/models/shared.py
```

---

## Q16: What can wait until after E6?

```
P2 (Technical debt, harmless):
  - VoiceAudioDecodeError consolidation
  - FakeUploadFile → conftest.py migration

P3 (Historical):
  - Archive adapter-it-at-* checkpoints (3.8GB)
  - Archive phase59_ws*.md reports
  - Archive core_model/inference/ stub
  - Archive backend/database/repositories/phase2.py
  - Phase-versioned guard/evaluator archiving
```

---

## Q17: What is the exact next technical action?

```
NEXT ACTION: Phase 60 WS07 Stage C — E4 Context Scaling (T=128 → T=512)

BEFORE STARTING THAT, complete these pre-E4 verification steps:
  Step 1: Document that E4/E5 runners must use strict=False for checkpoint loading
  Step 2: Create core_model/architecture/brud_small_v2.py (canonical model module)
  Step 3: Create core_model/training/brud_training_engine.py (canonical training engine)
  
  These steps require human authorization and design review before implementation.
```

---

## DUPLICATE CODE STATUS CLASSIFICATION

```
═══════════════════════════════════════════════════════════════
    DUPLICATE CODE STATUS: MINOR TECHNICAL DEBT
═══════════════════════════════════════════════════════════════

Not: CLEAN (71 duplicates exist)
Not: REQUIRES CLEANUP (no active runtime conflicts)
Not: HIGH RISK (no current production failures)
Not: CRITICAL (no security or data integrity issues)

CLASSIFICATION: MINOR TECHNICAL DEBT

The 71 duplicate class names are:
  - 44% intentional by design (B)
  - 20% phase-versioned history (F)  
  - 11% true duplicates awaiting consolidation (A)
  - No current production conflicts

One forward-looking P0 risk exists (BrudSmallV2Model PE checkpoint key)
that MUST be documented and handled before E4/E5 training begins.
═══════════════════════════════════════════════════════════════
```

---

## FINAL GOVERNANCE STATE

```
REPOSITORY MUTATION: FALSE ✅
TRAINING EXECUTION: BLOCKED ✅
OPTIMIZER STEPPING: FALSE ✅
WEIGHT MUTATION: FALSE ✅
CANDIDATE TRAFFIC: 0.0% ✅
PUBLIC CHAT: BLOCKED ✅
PRODUCTION PROMOTION: BLOCKED ✅

AUDIT COMPLETE. REPOSITORY UNMODIFIED.
ZERO FILES MODIFIED, DELETED, MOVED, OR RENAMED.
```

---

## Artifact Directory

All 21 forensic reports at:  
[`artifacts/system_audit/duplicate_forensics/`](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/)

| # | Report |
|---|---|
| [01](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/01_duplicate_inventory.md) | Duplicate Inventory — 71 names, 215 occurrences |
| [02](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/02_class_duplicate_analysis.md) | Class-by-Class Analysis — A/B/C/D/E/F/G/H classification |
| [03](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/03_brud_small_v2_comparison.md) | BrudSmallV2Model × 9 — PE key risk, canonical=E3 runner |
| [04](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/04_create_session_request_comparison.md) | CreateSessionRequest × 12 — intentional, domain-specific |
| [05](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/05_parallel_directory_analysis.md) | Parallel Directories — research_center/CLC/inference analysis |
| [06](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/06_config_duplicate_analysis.md) | Config Duplicates — 6017 adapter checkpoints (historical) |
| [07](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/07_dead_orphan_analysis.md) | Dead/Orphan Code — GGUF stubs, inference stub, phase59 md |
| [08](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/08_import_usage_graph.md) | Import Graph — zero cross-module confusion confirmed |
| [09](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/09_runtime_ownership_trace.md) | Runtime Ownership — which instance each path uses |
| [10](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/10_admin_assistant_duplicate_impact.md) | Admin Assistant Impact — ZERO impact confirmed |
| [11](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/11_training_pipeline_duplicate_impact.md) | Training Pipeline Impact — PE checkpoint risk for E4/E5 |
| [12](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/12_security_duplicate_impact.md) | Security Impact — 0 critical/high, 2 low severity |
| [13](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/13_canonical_architecture.md) | Canonical Architecture — all 10 canonicals resolved |
| [14](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/14_cleanup_recommendations.md) | Cleanup Recommendations — P0/P1/P2/P3 ranked |
| [15](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/15_duplicate_risk_register.md) | Risk Register — DRSK-01 through DRSK-10 |
| [16](file:///home/dhurai/Projects/brud-ai/artifacts/system_audit/duplicate_forensics/16_duplicate_forensics_final.md) | This report — Q1–Q17 final answers |
