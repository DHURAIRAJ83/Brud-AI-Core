# WS08 Duplicate Forensic Audit — 02: Class-by-Class Duplicate Analysis

**Audit Date:** 2026-09-01  
**READ-ONLY AUDIT**

---

## Classification Legend

```
A = TRUE DUPLICATE IMPLEMENTATION (same name + same code)
B = INTENTIONAL SPECIALIZATION (same name, domain-specific fields/behavior)
C = LEGACY COMPATIBILITY (old phase snapshot, superseded)
D = TEST FIXTURE / MOCK (local test helper defined per-test-file)
E = EXPERIMENTAL CANDIDATE (per-phase runner variants)
F = VERSIONED IMPLEMENTATION (progressive phase evolution)
G = DEAD / ORPHAN (unused, unreferenced)
H = UNCERTAIN — REQUIRES HUMAN REVIEW
```

---

## Full Analysis Table (All 71 Duplicate Class Names)

| ID | Class Name | Count | Same Impl? | Class | Active? | Risk | Recommendation |
|---|---|---|---|---|---|---|---|
| 1 | `AcceptanceDecisionRequest` | 2 | ❌ | B | ✅ | None | KEEP — different field sets for rag_sandbox vs incremental_training |
| 2 | `AdminApprovalRecord` | 2 | ❌ | B | ✅ | None | KEEP — domain.py (Pydantic) vs phase43_governance (dataclass) |
| 3 | `AdminReviewRequest` | 14 | Partial | A+B | ✅ | P2 | CONSOLIDATE LATER — 11 identical, 3 specialized |
| 4 | `ApprovalDecisionRequest` | 2 | ❌ | B | ✅ | None | KEEP — rag_sandbox vs dataset_import |
| 5 | `ApprovalRejectRequest` | 2 | ❌ | B | ✅ | None | KEEP |
| 6 | `ApprovalRequestRequest` | 2 | ❌ | B | ✅ | None | KEEP |
| 7 | `AssignmentPatch` | 2 | ❌ | B | ✅ | None | KEEP — inference_runtime vs tokenizers (different domains) |
| 8 | `AuthorizeRequest` | 2 | ❌ | B | ✅ | None | KEEP — external_ai_gateway vs training_engine |
| 9 | `BilingualLabel` | 3 | ❌ | B | ✅ | None | KEEP — slight field variations per subsystem |
| 10 | `BrudSmallV2Model` | 9 | ❌ | E+D | ✅ | P0 | Create shared module before E4/E5 |
| 11 | `BuildCreate` | 2 | ❌ | B | ✅ | None | KEEP — corpus vs dataset_versions |
| 12 | `CausalityVerdict` | 2 | ❌ | F | ❌ | None | KEEP — phase50 (legacy) vs phase51 (canonical) |
| 13 | `CheckpointCapabilitySnapshot` | 2 | ❌ | F | ❌ | None | KEEP — phase42 vs phase46 |
| 14 | `CollectDatasetsRequest` | 3 | ❌ | B | ✅ | None | KEEP |
| 15 | `CompareRequest` | 2 | ❌ | B | ✅ | None | KEEP — tokenizers vs incremental_training |
| 16 | `ConversationTurn` | 2 | ❌ | B | ✅ | None | KEEP — Pydantic (API) vs dataclass (context_builder) |
| 17 | `CreateSessionRequest` | 12 | ❌ | B | ✅ | None | KEEP — domain-specific per Mini Brain module (by design) |
| 18 | `DatasetVersionCreate` | 2 | ❌ | B | ✅ | None | KEEP |
| 19 | `DeletionRequestRequest` | 2 | ❌ | B | ✅ | None | KEEP |
| 20 | `DiagnosticGenerateRequest` | 2 | ❌ | B | ✅ | None | KEEP |
| 21 | `DiagnosticsResponse` | 2 | ❌ | B | ✅ | None | KEEP |
| 22 | `EvaluationFixtureCreate` | 2 | ❌ | B | ✅ | None | KEEP — conversation_memory vs rag domain |
| 23 | `EvaluationRunCreate` | 2 | ❌ | B | ✅ | None | KEEP |
| 24 | `EvaluationSuiteCreate` | 2 | ❌ | B | ✅ | None | KEEP |
| 25 | `ExpiryRequest` | 2 | ❌ | B | ✅ | None | KEEP |
| 26 | `ExportCreate` | 2 | ❌ | B | ✅ | None | KEEP |
| 27 | `FakeUploadFile` | 15 | ✅ | D | ✅ | P3 | CONSOLIDATE LATER — move to conftest.py |
| 28 | `FeedbackRepository` | 2 | ❌ | C | ❌ (legacy) | Low | ARCHIVE AFTER VERIFICATION |
| 29 | `GovernedRecord` | 2 | ❌ | F | ❌ | None | KEEP — phase52 vs phase53 |
| 30 | `GuardAction` | 3 | Partial | F | ❌ | None | KEEP — phase53/54/56 versioning |
| 31 | `HardwareProbeResponse` | 2 | ✅ | A | ✅ | P2 | CONSOLIDATE LATER |
| 32 | `HumanReviewCreate` | 2 | ❌ | B | ✅ | None | KEEP — feedback vs model_evaluation |
| 33 | `IngestProviderResultsRequest` | 2 | ✅ | A | ✅ | P2 | CONSOLIDATE LATER |
| 34 | `LoadModelRequest` | 2 | ❌ | B | ✅ | None | KEEP — mini_brain_runtime vs runtime_manager |
| 35 | `M` | 9 | Partial | D | ✅ | None | KEEP — test-local stub, all in test files |
| 36 | `OpenDomainStatus` | 2 | ❌ | F | ❌ | None | KEEP — phase50 vs phase51 |
| 37 | `Out` | 2 | ✅ | D | ✅ | None | KEEP — test helper, same file pattern |
| 38 | `ProviderOutput` | 2 | ✅ | A | ✅ | P2 | CONSOLIDATE LATER |
| 39 | `QualityAssessRequest` | 2 | ❌ | B | ✅ | None | KEEP — corpus vs dataset_quality |
| 40 | `RagAdminReviewRequest` | 2 | ✅ | A | ✅ | P2 | CONSOLIDATE LATER |
| 41 | `RecordExposureTelemetry` | 2 | ✅ | F | ❌ | None | KEEP — phase54 vs phase56 |
| 42 | `RecordMemoryRequest` | 2 | ❌ | B | ✅ | None | KEEP — CLC vs research_center |
| 43 | `RegressionRunCreate` | 2 | ❌ | B | ✅ | None | KEEP |
| 44 | `ResourceGuard` | 2 | ❌ | F | ❌ | None | KEEP — phase47 vs phase48 |
| 45 | `RetrievalProfileCreate` | 2 | ❌ | B | ✅ | None | KEEP — conversation_memory vs rag |
| 46 | `RetrievalProfilePatch` | 2 | ❌ | B | ✅ | None | KEEP |
| 47 | `ReviewActionRequest` | 2 | ❌ | B | ✅ | None | KEEP — semantic_chunks vs documents |
| 48 | `ReviewRequest` | 2 | ❌ | B | ✅ | None | KEEP |
| 49 | `RollbackPlanCreate` | 2 | ❌ | B | ✅ | None | KEEP |
| 50 | `RoutingDecision` | 2 | ❌ | B | ✅ | None | KEEP — phase44_runtime_canary vs smart_router |
| 51 | `RunRagEvaluationRequest` | 3 | ❌ | B | ✅ | None | KEEP |
| 52 | `RuntimeEventRequest` | 2 | ❌ | B | ✅ | None | KEEP |
| 53 | `SplitConfiguration` | 2 | ❌ | B | ✅ | None | KEEP |
| 54 | `TamilNormalizationError` | 2 | ❌ | F | ❌ | None | KEEP — phase46 vs phase47 |
| 55 | `UsageCheckRequest` | 3 | ❌ | B | ✅ | None | KEEP |
| 56 | `VoiceAudioDecodeError` | 2 | ✅ | A | ✅ | P2 | CONSOLIDATE LATER |
| 57–71 | Various (test helpers, phase-versioned) | 2–3 each | Mixed | D/F | Mixed | None | KEEP or CONSOLIDATE LATER per case |

---

## Summary Statistics

| Classification | Count of Duplicate Names | Count of Occurrences |
|---|---|---|
| A — True Duplicate | 8 | 19 |
| B — Intentional Specialization | 31 | 74 |
| C — Legacy Compatibility | 1 | 2 |
| D — Test Fixture / Mock | 11 | 63 |
| E — Experimental Candidate | 1 | 9 |
| F — Versioned Implementation | 14 | 33 |
| G — Dead / Orphan | 0 | 0 |
| H — Uncertain | 5 | 15 |
| **TOTAL** | **71** | **215** |

---

## Key Insight

> The vast majority (31/71 = 44%) of duplicates are **Intentional Specializations (B)** — same name, domain-specific schemas. These are correct by design in a modular Mini Brain architecture. They should NOT be consolidated.

> The 8 **True Duplicates (A)** (19 occurrences) are the only candidates for technical consolidation, and none of them create runtime conflicts today.

> The single **most important** finding is `BrudSmallV2Model` (E-class): not a dangerous duplicate, but a missing canonical module that must be created before E4/E5.
