# Phase 61 WS01 Report — 02: Existing Pipeline Dependency Map

| Subsystem Component | Canonical File Path | Status | Reusability | Action Taken |
|---|---|---|---|---|
| **Ingestion Pipeline** | `backend/services/corpus_ingestion_service.py` | REAL | 100% Reusable | Reused cleanly |
| **Quality Filter** | `backend/services/dataset_sample_quality_service.py` | REAL | 100% Reusable | Reused cleanly |
| **Mini Brain Proposal** | `backend/services/admin_mini_brain_service.py` | REAL | 100% Reusable | Reused cleanly |
| **Provider Gateway** | `backend/services/external_provider_service.py` | REAL | 100% Reusable | Reused cleanly |
| **Runtime Governance** | `core_model/release/phase44_runtime_governance.py` | REAL | 100% Reusable | Reused cleanly |
