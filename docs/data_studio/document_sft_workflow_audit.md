# Document Processing & SFT Workflow — Audit

Scope: audit the existing repository (branch `master`, HEAD `e24849f`, schema version 42) for
everything needed to support one guided Admin path:

`Upload → Extract → Review Pages → Cleanup → Tamil Quality → Create Chunks → Generate SFT →
Review Candidates → Export JSONL → Training Readiness`

Method: read-only investigation of `backend/`, `core_model/`, `apps/admin-dashboard/`, and
`backend/database/schema.py`. No files were modified while producing this document. This audit
must be read before any implementation begins (see the companion completion plan).

Status values used below: `fully_available`, `partially_available`, `backend_only`,
`frontend_only`, `missing`, `duplicate_risk`.

## 1. Prior related phases (context, not re-audited in depth)

- **Phase 4** (`docs/data_studio/phase4_pdf_research_workspace.md`) built the PDF upload /
  extraction / OCR / page-review / cleanup pipeline (`document_sources`, `document_pages`,
  `document_page_revisions`, `document_processing_jobs/_events`, `document_candidates`).
- **Phase 5** (`docs/data_studio/phase5_semantic_chunk_structured_record_studio.md`, migration
  026) built `semantic_chunks` and a separate `structured_record_candidates` concept (Chunk
  Studio's own dataset-record builder — a **different** thing from the SFT candidates this task
  requires; see §5).
- **Phase 6/7** built dataset versioning, quality/duplicate/conflict handling, and RAG/training
  integration (`dataset_versioning.py`, `corpus_export_service.py`).

This task is strictly additive on top of all of the above. Nothing here should be reopened.

## 2. PDF upload, extraction, OCR, page review, cleanup (backend)

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| PDF upload endpoint | fully_available | `backend/api/routes/documents.py:66-86` → `DocumentService.upload` | Admin-only, CSRF-protected, validates `ExtractionStrategy`/`LanguageCode` |
| Page count / file metadata | fully_available | `document_sources` table (checksum, page_count, status); `GET /{public_id}` | |
| Embedded text extraction | fully_available | `document_pages.extraction_method IN ('embedded',...)`, implemented in `document_service.py` | Own inline implementation (not `core_model/corpus/text_extraction.py`) — parallel, not duplicate, since it operates on a different table |
| OCR fallback | fully_available | `extraction_method='ocr'`; `ProcessRequest.strategy` includes `OCR`/`HYBRID` | |
| Page image preview | fully_available | `documents.py:296-299 GET /pages/{n}/image` → `workspace_service.render_page_image` | |
| Side-by-side editor backend support | fully_available | Page GET returns raw+cleaned text; `PATCH /pages/{n}` → `revision_service.save_draft`; `raw_text` column never overwritten | |
| Revision history | fully_available | `document_page_revisions` table, immutable via `document_revisions_immutable_update/delete` triggers; `GET/POST .../revisions[/restore]` | |
| Mark reviewed / approve / exclude / reopen | fully_available | `documents.py:325-374` → `DocumentPageReviewService` | |
| Single-page OCR rerun | fully_available | `documents.py:390-400 request-ocr-rerun`, `OcrRerunRequest` | |
| Header/footer/page-number detection | fully_available | `core_model/document_workspace/cleanup_suggestions.py`, `repeated_elements.py` + `document_repeated_elements` table | |
| URL / email / phone / watermark / logo-text detection | partially_available | Present in `cleanup_suggestions.py` detector set, but exact coverage of all 14 requested detector categories (incl. `copyright_notice`, `navigation_text`, `broken_line_wrap`, `hyphenation_break`, `duplicate_paragraph`, `noise_line`) not individually confirmed — must be verified line-by-line before extending | Do not re-detect categories that already exist |
| Bulk cleanup workflow (detect→preview→apply→confirm→audit) | fully_available | `documents.py:426-476` cleanup-suggestions / apply-cleanup / repeated-elements detect/list/review (accept/reject/apply_selected/apply_all) | |
| Job/event/crash-recovery, resumability | fully_available | `document_processing_jobs` (status incl. `paused`, `queued`, per-page progress) + immutable `document_processing_events` | Solid foundation for incremental 30-page processing — reuse, do not build a second job system |
| PDF size / page / batch limits | partially_available | `ProcessRequest.pages` capped at 300 items (`backend/models/documents.py:32`); no confirmed max-PDF-size or max-OCR-pages-per-batch constant | Needs an explicit `capabilities()`-style limit check before wizard work begins |

## 3. Tamil quality

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Tamil Unicode integrity detection | backend_only, not wired to documents | `core_model/corpus/unicode_normalization.py` (`assess_unicode_integrity`, `tamil_combining_marks_preserved`, mojibake detection) | Exists and is reusable, but `document_service.py` / `document_workspace_service.py` do not import it — this is the main Tamil gap |
| Tamil OCR-substitution correction | partially_available | `core_model/corpus/tamil_normalization.py: apply_tamil_ocr_substitutions` | Mechanical, low-risk correction — reusable |
| Tamil spelling / orthography suggestion engine | missing | No general spelling-suggestion service found beyond the fixed OCR-substitution table | Must stay conservative: mechanical fixes auto-proposed, spelling suggestions require preview, anything meaning-changing requires mandatory human review, per task policy |
| Ambiguous-correction human-review gating | missing (for documents) | No document-specific gating found; the *pattern* (low-risk vs preview vs mandatory-review) does not yet exist wired to page review | |

## 4. Semantic chunks

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Chunk service/schema | fully_available | `core_model/semantic_chunk/*`, `backend/services/semantic_chunk_service.py` (~1000 lines), tables `semantic_chunks/_revisions/_relations/_reviews/_events` | Retains document ID, page range (via `document_page_id`), checksum (`content_hash`), `generation_method` — matches requirement |
| Chunk actions (edit/split/merge/exclude/approve/open source page) | fully_available | `ChunkStudioPage.jsx` (manual/split/merge/reorder/coverage/quality/duplicate) + backend service | Reuse as-is. **Do not create a second chunk table.** |

## 5. SFT candidate generation — the central gap

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| `document_candidates` table (Phase 4) | duplicate_risk if reused directly | `backend/database/schema.py:509-535` | `candidate_type` CHECK only allows `pretrain/instruction/chat/translation/tanglish_pair/safety/preference` (the generic `DatasetRecordType`, `backend/models/domain.py:44-51`) — **not** the 17-value SFT task taxonomy. Table also lacks `context`, `task`, `domain`, `difficulty`, `rights_status`, `quality_status`, `generation_method`, and separate `input_language`/`output_language` columns. Extending its CHECK constraint requires an SQLite table rebuild migration either way. |
| `structured_record_candidates` (Phase 5, Chunk Studio) | duplicate_risk if reused directly | `ChunkStudioPage.jsx` "structured record candidate" builder, `recordType` e.g. `plain_text` | A **different concept** (generic structured dataset records), not the instruction/context/response SFT schema this task needs. Must not be conflated. |
| `DocumentSftCandidateGenerationService` | missing | grep confirms no `SftCandidate` symbol anywhere in `backend/` or `core_model/` | Must be created |
| SFT candidate schema (instruction/context/response/input_language/output_language/task/domain/difficulty/source_id/source_document_id/source_page_start/source_page_end/rights_status/quality_status/generation_method) | missing | — | Needs a new, purpose-built table — seeing the two existing candidate tables are schema-incompatible and semantically distinct, a new table (e.g. `document_sft_candidates`) is the correct additive choice, not a rebuild of either existing table |
| Lineage enforcement (reviewed/approved pages, cleaned text, rights-eligible, non-quarantined, approved chunks, non-duplicate) | missing | — | Must be built into the new generation service; can reuse existing page-review status columns, chunk approval status, and `data_sources.source_type` (which already includes `document_derived`, `schema.py:5545-5550`) for rights linkage |
| Duplicate detection | partially_available (pattern exists) | `document_candidates.content_hash` + `duplicate_record_public_id` pattern (Phase 4); `ChunkStudioPage` duplicate chunk action | Same hashing pattern should be reused for the new table |

## 6. SFT candidate review

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Candidate review UI/workflow | missing | `DocumentsPage.jsx` has no SFT-candidate tab; no equivalent of the Phase-4 `document_candidates` review endpoints for a task/domain/instruction-response schema | Reuse the *pattern* of `documents.py`'s candidates CRUD/select/reject/import endpoints, not the table |
| Bulk approval limits | missing | — | Must be implemented per task requirement (low-risk, exact, previewed only) |

## 7. JSONL export, manifest, checksum

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Generic JSONL/manifest/checksum helpers | fully_available | `core_model/corpus/manifest.py` (`build_jsonl_record`, `serialize_jsonl_line`, `shard_checksum`, `manifest_checksum`, `missing_required_fields`) | **Reuse these helpers directly** for the new SFT export rather than reimplementing JSONL/checksum logic |
| Generic corpus export service | fully_available | `backend/services/corpus_export_service.py` (`create_export`, `generate_manifest`, `get_manifest`, `compare`) | Reference implementation for how an export+manifest service should be shaped; the new document-SFT export service should follow this shape |
| Document-SFT-specific export path | missing | No export path found for `document_candidates` or a future SFT candidates table | Must be created; must export **approved-only**, rights-eligible records |

## 8. Dataset versioning / training readiness handoff

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Dataset versioning service | fully_available | `backend/services/dataset_versioning.py`: `create_version`/`create_build`, `_select_records`, `_split_config`, `_split_groups`, `_leakage`, `_manifest` | Selects from a generic `dataset_records`/`selectable_records` pool (via `CorpusRepository`), not directly from `document_candidates` |
| Default train/validation/test split | fully_available, matches spec exactly | `backend/core/config.py:217-224`: `dataset_default_train_percent=90`, `_validation_percent=5`, `_test_percent=5` | No change needed |
| Duplicate/leakage check | fully_available | `dataset_versioning.py: _leakage`, `content_hash` dedup in `_select_records` | Reusable as-is |
| Rights/provenance linkage for document-derived data | fully_available (schema level) | `data_sources.source_type` CHECK includes `'document_derived'` (`schema.py:5545-5550`); `source_rights.rights_status` CHECK (`schema.py:5587`) | Confirms documents are already a first-class rights-tracked source type — reuse, don't add a parallel rights concept |
| Handoff from approved SFT candidates into a dataset version | missing | `_select_records` reads from the generic corpus/dataset record pool; approved document-SFT candidates are not in that pool | Additive plan: after JSONL export, approved candidates get ingested as generic dataset records (existing ingestion pathway) tagged with a document-derived source, so they flow through the **unmodified** `DatasetVersioningService` — no new split/leakage logic needed |
| Instruction-tuning / training pipeline | fully_available (pre-existing, out of scope to modify) | `backend/services/instruction_tuning_service.py`, `backend/instruction_tuning_worker.py` | Confirms "do not start training" boundary already has a real system on the other side of it |

## 9. Admin Assistant (backend)

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| Dashboard/navigation registry | fully_available, reuse directly | `core_model/admin_assistant/dashboard_registry.py` (768 lines) — already has `page_id="documents"` (line 272) and `page_id="chunk_studio"` (line 290) entries with bilingual help text | New nav targets (Tamil Quality tab, SFT Candidates tab, Export tab) should be added as entries/`related_page_ids` here, not a new registry |
| Governed action registry + propose/preview/confirm/execute engine | fully_available (pattern), missing (document actions) | `core_model/admin_assistant/action_registry.py` (76 existing `action_type` entries, zero document/chunk/SFT ones); shared engine at `backend/services/admin_assistant_service.py:2383 def propose(...)` | New document/SFT actions are just new `ActionDefinition` entries — the engine itself needs no changes |
| Read-only document tools (`get_document_*`, `list_critical_document_pages`, etc.) | missing | `backend/services/admin_assistant_tools.py` has ~70 `_tool_*` functions covering datasets/samples/RAG-sandbox/knowledge-gap/trusted-web/tool-gateway — **none** for documents | All 8 required tools (§16 of the task) must be added |
| Governed document proposals (`propose_document_*`, etc.) | missing | Same file/registry as above | All 9 required proposals (§16) must be added |
| Tamil natural-language question handling for documents | missing | `core_model/admin_assistant/intent.py` has no document/Tamil-quality intent matching yet; generic Tamil localization exists (`core_model/admin_assistant/localization/`) but isn't hooked to documents | Must wire document intents into existing localization infra, not build a new one |
| Authority boundary (AA cannot approve/start training) | fully_available, inherited for free | Enforced structurally by the propose/confirm pattern itself (execution always requires explicit Admin confirmation) and documented explicitly elsewhere in `dashboard_registry.py` (e.g. `incremental_training` entry) | New document actions inherit this automatically by using the existing `propose()` engine — no extra boundary code needed |

## 10. Admin Dashboard frontend

| Feature | Status | Evidence | Notes |
|---|---|---|---|
| `DocumentsPage.jsx` | partially_available | 298 lines: Overview tab, side-by-side page review (image + editable text), cleanup suggestions UI, repeated-elements review UI, revisions, review events | Missing: Tamil-quality tab, critical-page filter queue, SFT-candidate tab, export/JSONL tab, training-readiness link, wizard/stepper shell |
| Backend route coverage for `DocumentsPage.jsx` | fully_available | `backend/api/routes/documents.py` (485 lines, ~35 endpoints) | Already far more complete than the current frontend surfaces — most new frontend work is "expose an existing endpoint," not "build a new endpoint" |
| Wizard/stepper component | missing | No `wizard`/`stepper` component found anywhere in `apps/admin-dashboard/src/` except an unrelated hit in `CoreModelPage.jsx` | Must be built new (§4 of the task) |
| `ChunkStudioPage.jsx` | fully_available (chunks), duplicate_risk (candidate builder) | 559 lines: chunk CRUD + a separate structured-record-candidate builder | Reuse chunk CRUD as the SFT generation input; do not reuse or extend its candidate builder for SFT candidates |
| `api.js` document/chunk functions | fully_available (documents+chunks), missing (SFT/export) | ~30 `document*` functions, ~5 `*Chunk*` functions | No `sft*`, `*Jsonl*`, or document-scoped `*TrainingReadiness*` functions exist yet |
| Other data-studio pages (`DataOverviewPage`, `DatasetVerificationPage`, `KnowledgeGapsPage`, `TrustedWebPage`, `DeterministicToolsPage`) | fully_available, unrelated | Confirmed as navigation-pattern references only, not reuse targets for this task | |

## 11. Security / privacy posture (baseline, to be tested against in §18 of the task)

- PDF content is already treated as untrusted input at the extraction layer (no code execution
  path found in `document_service.py`).
- No external URL fetching found in the document pipeline (Phase 20's `safe_web_fetcher.py` is a
  separate, already-hardened subsystem for a different feature — not reused here, not touched here).
- No existing secret-redaction pass specific to document text was found; the redaction pattern
  used by `ProductionRegressionService` (`[REDACTED]` pattern, confirmed in Phase-20-era tests)
  is a reusable reference implementation, not currently wired to documents.

## 12. Summary: missing vs partial vs reuse

**Missing (must be built new, additively):**
- `document_sft_candidates` table + `DocumentSftCandidateGenerationService`
- SFT candidate review workflow (approve/reject/edit/needs-correction, bulk-approval limits, lineage blocking)
- Document-SFT JSONL export service + manifest (reusing `core_model/corpus/manifest.py` helpers)
- Tamil quality detection wired into the document/page-review path (reusing existing `core_model/corpus/unicode_normalization.py` + `tamil_normalization.py`)
- Tamil spelling/orthography suggestion + ambiguous-correction human-review gating
- Critical-page filter queue (frontend + backend query)
- Document Processing Wizard (10-step stepper UI)
- 8 Admin Assistant read-only document tools + 9 governed document proposals
- Frontend: Tamil-quality tab, SFT-candidate tab, export/JSONL tab, training-readiness link on `DocumentsPage.jsx` (or a wizard shell wrapping it)
- Handoff step: ingest approved SFT candidates into the generic dataset-record pool so `DatasetVersioningService` picks them up unmodified

**Partially available (verify exact coverage, extend, do not rebuild):**
- Cleanup detector coverage vs the 14 requested categories
- PDF size / OCR-batch / cleanup-proposal limits (need explicit caps)
- Duplicate detection pattern (reuse `content_hash` approach)

**Fully available (reuse as-is, do not touch/duplicate):**
- Upload/extraction/OCR/page-review/revision-history/approve-exclude/OCR-rerun backend+frontend
- Bulk cleanup detect→preview→apply→confirm→audit flow
- Semantic chunking (service, schema, and Chunk Studio UI/actions)
- Job/event/crash-recovery system for resumable processing
- Dashboard registry, action-registry propose/confirm engine, authority-boundary enforcement
- Dataset versioning (split/leakage/manifest), 90/5/5 default split, rights/provenance schema
- Instruction-tuning/training pipeline (out of scope — never triggered by this task)

No duplicate subsystem is proposed anywhere in this audit. The completion plan
(`docs/data_studio/document_sft_workflow_completion_plan.md`) turns this into concrete migration,
backend, frontend, Admin Assistant, security, and test work.
