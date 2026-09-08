# Master Brud AI End-to-End Audit — 09: Dataset Pipeline & Ingestion Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal Data Architect & Pipeline Auditor  
**Confidence Rating:** HIGH CONFIDENCE (Verified by route handlers, parser modules, and database repositories)  

---

## 1. Trace of Admin Dataset Submission & Ingestion Pipeline

```
[ Admin Dataset Submission ]
(CSV, JSON, JSONL, TXT, PDF, Word Lists, Q&A)
               │
               ▼ POST /api/admin/dataset-sample-imports / POST /api/admin/manual-data
[ Ingestion & Parsing ]
  - Modules: backend/services/dataset_sample_pipeline_service.py, document_service.py
  - Status: ✅ IMPLEMENTED (Extracts text, parses lines, checks MIME types)
               │
               ▼
[ Normalization & Unicode Purity ]
  - Modules: core_model/nlp/text_processor.py, dataset_expansion_validator.py
  - Status: ✅ IMPLEMENTED (NFC normalization, zero-width character stripping)
               │
               ▼
[ Language Detection & Categorization ]
  - Modules: core_model/rag/language_routing.py (classify_language)
  - Status: ✅ IMPLEMENTED (Unicode script ratio: Tamil vs Latin vs Mixed vs Tanglish)
               │
               ▼
[ Quality & Safety Validation ]
  - Modules: backend/services/dataset_sample_quarantine_service.py
  - Status: ✅ IMPLEMENTED (PII checks, file safety, corruption detection, quarantine routing)
               │
               ▼
[ Duplicate & Contamination Detection ]
  - Modules: dataset_expansion_validator.py, core_model/training/phase54_memorization_guard.py
  - Status: ✅ IMPLEMENTED (SHA-256 deduplication and Phase 53 air-gap leak check)
               │
               ▼
[ AI Expansion / Translation ]
  - Modules: core_model/admin_assistant/dataset_expansion_engine.py
  - Status: 🟡 PARTIAL (7-mode deterministic expansion operational for 10 core concepts;
                        NOT automatically wired into the sample import upload endpoint)
               │
               ▼
[ Admin Review Queue ]
  - Modules: backend/services/admin_assistant_dataset_expansion_service.py
  - Status: ✅ IMPLEMENTED (Proposals enter 'PENDING' queue; admin decides APPROVE/REJECT)
               │
               ▼
[ Approval & Dataset Versioning ]
  - Modules: backend/database/repositories/dataset_admin.py, dataset_expansion_service.py
  - Status: ✅ IMPLEMENTED (Assigns immutable version string, e.g. 'v001')
               │
               ▼
[ Cryptographic SHA-256 Sealing ]
  - Modules: backend/services/admin_assistant_dataset_expansion_service.py::seal_dataset
  - Status: ✅ IMPLEMENTED (Outputs immutable JSONL with manifest SHA-256 digest)
```

---

## 2. Identified Missing Connections in Dataset Pipeline

1. **Gap 1: Auto-Trigger from Document Import to Expansion Engine**
   - *Current State:* When an admin uploads a file via `/api/admin/dataset-sample-imports`, it is quarantined, parsed, and approved as an imported sample. However, it does **not** automatically trigger `dataset_expansion_engine.py` to generate translations or Tanglish pairs.
   - *Workaround Today:* Expansion proposals must be triggered explicitly via the expansion API (`/api/admin/dataset-expansion/proposals/generate`) or script runner (`run_e3_expansion_proposals.py`).
   - *Severity:* Medium (Operational friction, but maintains governance control).
2. **Gap 2: PDF Layout / Table Extraction**
   - *Current State:* Plain text and basic paragraphs extract reliably from PDFs via PyPDF2. Complex tables, multi-column layouts, and scanned images without text layers are skipped or quarantined as unreadable text.
   - *Severity:* Low (Standard for local CPU-based parsers).
