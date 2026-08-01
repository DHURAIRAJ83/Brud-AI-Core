# Document Processing & SFT Workflow — Completion Plan

Based on `docs/data_studio/document_sft_workflow_audit.md`. Strictly additive: new migration
(043), new tables, new services, new routes, new frontend tabs/pages, new Admin Assistant tools —
nothing existing is renamed, dropped, or altered in a breaking way. Baseline: schema version 42,
branch `master`, HEAD `e24849f`.

## 1. Existing components to reuse (no changes)

- Upload/extraction/OCR/page-review/revision-history/approve-exclude/OCR-rerun:
  `backend/api/routes/documents.py`, `document_service.py`, `document_page_review_service.py`,
  `document_pages`, `document_page_revisions`.
- Cleanup: `core_model/document_workspace/cleanup_suggestions.py`,
  `core_model/document_workspace/repeated_elements.py`, cleanup-suggestions/apply-cleanup/
  repeated-elements endpoints.
- Semantic chunks: `core_model/semantic_chunk/*`, `semantic_chunk_service.py`, `semantic_chunks`
  table family, `ChunkStudioPage.jsx` chunk CRUD.
- Job/event/crash-recovery: `document_processing_jobs`, `document_processing_events`.
- Tamil Unicode/OCR helpers: `core_model/corpus/unicode_normalization.py`,
  `core_model/corpus/tamil_normalization.py`.
- JSONL/manifest/checksum: `core_model/corpus/manifest.py` helpers (`build_jsonl_record`,
  `serialize_jsonl_line`, `shard_checksum`, `manifest_checksum`).
- Dataset versioning: `backend/services/dataset_versioning.py` (split/leakage/manifest, 90/5/5
  defaults) — **unmodified**.
- Admin Assistant engine: `core_model/admin_assistant/dashboard_registry.py`,
  `core_model/admin_assistant/action_registry.py`, `admin_assistant_service.py: propose()`.
- Rights/provenance: `data_sources.source_type = 'document_derived'`, `source_rights`.

## 2. Missing components to build

1. **Migration 043** — new tables (additive only):
   - `document_sft_candidates` — the SFT candidate record itself.
   - `document_sft_candidate_reviews` — append-only review/audit trail (mirrors the immutable
     pattern used by `document_processing_events` / `document_page_revisions`).
   - `document_sft_exports` — export/manifest/checksum records (mirrors `dataset_versions`/
     `corpus_export_service` shape).
2. **`DocumentSftCandidateGenerationService`** (`backend/services/document_sft_candidate_service.py`)
   — generates candidates only from reviewed/approved pages + approved chunks; enforces rights
   eligibility, quarantine exclusion, and dedup via `content_hash`.
3. **Tamil quality wiring** — a thin service (`document_tamil_quality_service.py`) that calls the
   *existing* `unicode_normalization.py`/`tamil_normalization.py` functions per-page and stores
   results; no new Unicode-detection logic is written from scratch.
4. **Document-SFT JSONL export service** — reuses `core_model/corpus/manifest.py`; exports
   approved-only candidates.
5. **Corpus-record handoff** — after export, approved candidates are ingested as generic
   `dataset_records` (existing ingestion path) tagged `source_type='document_derived'`, so
   `DatasetVersioningService` picks them up with zero changes to that service.
6. **8 Admin Assistant read-only tools + 9 governed proposals** (§16 of the task) added to
   `admin_assistant_tools.py` / `action_registry.py`.
7. **Frontend**: a `DocumentWizardPage.jsx` stepper shell that links to (rather than rebuilds)
   `DocumentsPage.jsx` tabs, plus new tabs on `DocumentsPage.jsx`: Tamil Quality, SFT Candidates,
   Export, and a Training Readiness link. Critical-page filter added to the existing page list.

## 3. Duplicate-prevention decisions (explicit)

- SFT candidates get a **new** table (`document_sft_candidates`), never reuse or extend
  `document_candidates` (Phase 4, incompatible schema/CHECK constraint) or
  `structured_record_candidates` (Phase 5, different concept — generic structured records, not
  instruction/response SFT pairs). This was flagged `duplicate_risk` in the audit if conflated.
- Chunks: **no second chunk table**. SFT generation reads `semantic_chunks` as input only.
- Cleanup detectors: only add the categories confirmed missing in the audit (`web_url`,
  `email_address`, `phone_number`, `logo_text`, `watermark_text`, `copyright_notice`,
  `navigation_text`, `duplicate_paragraph`, `noise_line`) as new functions in
  `cleanup_suggestions.py`. Do not re-implement `repeated_header`/`repeated_footer`/`page_number`
  (already in `repeated_elements.py`) or `hyphenation_break` (already `suggest_broken_word_joins`).
  `broken_line_wrap` maps to the existing `suggest_repeated_whitespace`.
- Tamil detection: call existing `unicode_normalization.py`/`tamil_normalization.py` functions;
  do not write a second Unicode-integrity checker.
- JSONL/manifest/checksum: call `core_model/corpus/manifest.py` helpers; do not hand-roll JSON
  serialization or a second checksum algorithm.
- Dataset split/leakage/training-readiness: reuse `DatasetVersioningService` unmodified via the
  corpus-record handoff (§2.5) rather than building a parallel split engine.
- Rights status: read from `data_sources`/`source_rights` via the document's existing
  `document_derived` source-type linkage; do not add a second rights table.

## 4. Database impact

Migration 043 (`_apply_v43`, `PHASE43_SCHEMA`), `SCHEMA_VERSION` 42→43, additive only:

```sql
CREATE TABLE IF NOT EXISTS document_sft_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    document_source_id INTEGER NOT NULL,
    source_chunk_id INTEGER,
    source_page_start INTEGER NOT NULL CHECK (source_page_start > 0),
    source_page_end INTEGER NOT NULL CHECK (source_page_end >= source_page_start),
    task TEXT NOT NULL CHECK (task IN (
        'definition','fact_answer','explanation','contextual_meaning','multiple_meanings',
        'grammar','spelling_correction','grammar_correction','instruction_following',
        'summarization','clarification_request','Tamil_to_English','English_to_Tamil',
        'Tanglish_input_to_Tamil','basic_math_reasoning','computer_basics','safety_response'
    )),
    domain TEXT NOT NULL DEFAULT 'general',
    difficulty TEXT NOT NULL DEFAULT 'basic' CHECK (difficulty IN ('basic','intermediate','advanced')),
    instruction TEXT NOT NULL,
    context TEXT NOT NULL DEFAULT '',
    response TEXT NOT NULL,
    input_language TEXT NOT NULL,
    output_language TEXT NOT NULL,
    rights_status TEXT NOT NULL CHECK (rights_status IN ('verified','pending','blocked')),
    quality_status TEXT NOT NULL DEFAULT 'draft' CHECK (quality_status IN (
        'draft','pending_review','needs_correction','approved','rejected'
    )),
    generation_method TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    duplicate_of_public_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_source_id) REFERENCES document_sources(id) ON DELETE CASCADE,
    FOREIGN KEY (source_chunk_id) REFERENCES semantic_chunks(id) ON DELETE SET NULL
);
CREATE TABLE IF NOT EXISTS document_sft_candidate_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    candidate_id INTEGER NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('approve','reject','edit','needs_correction')),
    actor_reference TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (candidate_id) REFERENCES document_sft_candidates(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS document_sft_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    public_id TEXT NOT NULL UNIQUE,
    record_count INTEGER NOT NULL,
    excluded_count INTEGER NOT NULL,
    task_distribution_json TEXT NOT NULL DEFAULT '{}',
    language_distribution_json TEXT NOT NULL DEFAULT '{}',
    domain_distribution_json TEXT NOT NULL DEFAULT '{}',
    source_document_ids_json TEXT NOT NULL DEFAULT '[]',
    rights_summary_json TEXT NOT NULL DEFAULT '{}',
    quality_summary_json TEXT NOT NULL DEFAULT '{}',
    checksum_sha256 TEXT NOT NULL,
    export_path TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_document_sft_candidates_status
    ON document_sft_candidates(document_source_id, quality_status);
CREATE INDEX IF NOT EXISTS ix_document_sft_candidates_hash
    ON document_sft_candidates(content_hash);
CREATE TRIGGER IF NOT EXISTS document_sft_candidate_reviews_immutable_update
    BEFORE UPDATE ON document_sft_candidate_reviews
    BEGIN SELECT RAISE(ABORT, 'document sft candidate reviews are immutable'); END;
CREATE TRIGGER IF NOT EXISTS document_sft_candidate_reviews_immutable_delete
    BEFORE DELETE ON document_sft_candidate_reviews
    BEGIN SELECT RAISE(ABORT, 'document sft candidate reviews are immutable'); END;
```

`export_path` stores a path relative to `settings.allowed_data_dir` only (never an absolute
filesystem path) — enforced at write time, matching §18's "no private source path" rule.

## 5. Backend work

- `backend/database/migrations.py`: add `PHASE43_SCHEMA`, `MIGRATION_043_NAME`, `_apply_v43`,
  register in the upgrade chain.
- `backend/database/schema.py`: bump `SCHEMA_VERSION = 43`.
- `backend/database/repositories/documents.py` (or a new `document_sft.py` repository): CRUD for
  the 3 new tables.
- `backend/models/documents.py`: Pydantic models for candidate/review/export requests+responses.
- `backend/services/document_sft_candidate_service.py`: generation (enforcing lineage/rights/
  dedup/quarantine), review (approve/reject/edit/needs_correction with bulk-approval limited to
  low-risk exact-previewed candidates), lineage-block on missing source.
- `backend/services/document_tamil_quality_service.py`: per-page Tamil issue detection calling
  existing corpus helpers; mechanical fixes = low-risk auto-proposal, spelling = preview-required,
  ambiguous = mandatory human review (task/reason-code/confidence band on every issue).
- `backend/services/document_sft_export_service.py`: JSONL export (approved-only) + manifest,
  using `core_model/corpus/manifest.py`.
- Extend `core_model/document_workspace/cleanup_suggestions.py` with the 9 missing detector
  categories (see §3), each returning pattern/affected pages/occurrence count/confidence
  band/risk level/before-after sample, matching the existing suggestion shape.
- `backend/api/routes/documents.py`: new endpoints — Tamil quality list/accept/reject/edit,
  SFT candidate generate/list/approve/reject/edit, export create/get, training-readiness link.
- Limits (§19): explicit `max_pdf_size_bytes`, `max_pages_per_operation`,
  `max_ocr_pages_per_batch`, `max_cleanup_proposals_per_batch`, `max_corrections_per_batch`,
  `max_chunks_per_batch`, `max_sft_candidates_per_job` as `Settings` fields with safe defaults,
  enforced server-side with pagination/bounded previews everywhere.

## 6. Frontend work

- New `DocumentWizardPage.jsx`: 10-step stepper (status/pages-affected/blocking-issues/warnings/
  recommended-next-action per step; statuses `not_started/in_progress/needs_review/blocked/
  ready/completed`). Each step **links into** the relevant existing/new tab on `DocumentsPage.jsx`
  rather than re-implementing it.
- `DocumentsPage.jsx` additions: Tamil Quality tab, SFT Candidates tab (with review controls),
  Export tab (JSONL + manifest download, distributions), critical-page filter chips (All/Critical/
  OCR issues/Tamil issues/Unreviewed/Reviewed/Approved/Excluded), "Open Training Readiness" link
  to the existing readiness page.
- `api.js`: new functions for Tamil quality, SFT candidates, export — following existing
  `document*` naming conventions.
- `Sidebar.jsx`/`App.jsx`: one new nav entry for the wizard, reusing existing patterns.
- Mobile/accessibility: reuse existing responsive patterns already present in `DocumentsPage.jsx`.

## 7. Admin Assistant work

- `dashboard_registry.py`: extend the existing `documents`/`chunk_studio` entries'
  `related_page_ids` and add entries for the new tabs/wizard — no fabricated routes.
- `admin_assistant_tools.py`: add the 8 required read-only tools (`analyze_document_readiness`,
  `get_document_issue_summary`, `list_critical_document_pages`, `get_document_cleanup_summary`,
  `get_document_tamil_quality_summary`, `get_document_chunk_summary`,
  `get_document_sft_candidate_summary`, `get_document_training_readiness`), each backed by real
  repository queries.
- `action_registry.py`: add the 9 governed proposals (`propose_document_page_correction`,
  `propose_document_ocr_rerun`, `propose_bulk_cleanup`, `propose_tamil_corrections`,
  `propose_chunk_generation`, `propose_sft_candidate_generation`,
  `propose_candidate_status_change`, `propose_sft_export`, `propose_dataset_version_handoff`),
  all routed through the existing `propose()` engine (propose→preview→confirm→stale-check→
  execute→verify→audit) — no new execution engine.
- Tamil NL question handling: add document/Tamil-quality intent entries to
  `core_model/admin_assistant/intent.py` using existing localization infra.

## 8. Security / privacy rules

- PDF text is untrusted: any instruction-like text extracted from a page must never be treated as
  a system/Admin-Assistant instruction (test explicitly, per §18).
- No code execution, no external URL fetching, from any part of this workflow.
- Secret/PII patterns (email, phone, address, private IDs) inside extracted text must not leak
  into Admin Assistant tool responses verbatim — reuse the `[REDACTED]` pattern precedent from
  `ProductionRegressionService`.
- `export_path`/any document-derived file reference exposed via API or JSONL must be relative,
  never an absolute filesystem path.
- No automatic training/dataset-approval side effects anywhere in this workflow — every mutating
  action stops at "proposed"/"exported"/"handed off," never auto-executes training.

## 9. Tamil correction policy (task §9, restated as implementation rule)

- Mechanical Unicode fix (broken combining marks, misplaced pulli, broken vowel signs, invalid
  Unicode, zero-width corruption) → low-risk, auto-generated proposal, single accept/reject.
- OCR character substitution / spelling correction → preview required before apply.
- Meaning-changing or ambiguous correction → `human_review_required=true`, cannot be bulk-applied.

## 10. SFT generation policy (task §11, restated as implementation rule)

- Generate only from: reviewed/approved pages, cleaned text, rights-eligible sources,
  non-quarantined content, approved chunks, non-duplicate content.
- Not every type from every paragraph — generation is chunk-scoped and type-selective based on
  chunk content signals (a definition-shaped chunk yields `definition`/`fact_answer`, not all 17
  types).
- Current/volatile information is blocked from normal generation by default (reuse the freshness/
  volatility concept already established in Phase 20's `core_model/web_search/freshness.py` as a
  reference pattern for the classification, without depending on that module directly).
- Tanglish input → Tamil output only (never Tanglish → Tanglish).

## 11. Tests (to be run sequentially, per low-resource policy)

- Backend: migration 043 up/down + FK integrity; candidate generation lineage/rights/dedup
  enforcement; review workflow + bulk-approval limits; Tamil detection classification (mechanical
  vs preview vs mandatory-review); export JSONL validity + manifest/checksum; corpus-record
  handoff into `DatasetVersioningService`; Admin Assistant tools/proposals + authority boundary;
  security (prompt injection, PII redaction, no absolute paths, no code exec).
- Frontend: wizard step rendering/status transitions; critical-page filter; Tamil review controls;
  SFT candidate review controls; export tab.
- Regression: existing document/chunk/RAG/dataset/training suites must remain green unchanged.

## 12. Browser verification

Single browser worker, isolated backend+frontend servers, sequential steps per task §21 (30-page
PDF upload through export + Admin Assistant summary + navigation + 390px layout + keyboard nav +
console-error check + no private-path leakage).

## 13. Sequencing given low-resource constraints

Given the CPU-only/6GB-RAM/single-session/sequential-only constraints already in force this
session, implementation proceeds in this order, committing progress to the task list after each
stage: (1) migration 043 + repository, (2) SFT generation + review service, (3) Tamil quality
service, (4) export service + handoff, (5) cleanup detector additions, (6) routes, (7) Admin
Assistant tools/proposals, (8) frontend wizard + tabs, (9) tests, (10) browser verification,
(11) regression + final report. If any stage cannot be completed within the resource/time budget
of this session, it will be disclosed explicitly as a limitation in the final report rather than
silently skipped or fabricated as done.
