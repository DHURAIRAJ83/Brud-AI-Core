# Phase 11 — Licence Evidence, Terms Snapshot & Dataset Verification

Status: **implemented**. This document records the final architecture as built,
superseding the earlier planning assumptions in
`phase11_licence_evidence_verification_plan.md` where they diverged.

## Purpose

Phase 11 gives an Admin a governed workflow to verify a Phase 10 dataset
discovery candidate's identity, official source, dataset card, declared and
independently-assessed licence, terms of use, privacy/consent posture,
upstream sources, and per-use-case permission (RAG, training, evaluation,
commercial use) — producing an evidence-backed, human-reviewed verification
record.

Phase 11 **never**: downloads dataset files, imports records, activates RAG,
creates or starts training dataset versions/runs, releases a model, or
infers training/commercial permission from a licence name alone. Every
permission status that unlocks downstream use is admin-reviewed; the
system can only assess automatically into a bounded set of provisional
statuses (never directly into an approved/admin-only status).

## Data model (migrations 033, 034)

9 tables under `external_dataset_verification_*`:

- `external_dataset_verification_cases` — one case per active verification
  attempt against a Phase 10 candidate; carries lifecycle status, lock
  state, `declared_licence`/`normalized_licence_identifier` (migration 034),
  and reverification bookkeeping.
- `external_dataset_evidence_snapshots` — append-only, checksummed captures
  of fetched/uploaded evidence (dataset card, licence file, terms page,
  privacy page, etc.); delete-blocked but not update-blocked so
  `is_current` can be flipped when superseded.
- `external_dataset_evidence_links` — polymorphic link table connecting an
  evidence snapshot to the case-section it supports (identity check,
  licence assessment, permission assessment, upstream source, ...).
- `external_dataset_identity_checks` — per-dimension identity signal
  comparisons (name, homepage URL, organization, canonical dataset URL)
  against declared candidate values.
- `external_dataset_permission_assessments` — one row per (case,
  permission_type); automated assessment vs. admin review are structurally
  separated by DB triggers (see below).
- `external_dataset_verification_reviews` — admin decisions with reason
  text; append-only, update-blocked.
- `external_dataset_verification_events` — append-only, update-blocked
  audit trail of case-lifecycle events; conflict detection is folded in via
  `conflict_type`/`conflict_severity`/`resolution_status` columns rather
  than a separate table.
- `external_dataset_withdrawal_notices` — append-only, update-blocked
  record of upstream licence/availability withdrawal notices and their
  downstream impact status.
- `external_dataset_upstream_sources` — declared/derived upstream data
  sources for the candidate dataset, each independently reviewable.

### Trigger-enforced invariants

- 4 tables are delete-blocked (evidence snapshots, reviews, events,
  withdrawal notices); 3 of those are additionally update-blocked (reviews,
  events, withdrawal notices) — true append-only history.
- `ON DELETE CASCADE` on child foreign keys still fires the child's own
  `BEFORE DELETE` trigger, so a case with any evidence attached is
  structurally undeletable even via cascade — verified directly against
  SQLite in `tests/database/test_phase33_migration.py::test_case_with_evidence_can_never_be_deleted`.
- Two guard triggers on `permission_assessments` (INSERT and UPDATE) reject
  any write that sets an admin-only status (`approved`, `rejected`,
  `restricted`, `withdrawn` is system-triggered only) unless `reviewed_by`,
  `reviewed_at`, and a non-empty `reason` are present — this is the DB-level
  backstop for "no permission is ever granted without a human decision."

### Reverification without breaking immutability

A finalized (locked) case's report must stay immutable, but reverification
still needs to record new evidence and flag drift. Three narrowly-scoped
exceptions exist, each incapable of upgrading a status to an admin-only one:

- `add_evidence_snapshot(..., allow_locked_case=True)`
- `update_case_reverification_fields()` — whitelist of exactly 3 columns
  (`verification_expiry_status`, `last_verified_at`, `next_reverification_at`)
- `demote_permission_status()` — can only move a permission status *down*
  (e.g. `approved` → `reverification_required`), never up

## Evidence hierarchy & normalization

- `EVIDENCE_TYPES` (15) span dataset cards, licence files, terms/privacy
  pages, upstream declarations, and manual admin uploads.
- `EVIDENCE_AUTHORITY_LEVELS` (6) rank evidence trustworthiness (e.g. an
  official licence file outranks a third-party mirror's README); conflict
  detection and licence assessment prefer higher-authority evidence when
  sources disagree.
- Licence normalization matches **only** exact SPDX identifiers found in
  evidence text (`SPDX_EXACT_MATCHES` / `normalize_spdx_identifier()`); no
  fuzzy or semantic licence-name inference is performed anywhere in the
  pipeline.

## Permission assessment (16 dimensions)

`PERMISSION_TYPES` covers RAG use, training use, evaluation use, commercial
use (5 sub-categories), redistribution, modification, derivative works,
attribution requirements, and related dimensions.

Statuses are partitioned three ways and enforced both in application code
and by the DB triggers above:

- `AUTOMATED_PERMISSION_STATUSES` (5, includes `not_applicable`) — the only
  statuses `ExternalDatasetPermissionAssessmentService.assess()` may write.
- `ADMIN_ONLY_PERMISSION_STATUSES` (4) — `approved`, `rejected`,
  `restricted`, and one more; only `.review()` (which requires
  `reviewed_by`/`reason`) may write these.
- `SYSTEM_TRIGGERED_PERMISSION_STATUSES` (1) — `withdrawn`, set only by the
  withdrawal-notice pipeline, never by direct admin or automated write.

Commercial-use permission is assessed independently of the general
permission sweep (`assess_commercial_use()`), keyed to
`COMMERCIAL_USE_INTENDED_CATEGORIES` (6), since commercial eligibility
depends on the admin's declared intended use, not just the licence text.

## Conflict detection & upstream review

Conflicts (e.g. declared licence vs. evidence-derived licence, identity
signal mismatches, upstream source rights disagreeing with the primary
source) are recorded as `external_dataset_verification_events` rows typed
via `CONFLICT_TYPES`/`CONFLICT_SEVERITIES`; `BLOCKING_CONFLICT_SEVERITIES`
prevent case finalization until resolved or explicitly acknowledged by an
admin. Upstream sources are independently tracked and reviewed
(`UPSTREAM_VERIFICATION_STATUSES`), and an unresolved upstream source blocks
finalization (`unresolved_upstream_exists()`).

## Verification report & governance signals

`ExternalDatasetVerificationReportService.finalize()` produces an immutable
report snapshot including a `governance_eligibility` field with 4 booleans
(`rag_use_eligible`, `training_use_eligible`, `evaluation_use_eligible`,
`commercial_use_eligible`) — each **only** true when the corresponding
permission has been admin-approved; automated assessment alone can never
flip any of these to true. Phase 12+ governance consumes this field
read-only; Phase 11 performs no governance actions itself.

## Safe evidence retrieval

`backend/services/dataset_verification_transport.py` provides the only
network path evidence collection uses: bounded response size
(`MAX_EVIDENCE_RESPONSE_BYTES=2_000_000`), bounded extracted text
(`MAX_EVIDENCE_CONTENT_CHARS=200_000`), no retries
(`MAX_RETRIES_PER_EVIDENCE_FETCH=0`), a 5s timeout, at most 1 redirect, and
domain allow-listing (`is_domain_allowed()`) with DNS-resolved
SSRF protection (`default_resolver()`) rejecting private/loopback/link-local
targets. No fetched content is ever executed, cloned, or written outside
the evidence-snapshot store.

## Integration points

- **Dataset Discovery**: `DatasetDiscoveryPage` can open a verification case
  for a candidate (propose-only; never auto-starts one).
- **Source & Rights Registry**: `ExternalDatasetSourceRightsIntegrationService`
  finds an existing `data_sources` row by exact URL/org match and, only for
  a *finalized* case, drafts a `link_dataset_verification_rights` Admin
  Assistant proposal — no direct write to `data_sources`/`source_rights`
  happens outside the normal propose → review → execute pipeline.
- **Governance**: read-only consumption of `governance_eligibility`; no
  Phase 11 code path writes governance state.
- **Admin Assistant**: 6 tools + 10 registered actions (9 native + the 1
  Source & Rights link action) across all 4 language modes, plus an 8-entry
  deterministic FAQ (`dataset_verification_help.py`).
- **Data Overview**: 7 new aggregate metrics
  (`DatasetVerificationRepository.overview_counts()`) and a new "Open
  dataset verification" action.

## Frontend

`DatasetVerificationPage.jsx` — an 11-tab workspace (Overview, Evidence,
Identity, Licence, Terms & Privacy, Permissions, Commercial Use, Upstream
Sources, Conflicts, Report, Withdrawal Notices) wired through ~31 new
`DV`-prefixed API wrapper functions in `services/api.js`.

## Known limitations

- Frontend `refreshSelected()` issues its ~10 GET requests sequentially
  rather than via `Promise.all`, so the UI visibly lags (~3-5s) after a
  mutating action on a slow connection. Confirmed via direct DB inspection
  that the backend is always correct and fast; this is a perf
  characteristic, not a correctness bug, and is deferred rather than fixed
  in this phase.
- A full, unfiltered `tests/backend/ tests/database/ tests/core_model/`
  regression run could not be completed end-to-end in this environment
  (background test runs of this size are killed with no output after
  roughly 10-23 minutes, independent of Phase 11's own changes). Regression
  confidence instead comes from: the full 238-test Phase 11-specific sweep,
  an earlier full `tests/backend/` run (673/673) from within the same work
  window, and a clean whole-repo `ruff check .`.
