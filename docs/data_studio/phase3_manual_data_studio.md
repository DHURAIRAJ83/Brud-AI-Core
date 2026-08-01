# Phase 3 — Manual Data Studio

Status: complete. Schema version 23 -> 24 (migration `024_data_studio_phase3_manual_data_studio`).

A governed staging layer for hand-authored Tamil/English/Tanglish language
data (spoken examples, conversations, Q&A, instructions, dictionary
entries, translations, Tanglish normalization pairs, knowledge notes,
grammar examples, evaluation drafts) that the existing manual dataset
entry system has no columns for. See
[phase3_manual_data_studio_plan.md](phase3_manual_data_studio_plan.md)
for the pre-implementation baseline audit and architectural decisions.

## 1. Architecture

Manual Data Studio does **not** compete with the existing manual
dataset-record API (`backend/services/dataset_service.py` +
`/api/admin/datasets/records`, live since Phase 1/3). It is a richer
staging layer in front of it: an approved manual record only becomes a
real `dataset_records` row through an explicit **Create Dataset
Candidate** action, which calls `DatasetService.create_record()`
directly — the exact same bridge `feedback_dataset_service.export_candidate()`
already uses for feedback-derived candidates — never writing to
`dataset_records` itself.

Every manual record links to a Phase 2 source via a required `source_id`
foreign key on `manual_data_records` (not via `source_record_links`,
whose `entity_type` CHECK constraint would need altering migration 023
to extend — instead of that, a direct FK column covers every linking
scenario this phase requires). A supporting/verifying source (the
"primary source + verified-against source" scenario) is linked via
`manual_data_verifications.source_id`, a separate optional FK.

Usage-eligibility decisions never duplicate Phase 2's rights logic:
`core_model.manual_data.usage_policy.evaluate_manual_record_usage()`
calls `core_model.data_governance.usage_policy.evaluate_source_usage()`
directly, then layers three manual-record-specific gates on top
(lifecycle status, AI-assisted-without-review, high-risk-without-
verification).

## 2. Schema (migration 024)

Six new tables, all additive — no existing table's schema changed:

| Table | Purpose |
|---|---|
| `manual_data_records` | Canonical record: `record_type`, `status`, `active_revision_id`, required `source_id`, classification (`primary_language`, `input_language`, `output_language`, `domain`, `topic`, `difficulty`, `audience`, `style`, `fact_dependency`, `knowledge_risk`, `creation_method`), `requested_uses_json`, `approved_uses_json`, `review_expiry_at`, `exported_dataset_record_public_id`. |
| `manual_data_record_revisions` | Append-only content history: typed columns for every record-type's common fields (`title`, `input_text`, `output_text`, `instruction_text`, `response_text`, `question_text`, `answer_text`, `tamil_text`, `english_text`, `tanglish_text`, `word`, `part_of_speech`) plus `meanings_json`/`examples_json`/`metadata_json` (conversation turns, alternate spellings, etc. — structured optional data only, per the task's explicit instruction not to store everything in one opaque blob) and `content_hash`. |
| `manual_data_reviews` | Human review actions: `review_type` (language/translation/factual/domain/general), `review_status`, per-dimension scores. |
| `manual_data_verifications` | Verification actions against a revision, with an optional linked supporting `source_id`. |
| `manual_data_usage_decisions` | Append-only usage-eligibility decision log (mirrors Phase 2's `source_usage_decisions`). |
| `manual_data_events` | Append-only domain event log (mirrors Phase 2's `source_verification_events`) — backs the record's own History tab. |

`manual_data_usage_decisions` and `manual_data_events` get the identical
`BEFORE UPDATE/DELETE ... RAISE(ABORT, ...)` append-only trigger pair
Phase 2 used. `manual_data_record_revisions` is logically append-only
(only `INSERT`, never `UPDATE`) enforced at the service layer rather
than by trigger — a legitimate pre-review typo fix on a still-`draft`
revision is not the same thing as mutating *approved* content, which
the service refuses outright (see §4).

## 3. Record types, lifecycle, and classification

11 stable machine-readable `record_type` values (never display labels):
`plain_text, language_example, conversation, question_answer,
instruction_response, dictionary_entry, translation_pair,
tanglish_normalization, knowledge_note, grammar_example,
evaluation_case_draft`.

7-state lifecycle (`core_model/manual_data/lifecycle.py`):
`draft -> needs_review -> needs_source_verification/needs_domain_review
-> approved -> rejected -> archived`, with `approved -> draft` reserved
exclusively for the **correction pathway**: creating a new revision
against an approved record moves it back to `draft` while the
previously approved revision row is never deleted or edited — verified
end-to-end in manual testing (Flow E, §8).

Classification: `creation_method` (`human_created, admin_created,
teacher_created, ai_assisted, imported_manual, derived_manual`),
`fact_dependency` (`none, low, medium, high`), `knowledge_risk`
(`language_only, general, domain_specific, high_risk, time_sensitive`).

## 4. Validation, quality, and duplicate detection

`core_model/manual_data/validation.py` — per-record-type structural
validation (non-empty required fields, distinct input/output languages
for translation pairs, at least two turns with valid roles for
conversations, a revalidation date for time-sensitive knowledge).

`core_model/manual_data/quality.py` — deterministic quality assessment:
8 dimensions (`language_correctness, meaning_correctness, naturalness,
completeness, source_reliability, factual_confidence, format_validity,
uniqueness`) plus severity-independent blocking issue codes
(`MISSING_SOURCE, RIGHTS_BLOCK_TRAINING, HIGH_RISK_UNVERIFIED,
EMPTY_REQUIRED_FIELD, AI_ASSISTED_UNREVIEWED, INVALID_LANGUAGE_PAIR,
TRANSLATION_UNVERIFIED, FACTUAL_CONFLICT`). A blocking issue always
overrides the recommended status regardless of how high the average
score is — verified directly by a dedicated unit test
(`test_high_score_cannot_hide_blocking_issue`) and confirmed live in
manual testing (Flow C: a 78/100-scoring high-risk note was still
blocked from approval until verified).

`core_model/manual_data/duplicates.py` — exact-hash duplicate
detection mirroring `dataset_service.normalize_text`/`content_hash`
exactly (NFC normalize + whitespace collapse + optional casefold,
SHA-256 of canonical JSON); a dictionary-specific `(word,
primary_language)` uniqueness key. No semantic/embedding engine, per
the explicit deferral in this phase's scope.

Approval is gated on `ManualDataRecordService.approve()` re-running the
quality assessment and refusing (`ValidationError` -> 422) if any
blocking issue remains — never silently overridden.

## 5. Source-rights integration (rule 15)

`core_model/manual_data/usage_policy.py`'s `evaluate_manual_record_usage()`
calls Phase 2's `evaluate_source_usage()` directly rather than
duplicating rights logic. `ManualDataUsageService` loads the record's
linked source + rights, evaluates all 6 target uses on demand, and
persists every decision (append-only) without ever treating a cached
decision as permanent truth — a fresh check always re-evaluates.

Approval never blindly grants an admin's requested uses:
`ManualDataRecordService.approve()` re-checks each requested use
against the full policy gate (as if the record were already approved)
and silently drops any use that would still be blocked (unreviewed
AI content, unverified high-risk facts, unknown/insufficient source
rights), reporting the dropped uses back as `blocked_uses` rather than
granting them anyway. Verified in both automated tests
(`test_approve_drops_uses_blocked_by_source_rights`,
`test_approve_grants_uses_when_rights_allow`) and manual testing
(Flows A/B: `approved_uses: []` when no rights were ever declared).

## 6. Backend: repository / service / API layers

- `backend/database/repositories/manual_data.py` — `ManualDataRepository`,
  following `DataSourceRepository`'s `transaction(immediate=True)` and
  `public_row()` conventions exactly.
- `backend/services/manual_data_service.py` — `ManualDataRecordService`,
  `ManualDataReviewService`, `ManualDataVerificationService`,
  `ManualDataQualityService`, `ManualDataUsageService`.
- `backend/services/manual_data_candidate_service.py` —
  `ManualDataCandidateService`, the dataset-candidate bridge (§1).
- `backend/api/routes/manual_data.py` — 26 endpoints under
  `/api/admin/manual-data`, all behind `require_admin` + `CsrfDependency`:

  ```
  GET    /api/admin/manual-data
  GET    /api/admin/manual-data/summary
  POST   /api/admin/manual-data
  GET    /api/admin/manual-data/{id}
  PATCH  /api/admin/manual-data/{id}
  POST   /api/admin/manual-data/{id}/archive
  POST   /api/admin/manual-data/{id}/restore
  GET    /api/admin/manual-data/{id}/revisions
  POST   /api/admin/manual-data/{id}/revisions
  GET    /api/admin/manual-data/{id}/revisions/{revision_id}
  POST   /api/admin/manual-data/{id}/submit-review
  POST   /api/admin/manual-data/{id}/request-correction
  POST   /api/admin/manual-data/{id}/request-source-verification
  POST   /api/admin/manual-data/{id}/request-domain-review
  POST   /api/admin/manual-data/{id}/review
  GET    /api/admin/manual-data/{id}/reviews
  POST   /api/admin/manual-data/{id}/verify
  GET    /api/admin/manual-data/{id}/verifications
  POST   /api/admin/manual-data/{id}/approve
  POST   /api/admin/manual-data/{id}/reject
  POST   /api/admin/manual-data/{id}/quality-check
  POST   /api/admin/manual-data/{id}/duplicate-check
  POST   /api/admin/manual-data/{id}/usage-check
  GET    /api/admin/manual-data/{id}/usage-summary
  GET    /api/admin/manual-data/{id}/history
  POST   /api/admin/manual-data/{id}/create-dataset-candidate
  ```

Every mutation writes both a general `audit_logs` row (matching
`dataset_service.py`'s `_audit` convention) and a domain-specific
`manual_data_events` row (matching Phase 2's convention), so the
system-wide audit trail and the record's own History tab both stay
populated.

## 7. Frontend

- New sidebar entry **Manual Data** in the `Data` group, between
  `Datasets` and `Sources & Rights`.
- `ManualDataPage.jsx` — 8 tabs: **Overview** (honest live counts by
  status), **Create Data** (guided form: data type, source
  existing-or-new, classification, requested uses, type-specific
  content fields, save-as-draft only — no direct approval from this
  screen), **Records** (list/filter/archive/restore), **Review Queue**
  (quality/duplicate check, review submission, source/domain-review
  requests), **Verification Queue** (attach a supporting source and
  record a verification), **Approved** (per-use approval summary +
  explicit "Create Dataset Candidate" action), **Rejected**, **History**
  (revisions, events, and the full 6-target-use eligibility grid).
- `ContentFields`, `RecordSelector`, and `ReviewWorkspace` are hoisted
  to module scope (not redefined inside the page component's render
  body) — a real bug was caught here during manual testing where
  defining them inline caused React to remount the review panel on
  every keystroke, silently dropping all but the first typed character
  (see §9).
- `helpRegistry.js` gained a new bilingual `manual_data` help entry
  (EN/TA) with guided examples matching the task's list (Dhurai's
  spoken Tamil, a Tanglish phrase, a customer-service conversation, a
  dictionary word, a government-service procedure, medical
  information, an AI-generated Q&A); the existing `datasets` entry's
  `nextPageIds` now also links to it.

## 8. Manual browser verification (Flows A-E)

All five required flows were exercised end-to-end against the real
dev server + real backend (Playwright), each creating a fresh
timestamped source/record to avoid collisions with prior runs:

- **Flow A (spoken Tamil)**: create human-created source inline ->
  plain-text record -> submit for review -> quality check (no blocking
  issues) -> approve for RAG+training -> both **correctly dropped**
  (`BLOCKED_RIGHTS_UNKNOWN`, no rights ever declared) -> Create Dataset
  Candidate succeeds, stamping `exported_dataset_record_public_id`.
- **Flow B (Tanglish)**: `tanglish_normalization` record (Tanglish +
  normalized Tamil) -> submit -> approve -> same correct fail-closed
  drop for RAG (no rights declared).
- **Flow C (high-risk factual)**: `knowledge_note` with
  `knowledge_risk=high_risk`, `fact_dependency=high` -> quality check
  before verification shows `HIGH_RISK_UNVERIFIED` -> supporting source
  attached + verification recorded (`verified`) -> blocking issue
  clears -> approval now succeeds.
- **Flow D (AI-assisted)**: `question_answer` record with
  `creation_method=ai_assisted` -> quality check shows
  `AI_ASSISTED_UNREVIEWED` until a human review is recorded.
- **Flow E (revision on an approved record)**: approved plain-text
  record edited via "Edit content" -> new revision created, record
  moves `approved -> draft`, previous revision preserved untouched ->
  History tab shows both revisions (`#1 initial draft`, `#2 <summary>`)
  and the full event chain (`record_created -> submitted_for_review ->
  approved -> revision_created`).

Also verified: bookmarked hash route (`#Manual%20Data` opened directly
in a fresh tab correctly restores the page with the Data group
expanded), hard refresh (route and expansion state both survive),
narrow/mobile layout (390px viewport — tabs scroll horizontally, metric
cards stack in a single column, no overflow), and the bilingual
(EN/TA) help entry.

## 9. Real bugs found and fixed during manual verification

Manual browser testing (not the automated suite) caught two genuine
application bugs, both fixed in this session:

1. **Invalid lifecycle transitions returned an uncaught 500 instead of
   a clean 422.** `core_model.manual_data.lifecycle.validate_transition`
   raises a bare `ValueError` (it is a pure, framework-agnostic
   module) — but `ManualDataRecordService._transition()`/`.approve()`
   called it directly, so an invalid transition (e.g. attempting to
   approve a fresh `draft` record) fell through FastAPI's generic
   `Exception` handler as an "Internal server error" rather than the
   registered `RepositoryError` handler's 422. Fixed by wrapping the
   call in a local `_validate_transition()` that translates `ValueError`
   into `ValidationError`. A regression test
   (`test_invalid_transition_returns_422_not_500`) now asserts the 422.
2. **Editing an approved record's content always failed with a 422.**
   `ManualDataPage.jsx`'s `contentFromRevision()` spread the *entire*
   fetched revision object into the edit form's state, including
   server-only fields (`public_id`, `revision_number`, `content_hash`,
   `created_by_admin_public_id`, `created_at`) that Pydantic's
   `extra="forbid"` then rejected on submit. Fixed by picking only the
   legitimate content field keys. Caught via direct network-response
   inspection during Flow E manual testing; confirmed fixed by
   re-running the same flow, which then showed both revisions
   correctly preserved.
3. **Classification fields silently carried over between records.**
   After creating a record, only the type-specific `content` was reset
   — `recordForm` (record type, primary language, domain, topic,
   **fact dependency, knowledge risk**, creation method, requested
   uses) was left at whatever the previous record used. Caught when a
   `question_answer` record created immediately after a `high_risk`
   `knowledge_note` inherited that note's risk classification, which
   would have silently mis-categorized real data in production use.
   Fixed by resetting the full form (including source-selection state)
   after a successful create.

## 10. Test evidence

New tests added this phase (all passing):

| File | Tests |
|---|---|
| `tests/core_model/test_manual_data_validation.py` | 15 |
| `tests/core_model/test_manual_data_duplicates.py` | 7 |
| `tests/core_model/test_manual_data_quality.py` | 13 |
| `tests/core_model/test_manual_data_usage_policy.py` | 9 |
| `tests/database/test_phase24_migration.py` | 4 |
| `tests/database/test_manual_data_repository.py` | 7 |
| `tests/backend/test_manual_data_service.py` | 21 |
| `tests/backend/test_manual_data_api.py` | 13 |
| `apps/admin-dashboard/src/pages/ManualDataPage.test.jsx` | 14 |
| **Total new** | **103** |

Regression fixes required by the migration (schema version moved from
23 to 24, same class of issue hit in Phases 1/2): `tests/backend/test_system_api.py`
(added migration 024 to the expected `applied_migrations` set) and
`tests/database/test_phase23_migration.py` (two assertions hardcoded
`SCHEMA_VERSION == 23`; changed to compare dynamically while keeping
`>= 23`).

Final verification run (this session, 2026-07-26), after all bug
fixes above were applied:

- `python -m pytest tests/backend tests/database tests/core_model -q`
  — **698 passed**, 0 failed (14m48s).
- `ruff check .` — clean, project-wide.
- `npm run test --prefix apps/admin-dashboard -- --run` — 44 passed
  (4 files).
- `npm run build --prefix apps/admin-dashboard` — succeeds.
- `npm run build --prefix apps/chatbot` — succeeds.
- `python -m backend.database.migrations status` — current version
  24, all 24 migrations listed as applied.
- `python -m backend.database.migrations verify` — `{"integrity_check":
  "ok", "foreign_key_violations": []}`.

## 11. Limitations / explicitly deferred

- No pipeline is hard-blocked by manual-data usage decisions yet — the
  usage-check/summary endpoints are additive read/decision APIs, exactly
  mirroring Phase 2's own additive-only integration. Wiring an automatic
  hard gate into dataset build/RAG ingestion/pretraining readiness
  remains future scope.
- No existing dataset record, document, or RAG source was backfilled
  or modified — this phase only adds new tables and new admin-facing
  workflows.
- Out of scope per the task's explicit list and left untouched: PDF
  page preview redesign, OCR side-by-side editor, semantic chunk
  split/merge, dictionary PDF parser, automatic translation/Tanglish
  generation, semantic duplicate embeddings, dataset-version builder
  changes, floating Admin Assistant, automated web/fact verification,
  public user submission forms.

**Do not proceed to Phase 4.**
