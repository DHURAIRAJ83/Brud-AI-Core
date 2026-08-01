# Phase 3 Plan — Manual Data Studio

Written before implementation, per this phase's Step 1. Documents what
already exists and is being reused, the proposed Phase 3 architecture,
and where the risk is.

## 1. Existing reusable systems (confirmed by direct inspection)

### 1.1 Dataset lifecycle (`backend/services/dataset_service.py`)

- `TRANSITIONS` dict: `draft -> {pending_review, archived}`,
  `pending_review -> {approved, rejected, draft, archived}`,
  `approved -> {archived}`, `rejected -> {draft, archived}`,
  `archived -> {draft}`.
- `dataset_records` table + `DatasetRecordType` enum (`pretrain,
  instruction, chat, translation, tanglish_pair, safety, preference`)
  and `LanguageCode` enum (`ta, en, tgl, mixed, unknown`).
- Duplicate detection is **exact-hash, not semantic**:
  `normalize_text()` (NFC + whitespace collapse + optional casefold)
  feeds `content_hash()` (SHA-256 of a canonical JSON dict of the
  record's logical fields). `create_record()` hard-blocks (raises
  `ConflictError`) on a hash match rather than silently merging or
  warning. This is the exact approach Phase 3 will mirror for its own
  duplicate checks (Step 8) — there is no embedding/semantic engine
  anywhere in this repository to reuse, confirming the task's
  instruction to defer that.
- Quality: `backend/services/dataset_quality.py`'s
  `dataset_quality_assessments` (per-dimension REAL 0-1 scores +
  `readiness_status` CHECK IN `ready/warning/blocked/not_assessed`)
  and `dataset_quality_issues` (`severity` CHECK IN
  `info/warning/error/blocking`). Critically: a `blocking` severity
  issue forces `readiness_status='blocked'` **regardless of the
  average score** — this is the exact "a high overall average must
  not hide a blocking issue" behavior Step 7 requires, and Phase 3's
  quality module will follow the identical shape (dimension scores +
  severity-tiered blocking issues + one recommended status).

### 1.2 Existing "candidate -> real dataset record" bridge (directly reusable precedent)

`backend/services/feedback_dataset_service.py`'s `export_candidate()`
(lines 349-425) is exactly the pattern Step 17 asks for and is reused
verbatim in shape:

1. Reads/validates the staging row (`feedback_dataset_candidates`,
   itself a full staging table with its own `status` lifecycle and
   `feedback_candidate_versions` revision history — direct precedent
   for `manual_data_record_revisions`) in its own transaction.
2. Resolves-or-creates a `dataset_sources` row via a small
   `_find_or_create_feedback_source()` helper (look up an existing row
   by a stable marker before creating — avoids duplicate source rows
   on repeat calls).
3. Calls `self.dataset_service.create_record(RecordCreate(...),
   admin_id)` **directly** — never writes to `dataset_records` itself.
4. In a **separate**, later transaction, stamps the staging row
   `exported` and records the resulting `dataset_record_public_id`.
   The code comments explain why this must be two separate,
   self-committing transactions rather than one nested transaction:
   a nested call against a different repository's connection would
   leave the new row invisible until commit.

Phase 3's "Create Dataset Candidate" action (Step 17) will call
`DatasetService.create_record()` through this exact same bridge,
mapping its own manual `record_type` taxonomy down to the 7
`DatasetRecordType` values (see §4 below), and will stamp the manual
record with the resulting `dataset_record_public_id` the same way
`feedback_dataset_candidates.exported_dataset_record_public_id` does.
**No new dataset-versioning pipeline is built.**

### 1.3 Phase 2 source registry (unchanged, confirmed live)

`backend/services/data_source_service.py` (`SourceRegistryService`,
`SourceRightsService`, `SourceUsagePolicyService`,
`SourceVerificationService`), `backend/database/repositories/data_sources.py`,
`core_model/data_governance/usage_policy.py`
(`evaluate_source_usage(*, source, rights, target_use)`), and
`core_model/data_governance/__init__.py`'s enums are all present and
untouched. Phase 3's new `ManualDataUsageService` will call
`SourceRegistryService`/`SourceRightsService` to load the manual
record's linked source + rights as dicts, then call
`evaluate_source_usage()` directly (the exact same two-line pattern
`SourceUsagePolicyService.evaluate()` already uses internally) —
**the policy function itself is never re-implemented.**

**Structural finding, resolved architecturally (see §3 below):**
`source_record_links.entity_type`'s CHECK constraint
(`backend/database/schema.py` ~5665) does not include a manual-data
entity type, and per rule 1 migration 023 cannot be altered. Phase 3
therefore links manual records to sources via dedicated `source_id`
foreign-key columns on the new tables themselves (see §3), never by
attempting to widen `source_record_links`.

### 1.4 Admin auth, CSRF, audit, repository conventions

- `from backend.api.auth import CsrfDependency, require_admin` — same
  import Phase 3 routes will use.
- Two audit-helper conventions coexist. Phase 3 uses the simpler
  `_audit(connection, event, admin_id, resource_id, **metadata)`
  style from `dataset_service.py`/`feedback_dataset_service.py`
  (writes directly to `audit_logs` with the same 11-column INSERT),
  since Phase 3 sits in the dataset-record family, not the Phase-2
  settings-dependent variant.
- `BaseRepository.transaction(immediate=True)`, `NotFoundError` /
  `ConflictError` / `ValidationError` from
  `backend/database/repositories/base.py`, and the per-repository
  `public_row()` convention (strip internal ids, un-JSON `_json`
  fields) are reused exactly as in every prior phase.

### 1.5 Frontend conventions

- `Sidebar.jsx`'s `dataGroup.children` array, current exact order:
  `Data Overview, Datasets, Sources & Rights, Documents, Corpus
  Builder, Knowledge & RAG, Pretraining Readiness, Evaluation, Data
  Help`. `Manual Data` will be inserted between `Datasets` and
  `Sources & Rights` (a manual record is created before its rights are
  reviewed as a linked source, so it reads naturally right after
  `Datasets`). `Sidebar.test.jsx`'s route-preservation assertions
  derive `DATA_CHILDREN` live from `navTree`, so adding a new child
  does not itself break that test — it will be extended to assert the
  new key is present, not rewritten.
- `api.js`'s `const DS = '/api/admin/data-sources'` module-constant +
  per-endpoint function pattern is mirrored with
  `const MD = '/api/admin/manual-data'`.
- `helpRegistry.js` entry shape (confirmed from the live
  `sources_rights` entry): `{ pageId, activeKey, title: {en, ta},
  purpose: {en, ta}, prerequisites: [{en, ta}], workflowSteps: [{en,
  ta}], commonIssues: [{en, ta}], nextPageIds: [pageId],
  safetyNote: {en, ta} }`.
- `SourcesRightsPage.jsx`'s multi-tab structure (`.dataset-tabs` nav +
  one panel per tab) and its previously-fixed CSS pitfall (bare
  controls placed directly inside a `display:grid` wrapper stretch to
  fill their cell — must wrap in a dedicated flex container like
  `.panel-controls`) are the template for `ManualDataPage.jsx`.

## 2. Manual dataset-record precedent: what Phase 3 must NOT duplicate

`backend/services/dataset_service.py` + `/api/admin/datasets/records`
is **already** a live, admin-facing manual entry system for the 7
`DatasetRecordType` values (pretrain/instruction/chat/translation/
tanglish_pair/safety/preference). Phase 3 does not compete with it —
Manual Data Studio is a **richer staging layer** in front of it,
covering record shapes that system has no columns for at all
(conversations with N ordered turns, dictionary entries with senses,
knowledge notes with fact-dependency/risk classification, Tanglish
normalization pairs with alternate spellings, etc.), which only
becomes a real `dataset_records` row through the explicit "Create
Dataset Candidate" bridge in §1.2. `manual_admin_content` (a RAG
knowledge-source `content_type`) is an unrelated, pre-existing concept
and is not touched.

## 3. Proposed Phase 3 architecture

### 3.1 New tables (migration 024)

`manual_data_records`, `manual_data_record_revisions`,
`manual_data_reviews`, `manual_data_verifications`,
`manual_data_usage_decisions`, `manual_data_events` — following the
task's recommended field lists almost exactly, with these concrete
resolutions:

- **Source linking**: `manual_data_records.source_id` is a required
  FK to `data_sources(id)` — the primary source, set at creation time
  (either an existing human-created source or a freshly created one
  via the same `SourceRegistryService.create()` Phase 2 already
  exposes). `manual_data_verifications.source_id` is an *optional* FK
  used for the "supporting/verified-against source" scenario in Step 5
  (e.g. a human-written note primarily sourced to "Dhurai — General
  Knowledge Notes", separately verified against a specific government
  document). This covers every scenario Step 5 describes without
  needing to widen `source_record_links`'s CHECK constraint.
- **Revisions**: typed columns for every record-type's common fields
  (`title, input_text, output_text, instruction_text, response_text,
  question_text, answer_text, tamil_text, english_text, tanglish_text,
  word, part_of_speech`), plus `meanings_json, examples_json,
  metadata_json` for structured optional data (dictionary senses,
  conversation turns, alternate spellings) — matching the task's
  explicit instruction not to store everything in one opaque blob.
- **Append-only**: `manual_data_events` (the audit-style action log,
  mirroring `source_verification_events`) and
  `manual_data_usage_decisions` (mirroring `source_usage_decisions`)
  get the identical `BEFORE UPDATE/DELETE ... RAISE(ABORT, ...)`
  trigger pair Phase 2 used. `manual_data_record_revisions` is
  logically append-only too (a new revision is added, never edited)
  but is enforced at the service layer (only `INSERT`, never
  `UPDATE`) rather than by trigger, since a future correction to a
  *draft* revision's typo before its first review is a legitimate,
  common operation the task does not ask to forbid — only *approved*
  content must never be silently edited (rule 12/13), which is
  enforced by the service refusing to mutate a revision once its
  parent record has reached `approved`.

### 3.2 Record types (`core_model/manual_data/__init__.py`, new package)

Exactly the 11 enum values from Step 2:
`plain_text, language_example, conversation, question_answer,
instruction_response, dictionary_entry, translation_pair,
tanglish_normalization, knowledge_note, grammar_example,
evaluation_case_draft` — stored as-is (never a display label).
Classification enums (`creation_method`, `fact_dependency`,
`knowledge_risk`) also exactly as specified in Step 2.

### 3.3 Lifecycle

Exactly the 7 states from Step 3: `draft, needs_review,
needs_source_verification, needs_domain_review, approved, rejected,
archived`. Transition table mirrors `TRANSITIONS`/`_SOURCE_STATUS_TRANSITIONS`'s
shape (dict of allowed next-states), with `approved` **not** directly
editable — an edit to an approved record creates a new `draft`
revision (`revision_number = active + 1`) tied to the same
`manual_data_records` row, going through review again before it can
become the new `active_revision_id`; the previously approved revision
row is never deleted or mutated (Step 15).

### 3.4 Quality module (`core_model/manual_data/quality.py`)

Pure function, same shape as `dataset_quality`'s: 8 dimensions from
Step 7, blocking-issue codes exactly as listed in Step 7
(`MISSING_SOURCE, RIGHTS_BLOCK_TRAINING, HIGH_RISK_UNVERIFIED,
EMPTY_REQUIRED_FIELD, AI_ASSISTED_UNREVIEWED, INVALID_LANGUAGE_PAIR,
TRANSLATION_UNVERIFIED, FACTUAL_CONFLICT`), `overall_score >= 85 AND
no blocking issues` as the approval baseline, with the threshold
exposed via `backend/config.py`'s existing settings object (not
hardcoded per call site).

### 3.5 Duplicate module (`core_model/manual_data/duplicates.py`)

Mirrors `dataset_service.normalize_text`/`content_hash` exactly:
NFC-normalize + collapse whitespace, SHA-256 of a canonical JSON of
the record-type's logical fields. Per-type duplicate keys: exact text
hash, normalized-text hash, source+type combination, and for
dictionary entries specifically a `(word, primary_language)` uniqueness
check against existing meanings. No semantic/embedding engine.

### 3.6 Usage decisions

`ManualDataUsageService.evaluate(record_id, target_use)` loads the
record's linked source + rights via the existing Phase 2 services,
calls `evaluate_source_usage()`, and additionally hard-blocks (before
even consulting source rights) when: the record's own lifecycle
status is not `approved` for any use beyond `rag`/internal review, the
record is `creation_method in {ai_assisted}` and has no human review
recorded, or `knowledge_risk in {high_risk, time_sensitive}` /
`fact_dependency == high` without a completed verification. Decisions
are cached in `manual_data_usage_decisions` for history/audit but are
always *recomputed* on a fresh usage-check call — a cached row is
never treated as permanent truth if rights change later (task's
explicit instruction), matching Phase 2's own `source_usage_decisions`
being an append-only log rather than a mutable cache.

## 4. record_type -> DatasetRecordType mapping for candidate export

| Manual `record_type` | `DatasetRecordType` |
|---|---|
| `language_example`, `plain_text`, `grammar_example` | `pretrain` |
| `conversation` | `chat` |
| `question_answer` | `instruction` |
| `instruction_response` | `instruction` |
| `translation_pair` | `translation` |
| `tanglish_normalization` | `tanglish_pair` |
| `dictionary_entry`, `knowledge_note` | `pretrain` |
| `evaluation_case_draft` | *not exportable* — evaluation drafts are never turned into training records, mirroring `feedback_dataset_service`'s explicit refusal to export `evaluation_only` candidates. |

## 5. API plan

`/api/admin/manual-data` — the 19 endpoints listed in Step 10,
verbatim, following `data_sources.py`'s route-file structure
(`APIRouter(prefix=..., dependencies=[Depends(require_admin)])` +
`CsrfDependency` per mutating route). Plus one additional action not
explicitly enumerated in Step 10 but required by Step 17:
`POST /api/admin/manual-data/{record_id}/create-dataset-candidate`.

## 6. Frontend plan

New sidebar entry `Manual Data`; new page `ManualDataPage.jsx` with
the 8 tabs from Step 12; type-specific editors as described in Step
13, each shown/hidden based on the selected `record_type` in the
guided create form (Step 12's 7 sub-steps); review workspace per Step
14 with per-use approval (never one global approve); revision history
panel per Step 15. `helpRegistry.js` gains one new bilingual
`manual_data` entry.

## 7. Migration plan

`MIGRATION_024_NAME = "024_data_studio_phase3_manual_data_studio"`,
`PHASE24_SCHEMA` constant, `_apply_v24()` wired into
`initialize_database` immediately after `_apply_v23()` — identical
structure to the v22->v23 wiring. `SCHEMA_VERSION` becomes 24.

## 8. Compatibility risks and mitigations

- **Risk**: adding a manual-data entity type to any Phase-2 enum table
  would require altering an existing migration. **Mitigation**: not
  needed — direct FK columns cover every linking scenario Phase 3
  requires (§3.1).
- **Risk**: a naive "approve -> auto-insert into dataset_records"
  action could silently create a second, divergent dataset-management
  system. **Mitigation**: the explicit, admin-triggered "Create
  Dataset Candidate" action reuses `DatasetService.create_record()`
  exactly, so every manual-derived dataset record still goes through
  the existing duplicate-hash check, quality assessment, and dataset
  lifecycle unchanged.
- **Risk**: editing an approved record in place would violate rule
  12/13. **Mitigation**: service-layer enforcement — `approved`
  records can only be mutated by creating a new revision in `draft`.
- **Risk**: schema/test regressions from `SCHEMA_VERSION` moving to 24
  (same class of issue hit twice in Phase 1/2: hardcoded
  `applied_migrations`/`SCHEMA_VERSION == N` assertions elsewhere).
  **Mitigation**: grep for both patterns before the final verification
  pass and update them the same way Phase 2 did.

## 9. Explicitly deferred (this phase)

Everything listed in the task's "Explicitly out of scope" section:
PDF/OCR redesign, semantic chunk editing, automatic translation/Tanglish
generation, semantic duplicate embeddings, dataset-version builder
changes, pipeline hard-block enforcement (Phase 2's rights-check
endpoints remain additive-only, not wired as a hard gate anywhere),
floating Admin Assistant, automated web/fact verification, public
user submission forms.
