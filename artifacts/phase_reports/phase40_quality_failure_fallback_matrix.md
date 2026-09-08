# PHASE 40 QUALITY FAILURE AND FALLBACK MATRIX

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Scope:** Comprehensive 27-Scenario Failure, Exception & Fallback Specifications  

---

| ID | Condition / Trigger | Expected System Behavior | Verification Method | Severity | Fallback Strategy |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SC-01** | Missing dataset file | Pipeline raises FileNotFoundError | Unit test path check | BLOCK | Reject job; log missing archive |
| **SC-02** | Corrupted dataset format | Stream JSONL skips corrupt lines | `test_001_production_dataset` | WARN | Quarantine malformed records |
| **SC-03** | Dataset hash mismatch | Manifest verification fails | Checksum comparison | BLOCK | Abort ingestion; flag tampering |
| **SC-04** | Unauthorized dataset | Provenance/license check fails | `test_002_dataset_provenance` | BLOCK | Reject unvetted corpus sources |
| **SC-05** | Bad / restricted license | Pipeline rejects commercial restrict| License taxonomy check | BLOCK | Do not admit into pretraining |
| **SC-06** | Malformed / short record | Filter rejects text <15 characters | Length boundary check | WARN | Discard record; update telemetry |
| **SC-07** | Excessive duplicates | Exact / near duplicate filters | `test_007` & `test_008` | WARN | Deduplicate clusters to 1 copy |
| **SC-08** | Tokenizer missing | SPM import error intercepted | Graceful skip / error | BLOCK | Halt tokenizer operations |
| **SC-09** | Tokenizer vocab mismatch | Config validation detects gap | `test_015_tokenizer_model` | BLOCK | Refuse model initialization |
| **SC-10** | Architecture mismatch | Non-divisible head dimension | `BrudModelConfig.validate` | BLOCK | Reject configuration before run |
| **SC-11** | Insufficient host RAM | `verify_resource_feasibility` fails | `test_017_cpu_resource` | BLOCK | Gracefully pause; prevent OOM |
| **SC-12** | Insufficient host disk | Resource Guard detects <500MB free | `assess_resource_guard` | BLOCK | Refuse checkpoint write |
| **SC-13** | Training interruption | Process terminates mid-epoch | Step metrics recorded | WARN | Resume from latest valid ckpt |
| **SC-14** | Checkpoint corruption | Checksum mismatch in manifest | `test_026_corruption` | BLOCK | Revert to previous good ckpt |
| **SC-15** | Validation degradation | Validation loss fails to improve | Step telemetry tracking | WARN | Retain best validation ckpt |
| **SC-16** | Tamil quality failure | Model outputs malformed Tamil | Linguistic evaluation | WARN | Retain model in candidate stage |
| **SC-17** | English quality failure | Model fails instruction bounds | Offline evaluation | WARN | Retain model in candidate stage |
| **SC-18** | Reasoning failure | Multi-step deduction fails | Deterministic task suite | WARN | Report WARN; prevent promotion |
| **SC-19** | RAG prompt injection | Document contains hidden attack | `assess_context_item` | BLOCK | Quarantine chunk; refuse exec |
| **SC-20** | Memory leakage attempt | Cross-session token inspection | UUID session check | BLOCK | Reject cross-session retrieval |
| **SC-21** | Hallucination attempt | Query lacks ground-truth chunk | Citation confidence check| WARN | Return safe uncertainty message |
| **SC-22** | AST safety failure | Codebase contains forbidden eval | `test_034_ast_security` | BLOCK | Terminate release immediately |
| **SC-23** | Canary telemetry drop | Error rate spikes in canary stage | `CanaryManager.rollback` | BLOCK | Immediate atomic rollback |
| **SC-24** | Approval missing | Model lacks admin sign-off | `test_037_canary_governance`| BLOCK | Retain in ADMIN_REVIEW |
| **SC-25** | Rollback required | Human curator triggers rollback | `test_038_atomic_rollback` | WARN | Restore active release |
| **SC-26** | Production DB mutation | DB checksum or size changes | `test_039_production_db` | BLOCK | Immediate hard halt |
| **SC-27** | Public chat scope leak | Public request targets admin scope | Resolver scope gate | BLOCK | Return 403 Forbidden / null |
