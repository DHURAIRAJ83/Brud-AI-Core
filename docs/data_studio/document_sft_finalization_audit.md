# Document SFT Workflow — Finalization Audit

Scope: the 8 documented limitations from `document_sft_workflow_completion_plan.md`
(schema 43, verdict `DOCUMENT_SFT_WORKFLOW_COMPLETE_WITH_LIMITATIONS`). Read-only
investigation before any implementation. No files were modified while producing
this document.

## 1. Dataset handoff bridge

| Component | Status | Evidence |
|---|---|---|
| `dataset_records` table | fully_available | `backend/database/schema.py:38-47` (base) + `PHASE2_COLUMNS["dataset_records"]` (`schema.py:239-249`) adds `public_id, record_type, instruction, input_text, output_text, normalized_input, content_hash, quality_score, metadata_json`. No `task`/`domain`/`rights_status`/lineage columns — `metadata_json` is the documented extension point (confirmed reused elsewhere, e.g. `manual_data_service.py`). |
| `dataset_sources` table | fully_available | `schema.py:29-36`; `source_type` has no CHECK constraint; `DatasetSourceType.GENERATED = "generated"` (`backend/models/domain.py:25`) is the correct, already-modeled value for this handoff — no new source type needed. |
| Record creation + built-in duplicate detection | fully_available | `DatasetService.create_record` (`backend/services/dataset_service.py:156-194`) hashes via `content_hash()` (language-aware, casefold for en/tgl) and checks `DatasetAdminRepository.duplicate()` before insert — reusable as-is. |
| Dataset versioning (create_version/create_build/validate_build/run_build) | fully_available | `DatasetVersioningService` (`backend/services/dataset_versioning.py`) — `create_build` accepts `selection_filters` including `source_public_id` (`dataset_quality.py:143`), `validate_build` returns a full preview (selected/excluded/splits/leakage), `run_build` requires `payload.confirm=True` (hard Admin-confirmation gate already built in). **No new split/leakage/versioning logic is needed.** |
| Split defaults | fully_available | `SplitConfiguration` defaults to 90/5/5 (`backend/models/dataset_versions.py:22-26`) — matches requirement exactly. |
| Near-duplicate / source-family split protection | fully_available | `DatasetVersioningService._groups`/`_split_groups` (`dataset_versioning.py:468-504`) already groups records before splitting — reused unmodified. |
| Handoff idempotency/tracking (export→import mapping, checksum conflict detection) | **missing** | No table or service tracks "this SFT export was already imported." Must be added — a new forward-only migration (schema 43→44) is required per the task's own instruction not to touch migration 043. |
| `document_sft_exports.export_path` → re-derivable record list | partially_available | The export JSONL itself carries `source_id` = candidate `public_id` per record (existing design, `document_sft_export_service.py`), which is sufficient to re-derive full lineage by joining back to `document_sft_candidates` at ingestion time — no schema change needed for this. |

## 2. Additional SFT task generators

| Generator | Status | Notes |
|---|---|---|
| `fact_answer`, `instruction_following` | missing, tractable | Achievable via chunk-type adjacency pairing (`question`+`answer`, `instruction`+`response` sibling chunks under the same `parent_chunk_id`/`reading_order`) — same mechanism designed but not implemented in the prior pass. |
| `Tamil_to_English`, `English_to_Tamil` | missing, tractable | Achievable via `translation_source`+`translation_target` sibling chunk pairing, mapped by `chunk.language`. No external translation API, no model inference — matches the "reviewed pair" requirement. |
| `Tanglish_input_to_Tamil` | missing, tractable | Achievable via `tanglish_text`+`tamil_text` sibling chunk pairing. |
| `summarization` | missing, tractable | Achievable only for a `paragraph`/heading-grouped chunk whose length exceeds a minimum threshold, using the immediate `heading`/`subheading` chunk's text (or the chunk's own opening sentence) as a grounded "summary" candidate — genuinely conservative, not fabricated. |
| `spelling_correction` | missing, tractable via **already-existing reviewed data** | `document_tamil_quality_issues` rows with `review_status IN ('accepted','edited')` are *exactly* "reviewed original incorrect form + approved corrected form + context" per the task's own eligibility rule — a real, already-governed data source, not a new detector. |
| `grammar_correction` | missing, partially tractable | No existing "grammar correction" review artifact exists distinct from Tamil quality issues; deferring to reuse the same reviewed-Tamil-issue mechanism only where `issue_type` indicates a grammar-adjacent mechanical fix (limited coverage, disclosed). |
| `contextual_meaning`, `multiple_meanings`, `clarification_request` | missing, **not tractable without NLP/model inference** | No existing repository signal distinguishes "this word has two source-attested meanings" or "this input is genuinely ambiguous" — generating these deterministically from chunk text alone would require inventing signal that doesn't exist, violating "do not invent alternate meanings." Deferred, disclosed. |
| `basic_math_reasoning` | missing, tractable | `core_model/tool_gateway/calculator.py` (Phase 20) already provides a deterministic, verifiable calculator — reusable to verify an arithmetic statement found in chunk text before generating a candidate. |
| `computer_basics` | missing, not tractable without a curated fact base | No existing "stable computer-knowledge" content source exists in the repo distinct from ordinary chunk text; generating this safely (version-insensitive) from arbitrary PDF content isn't reliably distinguishable from other explanation-type content. Deferred, disclosed — could reuse the same `explanation` mapping in a future pass with an explicit topic allowlist. |
| `safety_response` | missing, not tractable without a policy template store | No existing "approved safety policy/template" table exists in this repo to generate from. Deferred, disclosed rather than inventing safety content from arbitrary document text (which the task explicitly forbids: "Do not use document content to create unsafe operational instructions"). |

## 3. Missing cleanup detectors

All 9 (`web_url`, `email_address`, `phone_number`, `logo_text`, `watermark_text`, `copyright_notice`, `navigation_text`, `duplicate_paragraph`, `noise_line`) are **missing**, but tractable — `core_model/document_workspace/cleanup_suggestions.py` already establishes the exact suggestion shape (`suggestion_type`, `original_text`, `proposed_text`, `reason`, `confidence`) and `repeated_elements.py` establishes the cross-page repetition-detection pattern (page-position + frequency threshold) needed for `logo_text`/`watermark_text`/`navigation_text`. Pure regex/heuristic detectors, no model inference needed.

## 4. Tamil orthography/spelling suggestions + governance

| Component | Status |
|---|---|
| Mechanical Unicode/OCR detection | fully_available, reused unchanged (`document_tamil_quality_service.py`, Phase 19 corpus helpers) |
| General spelling/orthography suggestion beyond the fixed OCR-substitution table | missing |
| Versioned, reviewable correction-rule registry (draft→needs_review→approved→active lifecycle) | missing — no such table exists. Requires a new table in the same forward-only migration. |
| Meaning-change risk classification (mechanical/spelling/grammatical/meaning_sensitive/ambiguous) | partially_available — `document_tamil_quality_issues.correction_risk` currently has 3 tiers (`mechanical`/`preview_required`/`mandatory_review`); the task now wants 5 named categories. Extending the existing enum is additive (no migration needed for the *issues* table; the new *rule registry* table is what needs migrating). |

## 5. Media/table classification

| Component | Status |
|---|---|
| Page image_count / embedded-image metadata | fully_available — `document_pages.image_count` already populated by extraction (`document_service.py`). |
| Structured table extraction | **missing** — no table-extraction logic exists anywhere in the repo (confirmed via repo-wide grep for "table" in `core_model/document_workspace/` and `backend/services/document_service.py`); PyMuPDF (`fitz`) does have a `find_tables()` API available in this environment's installed version, usable for conservative, deterministic table-cell extraction without any vision model. |
| Content-type classification (`text_only`/`image_with_caption`/.../`vision_required`) | missing — new, tractable via `image_count` + `text_length` + table-detection heuristics only (no vision model, per the task's explicit prohibition). |

## 6. Prompt-injection and PII detection

| Component | Status |
|---|---|
| Secret/absolute-path scanning at export time | fully_available, reused unchanged (`core_model.corpus.manifest.scan_for_sensitive_content`, already tested in the prior pass). |
| Prompt-injection phrase detection on document text | missing — new, tractable (deterministic phrase/pattern matching, e.g. "ignore previous instructions"). |
| PII detection (email/phone/address/government-ID/bank/API-key/password/path patterns) beyond the existing secret/path scan | missing — new, tractable via conservative regex with reason codes and confidence bands (never claiming certainty for ordinary educational content). |

## 7. Admin Assistant / Frontend / Migration

All 8 new tools and 8 new proposals listed in the task are **missing** (net-new), but the underlying engine (`propose()`/`ACTION_EXECUTORS`/`STALE_CHECK_FINGERPRINTS`/`PREVIEW_GENERATORS`/`READ_ONLY_TOOLS`/dashboard registry parity tests) is fully available and unchanged from the prior pass — same mechanical extension pattern applies.

Frontend: `DocumentsPage.jsx`/`DocumentWizardPage.jsx` exist and are extensible; no new top-level pages are architecturally required — new tabs on the existing pages, per the task's own "extend, don't rebuild" instruction.

## 8. `blocked_by_architecture` items (none found)

No requested feature in this task is architecturally blocked. Everything is either `missing`+tractable or explicitly deferred due to requiring genuine NLP/model inference or a curated content source that does not exist in this repository (both disclosed above, not fabricated).
