# BRUD AI — TEST AUDIT (WS13)
**Audit Date:** 2026-09-07

---

## TEST INVENTORY

Total test files: 562 (Python) + ~50 JSX test files + Playwright E2E

---

## BACKEND TESTS (tests/backend/)

### Admin Assistant Tests
| Test File | Tests | Status |
|-----------|-------|--------|
| test_admin_assistant_api.py | Admin Assistant API | ACTIVE |
| test_admin_assistant_api_phase8.py | Phase 8 specific | ACTIVE |
| test_admin_assistant_chat_service.py | Chat service | ACTIVE |
| test_admin_assistant_context_repository.py | Context repo | ACTIVE |
| test_admin_assistant_dataset_discovery_integration.py | Integration | ACTIVE |
| test_admin_assistant_document_navigation.py | Navigation | ACTIVE |
| test_admin_assistant_external_data_provider_integration.py | Integration | ACTIVE |
| test_admin_assistant_governance_route.py | Governance | ACTIVE |
| test_admin_assistant_language_deterministic_responses.py | Language | ACTIVE |
| test_admin_assistant_language_preference_api.py | Language API | ACTIVE |
| test_admin_assistant_language_service.py | Language service | ACTIVE |
| test_admin_assistant_lifecycle.py | Lifecycle | ACTIVE |
| test_admin_assistant_llm_language_enforcement.py | LLM language | ACTIVE |
| test_admin_assistant_tools.py | Tool execution | ACTIVE |

### Dataset Tests
| Test File | Status |
|-----------|--------|
| test_dataset_api.py | ACTIVE |
| test_dataset_discovery_api.py | ACTIVE |
| test_dataset_discovery_security.py | ACTIVE |
| test_dataset_governance_manifest_service.py | ACTIVE |
| test_dataset_phase6.py | ACTIVE |
| test_dataset_sample_archive_safety_service.py | ACTIVE |
| test_dataset_sample_contamination_service.py | ACTIVE |
| test_dataset_sample_deletion_service.py | ACTIVE |
| test_dataset_sample_download_service.py | ACTIVE |
| test_dataset_sample_duplicate_service.py | ACTIVE |
| test_dataset_sample_eligibility_service.py | ACTIVE |
| test_dataset_sample_file_validation_service.py | ACTIVE |
| test_dataset_sample_import_api.py | ACTIVE |
| test_dataset_sample_import_security.py | ACTIVE |
| test_dataset_sample_language_service.py | ACTIVE |
| test_dataset_sample_normalization_service.py | ACTIVE |
| test_dataset_sample_parsing_service.py | ACTIVE |
| test_dataset_sample_pii_safety_service.py | ACTIVE |
| test_dataset_sample_poisoning_service.py | ACTIVE |
| test_dataset_sample_quality_service.py | ACTIVE |
| test_dataset_sample_quarantine_service.py | ACTIVE |
| test_dataset_sample_report_service.py | ACTIVE |
| test_dataset_sample_review_service.py | ACTIVE |
| test_dataset_sample_security_scan_service.py | ACTIVE |
| test_dataset_verification_api.py | ACTIVE |
| test_dataset_verification_case_service.py | ACTIVE |
| test_dataset_verification_evidence_service.py | ACTIVE |
| test_dataset_verification_permission_service.py | ACTIVE |
| test_dataset_verification_report_service.py | ACTIVE |
| test_dataset_verification_security.py | ACTIVE |
| test_dataset_verification_source_rights_service.py | ACTIVE |
| test_dataset_verification_transport.py | ACTIVE |

### Core Tests
| Test File | Status |
|-----------|--------|
| test_api.py | ACTIVE |
| test_auth.py | ACTIVE |
| test_config.py | ACTIVE |
| test_conversation_memory_api.py | ACTIVE |
| test_corpus_api.py | ACTIVE |

---

## PHASE 28 SUBPROCESS RUNNERS (Test Infrastructure)

9 files: `_phase28b_subprocess_runner.py` through `_phase28j_subprocess_runner.py`
- These are subprocess harness helpers for concurrency/isolation tests
- NOT test cases themselves
- **Status:** TEST_INFRASTRUCTURE (not test cases)

---

## FRONTEND TESTS (apps/admin-dashboard/src/test/)

Using Vitest:
- ~50 .test.jsx files co-located with pages/components
- MiniBrainPage.test.jsx (43 KB) — comprehensive
- DocumentsPage.test.jsx (26 KB) — comprehensive
- ManualDataPage.test.jsx (14 KB)
- ProductionReadinessPage.test.jsx (14 KB)

---

## E2E TESTS

- `apps/admin-dashboard/e2e/` — Playwright E2E
- `tests/e2e/` — Python E2E tests
- Playwright config: `playwright.config.js`

---

## FALSE CONFIDENCE RISK ASSESSMENT

### Potential False Confidence Tests

| Test | Risk | Reason |
|------|------|--------|
| test_admin_assistant_api_phase8.py | MEDIUM | Tests Phase 8 system; MB-28 is separate parallel system |
| Subprocess runner tests | LOW | Test infrastructure, not business logic |
| tests/evaluation/ | MEDIUM | May test model evaluation framework, not real model quality |

---

## TEST COVERAGE GAPS

| Area | Coverage | Notes |
|------|----------|-------|
| Mini Brain Intelligence (Phase 17) | HIGH | tests/core_model/mini_brain/ |
| Memory System | HIGH | Multiple dedicated test files |
| Admin Assistant | HIGH | 14+ test files |
| Dataset Pipeline | HIGH | 30+ test files |
| RAG Pipeline | MEDIUM | Some tests exist |
| Public Chat | MEDIUM | Some tests |
| Inference Runtime | LOW | Limited tests found |
| Provider Routing | LOW | Mock-based only |
| Voice Runtime | LOW | Likely placeholder |
| Vision Pipeline | LOW | Likely placeholder |

---

## FINDINGS

1. **COMPREHENSIVE:** Test coverage for Admin Assistant, Dataset pipeline, Memory system
2. **HIGH:** Dataset sample processing tests are very thorough (30+ files)
3. **GAP:** Inference runtime has limited test coverage
4. **GAP:** Provider routing tested primarily with mocks
5. **GAP:** ~40% of admin dashboard pages have no test file
6. **INFRASTRUCTURE:** 9 subprocess runner files are test helpers, not test cases
7. **RISK:** Some tests may test Phase 8 Admin Assistant but not MB-28 path

---
*WS13 Complete*
