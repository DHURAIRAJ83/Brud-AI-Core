# Phase 2 — Source, Rights & Usage Registry: Plan

## 0. Working-tree check (Step 1)

`git status --short` at the start of this phase showed exactly the Phase 1 diff from the
completion report (6 modified files under `apps/admin-dashboard`, the 8 new Phase 1 files/dirs)
plus the pre-existing untracked `.claude/` and `data/manual_verification_*` directories. Nothing
was reset, overwritten, or discarded; those two untracked paths remain untouched throughout Phase 2.

## 1. What already exists (do not duplicate)

This is the single most important finding of this plan: **a source/rights governance system
already exists**, built in Phases 19-20 for the corpus builder, and it is comprehensive.

### 1.1 `dataset_sources` (Phase 2/3) — lightweight, per-record

`id, public_id, name, source_type, original_filename, source_uri, language, licence_name,
licence_status ('unknown' default), checksum_sha256, status, metadata_json`. One row per
dataset source; `dataset_records.source_id` FKs into it directly. No separate rights table, no
usage-eligibility flags beyond a single `licence_status` string, no verification history.

### 1.2 `corpus_source_registries` + `corpus_source_licences` (Phase 19/20) — comprehensive, corpus-pipeline-scoped

`corpus_source_registries`: `source_type` (CHECK-constrained to pipeline-specific values like
`uploaded_pdf`, `manual_admin_text`, `government_publication`, ...), `author_or_organisation`,
`publisher`, `original_publication_date`, `source_reference`, `language`, `domain`,
`ownership_claim`, `origin_verified` (bool) + `origin_evidence` (text, no history), `status`
(draft/origin_review/licence_review/approved/approved_with_restrictions/rejected/quarantined/
disputed/archived) — **and, critically, `corpus_policy_id INTEGER NOT NULL REFERENCES
corpus_policies(id)`**.

`corpus_source_licences`: `licence_family`, `licence_name`, `copyright_holder`,
`allowed_uses_json`/`prohibited_uses_json`, `attribution_required`, `share_alike_required`,
`commercial_use_permitted`, `modification_permitted`, `ai_training_permitted`,
`redistribution_permitted`, `evidence_type`, `review_status`, `valid_from`/`expires_at`. This is
already almost exactly the task's requested `source_rights` shape, field-for-field.

`core_model/corpus/licence_policy.py::assess_training_export_eligibility()` is already a pure,
deterministic, unit-tested policy function taking explicit booleans/statuses and returning
`{"eligible": bool, "blocking_reasons": [...]}` — the exact shape Step 4 of this phase asks for.

### 1.3 Why this phase does not simply extend `corpus_source_registries` in place

The blocking structural fact: **every `corpus_source_registries` row requires a
`corpus_policy_id`**. A corpus policy is itself a heavyweight object (byte/character limits,
allowed source types, allowed licence statuses, export format policy) meant for large-scale
corpus assembly runs. Forcing an admin to create/select a corpus policy before they can declare
"this paragraph of spoken Tamil is something I wrote myself" would be exactly the kind of
awkward, purpose-mismatched reuse this task's own rule 5 ("reuse... without breaking existing
workflows") warns against, and its Step 1 instruction "extend and normalize it" together with
"do not duplicate" has to be read against that constraint.

Also blocking: `corpus_source_registries.source_type` and `.status` are SQLite `CHECK`
constraints. SQLite cannot add a value to an existing `CHECK (... IN (...))` without a full table
rebuild — this is the *exact* problem Phase 20's own migration already solved once (see its
`_PRODUCTION_LIFECYCLE_TRANSITIONS` comment in `corpus_source_service.py` and the
`production_lifecycle_status` additive column in `schema.py`) by layering a **new, additive**
column next to the old CHECK'd one rather than touching the CHECK. This phase cannot add
`human_created`/`ai_generated`/`user_contributed`/etc. into the existing `source_type` CHECK for
the same reason, and does not attempt to.

### 1.4 Decision: one new, general-purpose registry; normalize policy across both systems

- **New tables** `data_sources` / `source_rights` / `source_verification_events` /
  `source_usage_decisions` / `source_record_links` (Step 6) form a general registry for *any*
  origin of data entering Brud AI, independent of the corpus-policy pipeline. This is not a
  duplicate of §1.2 — it is scoped differently (no mandatory policy, covers human-authored
  admin content, individual dataset records, documents, and can also point *at* an existing
  `corpus_source_registries` row for cross-reference) and it uses the task's requested enum
  values (`human_created`, `ai_assisted`, ...) that the old CHECK constraint structurally cannot
  hold.
- **No column is added to `corpus_source_registries` or `corpus_source_licences`.** Zero risk to
  already-tested Phase 19/20 tables/migrations.
- **Normalization happens at the policy layer, not the schema layer**: `core_model/
  data_governance/usage_policy.py`'s `evaluate_source_usage()` takes a small, storage-agnostic
  `EffectiveRights` mapping (a plain dict of the six allowed-use booleans + status strings) that
  either `source_rights` (new) or `corpus_source_licences` (existing) can be adapted into. Two
  thin adapter functions (`rights_from_source_rights_row`, `rights_from_corpus_licence_row`)
  live beside it. This is the concrete meaning of "extend and normalize" here: one policy brain,
  two existing/new data shapes feeding it, matching the corpus system's own
  `assess_training_export_eligibility` in spirit and even in decision-code style, without forking
  its logic.
- `dataset_sources`/`dataset_records.source_id` (§1.1) is left completely untouched. The new
  `source_record_links` table can additionally reference a `dataset_source` or `dataset_record`
  by `entity_type`/`entity_public_id`, giving richer multi-source attribution *on top of* the
  existing single-FK relationship without replacing it.

## 2. Current usage gates (what exists today)

- `corpus.py`'s `/sources/{id}/training-eligibility` — corpus-pipeline-only, via
  `assess_training_export_eligibility`.
- `dataset_records`/`dataset_versions` — build/export today does not check
  `dataset_sources.licence_status` at all; a `licence_status='unknown'` source's records can
  already reach an exported dataset version. Phase 2 does **not** retroactively change this
  existing flow's default behaviour (rule 7: no silent full-authorization, but also no silent
  breakage) — it *adds* an explicit, opt-in preflight check (Step 9) that surfaces this gap
  going forward without turning existing passing builds into failing ones by surprise.
- RAG ingestion (`rag.py`) has no source-rights gate at all today (only source
  `licence_status` field exists on `rag_sources`? — to confirm during implementation; RAG's own
  source model is separate again from both systems above and will also gain an optional
  `source_record_links` cross-reference).
- Pretraining readiness reports corpus/dataset readiness but not rights eligibility.

## 3. Migration plan

Next migration: **`023_data_studio_phase2_source_rights_registry`** (schema version 22 → 23),
following the exact `_apply_v22`/`PHASE22_COLUMNS`/trailing-schema-block convention in
`backend/database/schema.py` and `backend/database/migrations.py`. Additive only: five new
`CREATE TABLE IF NOT EXISTS` statements, their indexes, and append-only triggers for
`source_verification_events` and `source_usage_decisions` (mirroring Phase 19/20's
`BEFORE UPDATE/DELETE ... RAISE(ABORT, ...)` pattern). No `ALTER` of any existing table. Backup
before/after via the existing `initialize_database`/`upgrade_database` machinery, unchanged.
Legacy data is not backfilled with any source link or rights assertion — existing
`dataset_sources`/`corpus_source_registries` rows simply have zero `source_record_links` rows
pointing at them until an admin explicitly creates one, which is the transparent, non-destructive
option the task allows (no fabricated `legacy_unclassified` source is created, since that would
itself be an assertion this system has no evidence for).

## 4. API plan

New router `backend/api/routes/data_sources.py`, prefix `/api/admin/data-sources`, registered in
`backend/api/router.py`, `Depends(require_admin)` + CSRF on mutations — identical posture to
every other admin router. Endpoints follow the task's Step 8 list exactly.

## 5. Frontend plan

New Sidebar child `Sources & Rights` (key: `Sources & Rights`) under the existing Phase 1 `Data`
group, auto-expand preserved via the existing `isWithin()` mechanism (no changes to that
mechanism itself — the new key is simply added to the Data group's `children` array). New page
`SourcesRightsPage.jsx` with the six tabs the task lists. New help entries appended to the
existing `helpRegistry.js` array (not a new file, not a competing registry).

## 6. Compatibility risks

- Risk: fragmenting policy logic between the new and the corpus-pipeline systems. Mitigated by
  the single shared `evaluate_source_usage()` + adapters (§1.4).
- Risk: an admin expects an existing `corpus_source_registries` source to "just show up" in the
  new registry. Mitigated by making this explicit in the UI/docs: the new registry is additive;
  a corpus-pipeline source can be *linked* to a new `data_sources` row for cross-visibility but
  is not automatically migrated or duplicated into it.
- Risk: new preflight checks silently changing existing build/export/RAG behaviour. Mitigated by
  making every new gate an explicit, separately-callable check (Step 9) that reports blocked
  counts/reasons rather than retrofitting a hard failure into an existing endpoint's default path
  without an opt-in flag — the exact mechanism will be finalized per-integration-point during
  implementation and recorded in the final Phase 2 doc.

## 7. Explicitly out of scope (unchanged from the task)

Manual Data Studio record editor, new PDF/OCR visual workspace, chunk split/merge editor,
dictionary extraction, translation studio, Tanglish studio, semantic duplicate engine, new
dataset version builder, floating Admin Assistant UI, AI-assisted source research, automated
internet licence lookup, legal advice, automatic permission requests. Also out of scope for this
phase specifically: touching `corpus_source_registries`/`corpus_source_licences` schema,
touching `dataset_sources`/`dataset_records.source_id`, retroactive backfill of rights for legacy
data.
