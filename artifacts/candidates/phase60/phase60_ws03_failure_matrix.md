# Phase 60 WS03 — Failure & Fallback Matrix

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS03 — Dataset Curation, Ingestion & Quality Validation  
**Date:** 2026-08-31  
**Status:** ✅ **VERIFIED & SEALED**  

---

## 1. Operational Failure & Fallback Protocols
| Failure Mode | Detection Mechanism | Immediate Action | Fallback Strategy | Status |
|---|---|---|---|---|
| Schema Mismatch | Automated validator | Reject candidate record | Re-validate against WS02 JSON schema | ✅ Handled |
| Tokenizer UNK > 0 | SentencePiece encode check | Quarantine record | Re-encode with native vocabulary pieces | ✅ Handled |
| Sequence Length > 128 | Token count assertion | Trim response / reject | Bounded response truncation | ✅ Handled |
| Benchmark Contamination | Exact & n-gram probe scan | Immediate quarantine | Regenerate distinct sovereign prompt | ✅ Handled |
| Duplicate Instruction | Hash set membership check | Discard candidate | Sample alternative prompt formulation | ✅ Handled |
