# Document SFT Workflow — Finalization Plan

Based on `document_sft_finalization_audit.md`. Strictly additive: one forward-only
migration (schema 43→44), new services, new routes, new frontend tabs, new Admin
Assistant tools/proposals. Migration 043 is never touched.

## 1. Existing components to reuse (unmodified)

- `DatasetService.create_record`/`create_source` + `DatasetAdminRepository.duplicate()` (dedup).
- `DatasetVersioningService.create_build`/`validate_build`/`run_build` (split/leakage/confirmation gate) — the handoff bridge is an orchestration layer on top, not a reimplementation.
- `core_model.corpus.manifest.manifest_checksum`/`scan_for_sensitive_content`.
- `core_model.corpus.unicode_normalization`/`tamil_normalization`.
- `core_model.document_workspace.cleanup_suggestions`/`repeated_elements` (shape + repetition-detection pattern for new detectors).
- `core_model.tool_gateway.calculator` (for `basic_math_reasoning` verification).
- `document_tamil_quality_issues` reviewed rows (for `spelling_correction` generation).
- Admin Assistant engine (`propose()`, three parity-tested registries).
- `DocumentsPage.jsx`/`DocumentWizardPage.jsx`.

## 2. Exact missing behavior (see audit for full detail)

1. Handoff idempotency/tracking table + `DocumentSftDatasetHandoffService`.
2. 6 new generators: `fact_answer`, `instruction_following`, `Tamil_to_English`, `English_to_Tamil`, `Tanglish_input_to_Tamil`, `summarization`, plus `spelling_correction` from reviewed Tamil issues (7 total). `contextual_meaning`, `multiple_meanings`, `clarification_request`, `computer_basics`, `safety_response` deferred (no non-fabricated data source); `grammar_correction` partial (subset of Tamil-issue types); `basic_math_reasoning` included via calculator verification.
3. 9 cleanup detectors.
4. Tamil correction-rule registry (new table) + 5-tier risk classification.
5. Content-type classification (new table) + conservative table extraction via `fitz`'s table finder.
6. Prompt-injection + PII detectors (new table for findings).
7. Admin Assistant tools/proposals, frontend tabs.

## 3. Database impact — migration 044 (forward-only, additive)

New tables:
- `document_sft_dataset_handoffs` — one row per export→dataset-source handoff attempt; `export_public_id` UNIQUE, `export_checksum_sha256`, `dataset_source_public_id`, `dataset_version_public_id` (nullable until built), counts (`imported_count`, `skipped_count`, `duplicate_count`, `rights_blocked_count`, `security_blocked_count`), `status` (`imported`/`version_proposed`/`version_built`/`blocked`), `created_by`, `confirmed_by`, timestamps.
- `document_tamil_correction_rules` — `incorrect_form`, `approved_correction`, `issue_category`, `evidence`, `confidence_band`, `meaning_change_risk`, `automatic_proposal_allowed`, `human_review_required`, `status` (`draft`/`needs_review`/`approved`/`active`), `rule_version`, append-only review trail via a companion `document_tamil_correction_rule_reviews` table.
- `document_content_classifications` — one row per page: `content_type` (`text_only`/`image_with_caption`/`image_with_explanation`/`diagram_with_labels`/`table`/`mixed_content`/`image_without_usable_text`), `caption_text`, `nearby_text`, `table_data_json`, `review_status`.
- `document_security_findings` — `finding_type` (`prompt_injection`/`pii_email`/`pii_phone`/`pii_address`/`pii_government_id`/`pii_bank`/`pii_secret`/`pii_path`), `matched_text` (redacted at read-time, not storage-time, so review can see it), `confidence_band`, `reason_code`, `action` (`allow`/`mask_for_preview`/`exclude_from_sft`/`require_review`/`block_export`), `review_status`.

All new tables get standard indexes; append-only triggers where the task requires an audit trail (handoffs, correction-rule reviews). No column is added to migration 043's tables — `document_sft_candidates.generation_method` already accommodates new generator names (`fact_answer_v1`, `instruction_following_v1`, etc.) without a schema change.

## 4. Service changes

- `backend/services/document_sft_dataset_handoff_service.py` — `preview()`, `ingest()` (idempotent), `propose_dataset_version()` (thin wrapper over `DatasetVersioningService.create_build`), `preview_split()` (wraps `validate_build`), `confirm_build()` (wraps `run_build`).
- Extend `backend/services/document_sft_candidate_service.py` with 7 new generator functions, each with an explicit eligibility-check function and `generator_name`/`generator_version` recorded via `generation_method`.
- `backend/services/document_tamil_correction_registry_service.py` — rule CRUD + lifecycle transitions (Admin Assistant may propose `draft`/`needs_review` only, never `approved`/`active`).
- `backend/services/document_content_classification_service.py` — per-page classification, conservative table extraction.
- `backend/services/document_security_review_service.py` — prompt-injection + PII scanning.
- Extend `core_model/document_workspace/cleanup_suggestions.py` with the 9 new detector functions.

## 5. API changes

New routes under `/api/admin/documents/{public_id}/...`: `sft-dataset-handoff/preview`, `/ingest`, `/propose-version`, `/preview-split/{build_public_id}`, `/confirm-build/{build_public_id}`; `sft-candidates/generate-selected` (generator selection); `cleanup-detectors/scan`; `tamil-correction-rules` (list/propose); `content-classification`; `security-review`. All Admin-only, CSRF on writes, paginated lists.

## 6. Frontend changes

New tabs on `DocumentsPage.jsx`: **Dataset Handoff**, **Cleanup Detectors** (extends existing cleanup UI), **Media & Tables**, **Security Review**; SFT Candidates tab extended with generator selection. Wizard step 9/10 updated to reflect real handoff status.

## 7. Admin Assistant changes

8 read-only tools + 8 governed proposals per the task list, all through the existing engine, parity-tested.

## 8. Security/privacy controls

Export blocked on secret/path (existing) **and** on any `document_security_findings` row with `action='block_export'`. PII findings require review before candidate approval eligibility. Prompt-injection-flagged text is excluded from automatic generation and never alters Admin Assistant behavior (there is no code path where document text reaches an LLM/instruction-following context in this repo — deterministic-generator-only, so this is a structural guarantee, verified and tested).

## 9. Performance controls

New `Settings` fields: `document_sft_handoff_max_records`, `document_content_classification_max_pages_per_job`, `document_security_scan_max_findings_per_page`. Reuse existing job/pagination patterns.

## 10. Test strategy

Focused backend tests per new service (positive+negative per generator, per detector, per correction-risk tier, per content class, per security finding type), frontend tests per new tab, one extended Playwright e2e test covering the full bridge.

## 11. Canonical regression strategy

Run the full backend/frontend/browser targeted suite first (as before). Then attempt the official `ProductionRegressionService` 70-batch manifest once; record run_id/manifest_version/checksum/counts. If the environment's demonstrated single-long-process fragility recurs, disclose explicitly and use `_WITH_LIMITATIONS`, per the task's own §32 instruction — never fabricate a result.

## 12. Out-of-scope (explicitly, per task §35)

Vision model, image embeddings/generation, voice, video, external MCP, payments, live web ingestion, automatic training/release/activation/RAG promotion, `contextual_meaning`/`multiple_meanings`/`clarification_request`/`computer_basics`/`safety_response` generators (no non-fabricated data source — disclosed as deferred, not implemented).
