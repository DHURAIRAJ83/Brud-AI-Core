# Phase 60 WS01 — Dataset Expansion Specification

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS01 — Post-Training Diagnostic & Capability Gap Baseline  
**Date:** 2026-08-31  
**Status:** ✅ **PHASE 60 DATASET ARCHITECTURE SPECIFIED (DESIGN-ONLY)**

---

## 1. Quantitative Target Architecture

- **Total Target Records:** **1,500 – 2,500 records** ($4\times - 6\times$ increase over Phase 55).
- **Partition Splits:**
  - Training Split: 1,200 – 2,000 records (80%)
  - Validation Split: 150 – 250 records (10%)
  - Held-Out Test Split: 150 – 250 records (10%)

---

## 2. Target Task Distribution

| Task Category | Target Percentage | Target Records (approx) | Primary Capabilities Addressed |
|---|---|---|---|
| **Definition & Concepts** | 20% | 300 – 500 | CAP-01, CAP-08, CAP-09 |
| **Factual QA & Knowledge** | 20% | 300 – 500 | CAP-02, CAP-07, CAP-15 |
| **Dialogue & Conversational**| 15% | 225 – 375 | CAP-04, CAP-05, CAP-10 |
| **Directives & Constraints** | 15% | 225 – 375 | CAP-06, CAP-20 |
| **Structured Output (JSON)** | 10% | 150 – 250 | CAP-16, CAP-23 |
| **Tool Boundaries & Math** | 10% | 150 – 250 | CAP-13, CAP-14, CAP-24 |
| **Safety & Refusals** | 5% | 75 – 125 | CAP-18 |
| **Translation & Summary** | 5% | 75 – 125 | CAP-21, CAP-22 |

---

## 3. Target Language Distribution
- **Tamil (ta):** 35%
- **English (en):** 35%
- **Mixed Bilingual (mixed):** 20%
- **Tanglish (tgl):** 10% (at least 150 – 250 records)
