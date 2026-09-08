# BRUD AI — DATA PIPELINE AUDIT (WS18)
**Audit Date:** 2026-09-07

---

## DATA FLOW OVERVIEW

```
External Sources
    ↓
External Data Providers (external_data_provider_service.py)
    ↓
Document Ingestion (documents)
    ↓
Dataset Compilation (datasets + corpus)
    ↓
Dataset Verification (legal/quality/license)
    ↓
Sample Import & Quarantine
    ↓
Corpus Build (corpus service)
    ↓
RAG Indexing OR Training Data
    ├─ RAG → rag_ingestion_service → vector storage → retrieval
    └─ Training → SFT generator → training pipeline
```

---

## DOCUMENT PIPELINE

| Service | File | Size | Status |
|---------|------|------|--------|
| Document Service | `document_service.py` (7 KB) | ACTIVE |
| Document Content Service | `document_content_classification_service.py` | ACTIVE |
| Document Language Service | `document_language_service.py` | ACTIVE |
| Document SFT Pipeline | Multiple `document_sft_*` services | ACTIVE |
| Document Wizard | `document_wizard_service.py` | ACTIVE |
| Tamil Correction | `document_tamil_correction_registry_service.py` | ACTIVE |
| Tamil Correction Rules | `document_tamil_correction_rule_service.py` | ACTIVE |

---

## DATASET PIPELINE

| Service | File | Status |
|---------|------|--------|
| Dataset Service | `dataset_service.py` (27 KB) | ACTIVE |
| Dataset Quality | `dataset_quality_service.py` (21 KB) | ACTIVE |
| Dataset Governance | `dataset_governance_manifest_service.py` (9.7 KB) | ACTIVE |
| Dataset Discovery | `dataset_discovery_service.py` (14 KB) | ACTIVE |
| Dataset Verification Case | `dataset_verification_case_service.py` (14 KB) | ACTIVE |
| Dataset Verification Evidence | `dataset_verification_evidence_service.py` (14 KB) | ACTIVE |
| Dataset Verification Source Rights | `dataset_verification_source_rights_service.py` | ACTIVE |
| Dataset Versions | `dataset_version_service.py` | ACTIVE |

---

## SAMPLE IMPORT PIPELINE

A complete sample-level governance pipeline:

| Stage | Service | Status |
|-------|---------|--------|
| Import | `dataset_sample_import_service.py` | ACTIVE |
| Parsing | `dataset_sample_parsing_service.py` | ACTIVE |
| File Validation | `dataset_sample_file_validation_service.py` | ACTIVE |
| Normalization | `dataset_sample_normalization_service.py` | ACTIVE |
| Language Detection | `dataset_sample_language_service.py` | ACTIVE |
| Quality Check | `dataset_sample_quality_service.py` | ACTIVE |
| PII Safety | `dataset_sample_pii_safety_service.py` | ACTIVE |
| Poisoning Check | `dataset_sample_poisoning_service.py` | ACTIVE |
| Contamination Check | `dataset_sample_contamination_service.py` | ACTIVE |
| Security Scan | `dataset_sample_security_scan_service.py` | ACTIVE |
| Duplicate Detection | `dataset_sample_duplicate_service.py` | ACTIVE |
| Eligibility | `dataset_sample_eligibility_service.py` | ACTIVE |
| Quarantine | `dataset_sample_quarantine_service.py` | ACTIVE |
| Review | `dataset_sample_review_service.py` | ACTIVE |
| Archive Safety | `dataset_sample_archive_safety_service.py` | ACTIVE |
| Download | `dataset_sample_download_service.py` | ACTIVE |
| Report | `dataset_sample_report_service.py` | ACTIVE |

---

## CORPUS PIPELINE

| Service | File | Status |
|---------|------|--------|
| Corpus Ingestion | `corpus_ingestion_service.py` (53 KB) | ACTIVE |
| Corpus Compilation | `corpus_compilation_service.py` | ACTIVE |
| Corpus Balancing | `corpus_balancing_service.py` | ACTIVE |
| Corpus Quality | `corpus_quality_service.py` | ACTIVE |
| Corpus Language | `corpus_language_service.py` | ACTIVE |
| Corpus Dedup | `corpus_deduplication_service.py` | ACTIVE |
| Corpus Export | `corpus_export_service.py` | ACTIVE |
| Corpus Security | `corpus_security_service.py` | ACTIVE |
| Corpus Governance | `corpus_governance_service.py` | ACTIVE |
| Dataset Compiler | `core_model/corpus/dataset_compiler.py` | ACTIVE |

---

## EXTERNAL DATA PROVIDERS

| Component | Status |
|-----------|--------|
| Provider Registry | `SourceRegistryService` | ACTIVE |
| Connection Service | `ExternalDataProviderConnectionService` | ACTIVE |
| Credential Service | `ExternalDataProviderCredentialService` | ACTIVE |
| Verification Service | `ExternalDataProviderVerificationService` | ACTIVE |
| Gateway Bridge | `external_gateway_dataset_bridge` (models + service + route) | ACTIVE |

---

## SFT (SUPERVISED FINE-TUNING) DATA PIPELINE

| Service | Status |
|---------|--------|
| SFT Generation Services | `document_sft_*_service.py` (multiple) | ACTIVE |
| Instruction Tuning | `instruction_tuning_service.py` (74 KB) | ACTIVE |
| SFT Export | Via corpus_export | ACTIVE |

---

## KEY FINDINGS

1. **COMPREHENSIVE:** 17-stage sample import pipeline with dedicated service per stage
2. **COMPLETE:** Full corpus pipeline from ingestion to export
3. **ACTIVE:** Dataset governance with verification, rights, legal checks
4. **ACTIVE:** External data provider integration
5. **NO DUPLICATE PIPELINES** — clear sequential ownership
6. **RISK:** High number of services per domain may cause coordination complexity

---
*WS18 Complete*
