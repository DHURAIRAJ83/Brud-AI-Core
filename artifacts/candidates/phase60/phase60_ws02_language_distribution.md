# Phase 60 WS02 — Language Distribution Specification

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS02 — Dataset Expansion Architecture & Curation Specification  
**Date:** 2026-08-31  
**Status:** ✅ **LANGUAGE DISTRIBUTION LOCKED (35 / 35 / 20 / 10)**

---

## 1. Distribution Targets

| Language Code | Language Category | Target Percentage | Target Records | Train (80%) | Val (10%) | Test (10%) |
|---|---|---|---|---|---|---|
| `ta` | Tamil (Native Script) | 35.0% | **700** | 560 | 70 | 70 |
| `en` | English | 35.0% | **700** | 560 | 70 | 70 |
| `mixed` | Mixed Bilingual (ta + en) | 20.0% | **400** | 320 | 40 | 40 |
| `tgl` | Tanglish (Latin Script) | 10.0% | **200** | 160 | 20 | 20 |
| **TOTAL** | **Complete Dataset** | **100.0%** | **2,000** | **1,600** | **200** | **200** |

---

## 2. Tanglish Sub-Distribution (LIM-WS04-01 Remediation)
To prevent Tanglish from collapsing into a single narrow domain, the 200 Tanglish records are distributed across:
- Conversational Exchanges: 60 records (30%)
- Instruction Following: 40 records (20%)
- Explanation & Concepts: 30 records (15%)
- Factual QA: 30 records (15%)
- Bidirectional Translation: 20 records (10%)
- Mixed Interaction: 20 records (10%)
