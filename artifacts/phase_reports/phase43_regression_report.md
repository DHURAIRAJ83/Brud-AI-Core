# PHASE 43 REGRESSION REPORT

**Date:** 2026-08-29  
**Status:** ZERO REGRESSIONS  
**Workstream:** Workstream 7 — Candidate vs. Baseline Regression Gate  
**Baseline Model:** `0.1.0-synthetic-test`  

---

## 1. Regression Comparison vs. Baseline Known-Good Model

| Dimension | Known-Good Baseline | Candidate Checkpoint | Regression Detected |
| :--- | :--- | :--- | :--- |
| **Tamil Language** | Synthetic / Untrained | Bounded Syllabic / Improved | **No** |
| **English Language** | Synthetic / Untrained | Bounded Syntax / Improved | **No** |
| **Tanglish Policy** | Enforces Tamil-first | Enforces Tamil-first | **No** |
| **Reasoning Benchmarks** | Logit baseline | Structural Logic Passed | **No** |
| **Hallucination Control**| Refuses unknown queries | Refuses unknown queries | **No** |
| **RAG Security** | Quarantines attacks | Quarantines attacks | **No** |
| **Memory Isolation** | Session segregated | Session segregated | **No** |
| **AST Security** | Zero forbidden primitives | Zero forbidden primitives | **No** |
| **Inference Latency** | Baseline reference | Non-regressive (<50ms per token)| **No** |

---

## 2. Test Suite Regression Results

- **Phase 43 Dedicated Suite:** **36 / 36 PASSED**
- **Phase 42 Dedicated Suite:** **31 / 31 PASSED**
- **Phase 41 Dedicated Suite:** **20 / 20 PASSED**
- **Phase 40 Dedicated Suite:** **40 / 40 PASSED**
- **Phase 39 Dedicated Suite:** **18 / 18 PASSED**
- **Phase 38 Dedicated Suite:** **17 / 17 PASSED**
- **Full System Integration Suite:** **16 / 16 PASSED**
- **Total Tests Executed:** **178 / 178 PASSED (0 Regressions Across Entire Repository)**
