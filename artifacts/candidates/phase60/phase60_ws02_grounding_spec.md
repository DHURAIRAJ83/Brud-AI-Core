# Phase 60 WS02 — Grounding & Context Derivation Specification

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS02 — Dataset Expansion Architecture & Curation Specification  
**Date:** 2026-08-31  
**Status:** ✅ **GROUNDING ARCHITECTURE LOCKED (80 TARGET RECORDS)**

---

## 1. Grounding Protocol
- Input format: `<user>Context: {passage} Question: {query}<assistant>`
- The answer must be derived strictly from the supplied `optional_context`.
- Negative testing: If context lacks the answer, the model must explicitly state "Based on the provided text, the answer is not mentioned."
