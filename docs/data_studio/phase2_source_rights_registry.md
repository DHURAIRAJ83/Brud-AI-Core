# Phase 2 — Source, Rights & Usage Registry

Status: complete. Schema version 22 -> 23 (migration `023_data_studio_phase2_source_rights_registry`).

This document describes what was built, why it was built as a new
parallel registry rather than an extension of the existing corpus
provenance tables, and how every other subsystem (dataset builds, RAG
ingestion, pretraining readiness, export) now asks it before trusting
data it did not originate.

See also: [phase2_source_rights_registry_plan.md](phase2_source_rights_registry_plan.md)
(written before implementation; records the baseline audit and the
architectural decision) and [phase1_unified_data_navigation.md](phase1_unified_data_navigation.md)
(Phase 1, unchanged by this phase except that its `Datasets` help entry
now also points at the new `Sources & Rights` help entry as a "next"
link).

## 1. Why a new registry instead of extending `corpus_source_registries`

The corpus builder (Phase 19/20) already has `corpus_source_registries`
and `corpus_source_licences`, but both are structurally scoped to the
corpus pipeline specifically:

- every `corpus_source_licences` row requires a `corpus_policy_id`
  foreign key -- there is no such policy concept for, say, a manually
  entered Tamil proverb or an uploaded PDF outside the corpus builder;
- the CHECK constraints on those tables enumerate corpus-specific
  values and can't gain new enum members (`human_created`,
  `ai_assisted`, etc.) without rewriting an existing migration, which
  is against the rules for this phase.

Rather than merge the two schemas (risking exactly the kind of
destructive, backwards-incompatible change this phase must avoid), the
new tables (`data_sources`, `source_rights`, `source_verification_events`,
`source_usage_decisions`, `source_record_links`) form a general-purpose
registry that:

- covers every kind of thing entering Brud AI (documents, dataset
  records, RAG knowledge sources, corpus items, evaluation cases -- see
  `ENTITY_TYPES` in `core_model/data_governance/__init__.py`), and
- shares its **decision shape**, not its schema, with the corpus
  builder's policy: `core_model/data_governance/usage_policy.py`
  mirrors `core_model.corpus.licence_policy` (deterministic decision +
  explicit list of blocking reasons, never a bare boolean), and even
  ships an adapter (`rights_from_corpus_licence_row`) so an existing
  `corpus_source_licences` row can be evaluated by the same policy
  brain without altering that table at all.

Nothing about the existing corpus provenance system was touched.

## 2. Schema (migration 023)

Five new tables, all created only if the database is fresh or being
migrated forward -- no existing table's schema changed:

| Table | Purpose |
|---|---|
| `data_sources` | One row per source: `source_code`, `title`, `source_type`, `status`, `risk_level`, plus optional `independent_reviewer_required` / `internal_rag_policy_allows_unknown_rights` policy flags. |
| `source_rights` | 1:1 with a source: `rights_status`, `verification_status`, the six per-target-use booleans (`rag_use_allowed`, `training_use_allowed`, `evaluation_use_allowed`, `commercial_use_allowed`, `public_export_allowed`, `redistribution_allowed`), `internal_only`, `attribution_required`/`attribution_text`, licence/permission references, `permission_expires_at`. |
| `source_verification_events` | Append-only (trigger-enforced) log of every verification action taken (`self_declare`, `document_verify`, `owner_confirm`, `legal_review`, `reject`, `expire`, `restrict`) with actor and note. |
| `source_usage_decisions` | Append-only log of every usage-eligibility check ever run, one row per `(source, target_use, decision)` -- this is the audit trail proving a use was actually checked, not assumed. |
| `source_record_links` | Polymorphic `entity_type` + `entity_public_id` link from any record elsewhere in Brud AI to the source(s) it came from, with a `relationship_type` (`primary_source`, `derived_from`, `translated_from`, `generated_from`, ...). |

Existing records everywhere else in the system are unaffected: a
dataset record, document, or RAG source with **no** row in
`source_record_links` is simply reported as `unlinked` by the new
policy endpoints -- it is not silently treated as authorized, and it
does not stop being readable through any existing page or API.

Enums for every `CHECK` constraint are centralized in
`core_model/data_governance/__init__.py` as the single source of
truth shared by schema, models, and policy.

## 3. Source types (human-created data is a first-class citizen)

Per the task's explicit requirement to support human-created knowledge
that never came from a document or the internet, `SOURCE_TYPES`
includes `human_created`, `admin_created`, `teacher_created`, and
`institution_created` alongside the document/web/dataset-derived types
and `ai_assisted` / `ai_generated`. A human-created source can be
declared, given rights (typically `rights_status=public_domain` or an
explicit `permission_granted` if it's a named contributor's work), and
used exactly like any other source -- it is not a special case in the
policy engine, only in the UI's source-type dropdown.

## 4. Rights, verification, and the usage-decision matrix

`evaluate_source_usage(source, rights, target_use)` in
`core_model/data_governance/usage_policy.py` is the single policy
brain. It is a pure function (no DB/IO) and deliberately never reads
`source_url`, hosting information, publication age, or the presence of
a copyright notice -- rule 10 ("never infer legal permission from
public accessibility / government hosting / age / a download URL /
lack of a copyright notice") is enforced structurally by the function
signature simply never accepting those fields, not by convention.

Decision codes returned (never a bare boolean):

| Code | Meaning |
|---|---|
| `ALLOWED` | Requested use is permitted. |
| `REVIEW_REQUIRED_INTERNAL_RAG` | Rights are unknown/pending, but an *explicit* admin policy flag permits private/internal RAG only (rule 9 -- never assumed, must be turned on deliberately). |
| `BLOCKED_RIGHTS_UNKNOWN` | No rights declaration exists at all. |
| `BLOCKED_PERMISSION_PENDING` | A rights review is in progress but not finished. |
| `BLOCKED_TRAINING_NOT_ALLOWED` / `BLOCKED_RAG_NOT_ALLOWED` / `BLOCKED_EVALUATION_NOT_ALLOWED` / `BLOCKED_COMMERCIAL_NOT_ALLOWED` / `BLOCKED_PUBLIC_EXPORT_NOT_ALLOWED` / `BLOCKED_REDISTRIBUTION_NOT_ALLOWED` | The specific per-use flag on the rights declaration is false. |
| `BLOCKED_LICENSE_EXPIRED` | `permission_expires_at` is in the past. |
| `BLOCKED_SOURCE_REJECTED` | Source status is `rejected`/`archived`, or `restricted` for a non-RAG use. |
| `BLOCKED_VERIFICATION_REQUIRED` | Source is AI-assisted/AI-generated (or flagged `independent_reviewer_required`) and hasn't reached a strong verification status (`document_verified`, `owner_confirmed`, `legal_reviewed`) yet -- rule 11 ("AI-generated or AI-assisted records must not become approved without human review") enforced unconditionally for every non-RAG use. |

Fail-closed defaults (rule 8/9): unknown or incomplete rights block
`training`, `commercial`, and `public_export` always; they are
*eligible* for internal RAG only when
`internal_rag_policy_allows_unknown_rights` is explicitly set true on
that source -- there is no default or implicit path to that state.

`validate_rights_combination()` additionally rejects internally
inconsistent declarations before they can be saved, e.g.
`training_use_allowed=true` while `rights_status` is still `unknown`,
or `commercial_use_allowed=true` without a strong verification status.

## 5. Backend: repository / service / API layers

- `backend/database/repositories/data_sources.py` --
  `DataSourceRepository`, following the existing
  `BaseRepository.transaction(immediate=True)` convention (claims the
  SQLite write lock upfront, same pattern as every other Phase
  19-22 repository) and the project's `public_row()` convention for
  stripping internal ids and un-JSONing `_json` fields.
- `backend/services/data_source_service.py` -- four services:
  `SourceRegistryService` (CRUD + archive/restore + polymorphic
  links), `SourceRightsService` (rights upsert + the verification
  state machine: `draft -> needs_review -> verified/restricted/rejected -> archived`,
  with `archived -> draft` as the only way back in), `SourceUsagePolicyService`
  (runs `evaluate_source_usage`, records the decision, and exposes
  `rights_summary_for_entities()` for cross-system integration), and
  `SourceVerificationService` (verification-event history).
- `backend/api/routes/data_sources.py` -- 19 endpoints under
  `/api/admin/data-sources`, all behind `require_admin` +
  `CsrfDependency` like every other admin mutation route in this
  codebase:

  ```
  GET    /api/admin/data-sources
  POST   /api/admin/data-sources
  GET    /api/admin/data-sources/{id}
  PATCH  /api/admin/data-sources/{id}
  POST   /api/admin/data-sources/{id}/archive
  POST   /api/admin/data-sources/{id}/restore
  GET    /api/admin/data-sources/{id}/rights
  PUT    /api/admin/data-sources/{id}/rights
  POST   /api/admin/data-sources/{id}/submit-review
  POST   /api/admin/data-sources/{id}/verify
  POST   /api/admin/data-sources/{id}/restrict
  POST   /api/admin/data-sources/{id}/reject
  GET    /api/admin/data-sources/{id}/links
  POST   /api/admin/data-sources/{id}/links
  DELETE /api/admin/data-sources/{id}/links/{link_id}
  POST   /api/admin/data-sources/{id}/usage-check
  GET    /api/admin/data-sources/{id}/usage-summary
  GET    /api/admin/data-sources/{id}/history
  GET    /api/admin/data-sources/{id}/verification-events
  ```

Every state-changing endpoint writes an audit event in the same
transaction as the mutation, via the same raw
`INSERT INTO audit_logs(...)` pattern used by
`corpus_source_service.py`/`admin_assistant_service.py` (rule: "every
state change must create an audit event").

## 6. Integration with existing subsystems (additive only)

Two small, purely additive GET endpoints let any existing subsystem
ask "is this allowed?" without that subsystem needing its own copy of
the policy logic:

- `GET /api/admin/datasets/versions/{public_id}/rights-summary?target_use=training`
  (added to `backend/api/routes/datasets.py`) -- walks every record in
  a dataset version and reports `allowed` / `blocked` / `review_required`
  / `unlinked` record ids plus `blocking_reasons`, so a dataset build
  or export step can check eligibility before proceeding.
- `GET /api/admin/rag/sources/{public_id}/rights-check` (added to
  `backend/api/routes/rag.py`) -- same evaluation for a single RAG
  knowledge source, target use fixed to `rag`.

Both are read-only additions to existing route files; no existing
route, response shape, or test was changed. When a record has multiple
linked sources, `rights_summary_for_entities()` applies "weakest link
governs" -- the record is only `allowed` if every linked source is.

Pretraining readiness and export flows can call the dataset-version
endpoint the same way; this phase wires the endpoint itself but does
not (per the task's scope) modify the pretraining-readiness or export
pipelines to hard-block on the result -- see Limitations below.

## 7. Frontend

- New sidebar entry **Sources & Rights** in the `Data` group, between
  `Datasets` and `Documents` (`Sidebar.jsx`).
- New page `SourcesRightsPage.jsx` with six tabs: **Overview** (honest
  counts by status, including zero states), **Sources** (create/list/archive/restore),
  **Rights Review** (per-source rights declaration with six explicit
  checkboxes -- `RAG`, `Training`, `Evaluation`, `Commercial use`,
  `Public export`, `Redistribution` -- deliberately never a single
  ambiguous "approved" toggle, plus the verification-action buttons:
  Submit for review / Verify (document) / Restrict / Reject),
  **Usage Eligibility** (single-use check and an all-six-uses-at-a-glance
  summary), **Verification History** (event log per source), and
  **Blocked Items** (only `restricted`/`rejected` sources, with an
  honest empty state).
- `helpRegistry.js` gained a new bilingual `sources_rights` help entry
  covering: what a source is vs. its rights, why human-created data
  still needs a rights declaration, why factual/public/government
  hosting never implies permission, and the six target-use meanings
  with common blocked-state examples. The existing `datasets` help
  entry's `nextPageIds` now also links to it; its own historical
  content was not rewritten.

## 8. Test evidence

New tests added this phase (all passing):

| File | Tests |
|---|---|
| `tests/core_model/test_data_governance_usage_policy.py` | 35 |
| `tests/database/test_phase23_migration.py` | 5 |
| `tests/database/test_data_source_repository.py` | 6 |
| `tests/backend/test_data_source_service.py` | 16 |
| `tests/backend/test_data_sources_api.py` | 11 |
| `tests/backend/test_data_sources_integration.py` | 3 |
| `apps/admin-dashboard/src/pages/SourcesRightsPage.test.jsx` | 12 |
| **Total new** | **88** |

Regression fixes required by the new migration (schema version moved
from 22 to 23): `tests/backend/test_system_api.py` (added migration
023 to the expected `applied_migrations` set) and
`tests/database/test_phase22_migration.py` (two assertions hardcoded
`SCHEMA_VERSION == 22`; changed to compare dynamically against
`SCHEMA_VERSION` while keeping `>= 22`).

Final verification run (this session, 2026-07-26):

- `python -m pytest tests/backend tests/database tests/core_model -q` -- **609 passed**, 0 failed, 13m39s.
- `ruff check .` -- clean, project-wide.
- `npm run test --prefix apps/admin-dashboard -- --run` -- **30 passed** (3 files).
- `npm run build --prefix apps/admin-dashboard` -- succeeds.
- `npm run build --prefix apps/chatbot` -- succeeds.
- `python -m backend.database.migrations status` -- current version 23, all 23 migrations listed as applied, `022_phase22_admin_assistant_execution_tracking` through `023_data_studio_phase2_source_rights_registry` present.
- `python -m backend.database.migrations verify` -- `{"integrity_check": "ok", "foreign_key_violations": []}`.
- Manual browser verification (Playwright against the real dev server + real backend): source creation, rights declaration and save, submit-for-review -> document-verify transition, usage-eligibility check transitioning from `BLOCKED_RIGHTS_UNKNOWN` to `ALLOWED` after verification, the six-target-use summary grid, verification-history log, and the bilingual (EN/TA) help entry were all exercised end-to-end and screenshotted. Two real CSS layout bugs were found this way (grid-stretched checkboxes/buttons; bare controls stretched full-width outside a flex wrapper) and fixed -- see the plan doc's "problem solving" notes for detail.

## 9. Limitations / explicitly deferred

- The two new integration endpoints (`rights-summary`, `rights-check`)
  are additive read-only checks. This phase does not modify the
  dataset-build, RAG-ingestion, or pretraining-readiness pipelines to
  automatically call and hard-block on them -- doing so would be a
  behavioral change to those existing workflows beyond a forward-compatible
  schema addition, and was not requested as part of this phase's
  explicit step list. Wiring an automatic hard gate is natural Phase 3
  scope.
- No backfill was performed against any existing dataset record,
  document, or RAG source -- they all correctly report as `unlinked`
  (not `allowed`, not `blocked`) until an admin explicitly links them
  to a declared source, per the "do not perform destructive backfills"
  and "must not be silently marked as fully authorized" rules.
  Existing pages, records, and workflows remain fully readable and
  functional exactly as before.
- No AI-assisted legal research, automated licence lookup, or
  automatic permission request was implemented, per the explicit
  out-of-scope list.
- Manual Data Studio, PDF Workspace redesign, semantic chunk editor,
  Tanglish editor, and the floating Admin Assistant remain untouched,
  per the explicit out-of-scope list.

**Do not proceed to Phase 3.**
