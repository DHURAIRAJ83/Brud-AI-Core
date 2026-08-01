# Phase 11 Plan — Licence Evidence, Terms Snapshot & Dataset Verification

Written before implementation, per this phase's Step 1.

## 1. Systems reused (confirmed by direct inspection)

- **Phase 10 dataset discovery**: `external_dataset_candidates` (+
  `external_dataset_candidate_sources` raw evidence,
  `external_dataset_candidate_scores`) is the *input* to this phase --
  a verification case always links to exactly one existing candidate
  row, never copies or duplicates it. `ExternalDatasetDiscoveryRepository`
  is read from (candidate lookup, provider lookup via
  `primary_provider_public_id`) but never written to for permission
  fields -- the candidate's own `commercial_use_status`/
  `training_use_status`/`rag_use_status`/`evaluation_use_status`
  columns stay structurally `not_approved`/`unknown` forever (Phase
  10's own CHECK constraints already make `'approved'` impossible
  there), untouched by this phase.
- **Phase 9 provider registry**: `ExternalDataProviderRepository` (domains,
  trust_status) is the source of the "registered provider domain"
  allowlist for evidence retrieval -- reused, not duplicated.
- **Source & Rights Registry** (`data_sources`/`source_rights`,
  Data Studio Phase 2): its `source_rights` table already has almost
  the exact boolean shape Phase 11's own permission dimensions need
  (`rag_use_allowed`, `training_use_allowed`, `commercial_use_allowed`,
  `redistribution_allowed`, `attribution_required`,
  `share_alike_required`, `modification_allowed`) -- confirming this
  is the right *target* shape for eventual linking, but that table
  governs content *already inside* Brud AI. Phase 11's own new tables
  are for *pre-import, external* candidates; only a *finalized*
  verification case may later *propose* (through the existing
  Admin Assistant pipeline, never directly) linking/creating a
  `data_sources`/`source_rights` row -- this phase never writes to
  those tables itself (see section 14).
- **Governance** (`GovernanceApprovalService`, `GOVERNANCE_TARGET_USES`):
  read-only awareness only. Phase 11 computes its own eligibility
  signals (`rag_use_eligible`, etc.) on the verification report; it
  never calls into `GovernanceApprovalService` or writes governance
  tables -- that integration is explicit Phase 12+ territory per the
  task's own rule.
- **Text extraction** (`core_model/corpus/text_extraction.py`):
  `content_checksum()` (SHA-256) and `extract_html_snapshot_text()`
  (script/style/tag stripping, entity decoding, whitespace collapse)
  are reused **unchanged** for every evidence snapshot -- exactly the
  "safe text, no active rendering" + "checksum every snapshot"
  requirements, already deterministic and dependency-free.
- **PDF extraction**: `CorpusProcessingService._extract_pdf_embedded`'s
  pattern (optional `fitz` import, `needs_pass`/`is_encrypted` rejection,
  per-page `get_text("text")` join) is *mirrored* (not imported --
  it is a private method, not a shared utility) for the one supported
  evidence content type (`application/pdf`) that needs it.
- **Redaction/JSON bounds**: `backend.core.json_utils.redact_secrets()`/
  `dumps_json(..., max_bytes=...)` reused unchanged for
  `metadata_json`/`response_headers_json` and for bounding snapshot
  text length.
- **Connector/transport pattern** (Phase 9/10):
  `HttpTransport`/`default_http_transport`/`ConnectorConfig` shape
  reused as the base for a new, Phase-11-specific bounded transport
  that adds what Phase 9/10 never needed: real DNS/IP SSRF validation
  (an "official upstream domain" is admin-*registered* per case, not
  always one of Phase 9's pre-vetted provider domains, so resolving
  and checking the actual IP before connecting is new, necessary work).
- **Admin Assistant pipeline** (Phase 8/10A):
  `AdminAssistantService.propose/review/execute`,
  `ACTION_DEFINITIONS`/`ACTION_EXECUTORS`, `admin_assistant_tools.py`'s
  `READ_ONLY_TOOLS`, `admin_assistant_chat_service.py`'s deterministic
  reply + localization pipeline -- extended with new tools/actions,
  never re-implemented.
- **Migration conventions**: `SCHEMA_VERSION`/`MIGRATION_0NN_NAME`/
  `PHASENN_SCHEMA` + `_apply_vNN` in `migrations.py`, delete-blocked/
  append-only triggers exactly like Phase 10's `external_dataset_*`
  tables.

## 2. Schema design (migration 033, schema 32 -> 33)

9 new, additive tables: Step 3's exact list of 8
(`external_dataset_verification_cases`, `_evidence_snapshots`,
`_evidence_links`, `_identity_checks`, `_permission_assessments`,
`_verification_reviews`, `_verification_events`,
`_withdrawal_notices`) plus one documented deviation --
`external_dataset_upstream_sources` -- added because Step 10's own
field list (`upstream_name, upstream_url, upstream_organization,
upstream_licence, upstream_terms, upstream_permission_status,
relationship_type, coverage_notes, verification_status`) does not fit
any of the other 8 named tables, and Step 3 itself calls its list
"recommended," not exhaustive. `external_dataset_evidence_links` is
used for its more literal, general purpose instead: a polymorphic
link (`evidence_snapshot_id`, `linked_entity_type`, `linked_entity_id`,
`link_role`) connecting one evidence snapshot to whichever permission
assessment/identity check/upstream source/licence determination/
conflict event it supports, rather than a dedicated join table per
relationship. Conflicts (Step 12) are likewise not a 10th table --
folded into `external_dataset_verification_events` as
`event_type='conflict_detected'` rows with three dedicated extra
columns (`conflict_type`, `conflict_severity`, `resolution_status`)
on that same event row, since Step 3's table list has no separate
conflicts table.

Every mutable table (`external_dataset_verification_cases`,
`_identity_checks`, `_permission_assessments`, `_upstream_sources`)
may only be updated while `locked_at IS NULL` (case row); the 4
append-only tables named in Step 3 (`_evidence_snapshots`,
`_verification_reviews`, `_verification_events`,
`_withdrawal_notices`) get delete-blocked triggers, and reviews/events/
withdrawal-notices additionally get update-blocked triggers (mirrors
Phase 10's `external_dataset_search_events` append-only pattern
exactly) -- `_evidence_snapshots` deliberately stays update-*allowed*
(only delete-blocked) so `is_current`/`supersedes_evidence_id` can be
flipped when a newer snapshot supersedes an older one, without ever
destroying the original captured text. `external_dataset_permission_
assessments.status` gets a CHECK constraint listing all 10 allowed
values (structural allowlist); the automated-vs-admin-only split
(Step 8) is enforced in the *service* layer (only
`ExternalDatasetPermissionAssessmentService.review()` -- never
`.assess()` -- may pass one of the 4 admin-only values to the
repository), reinforced by a dedicated trigger (fires on both INSERT
and UPDATE) that rejects any row transitioning into an admin-only
status without a non-null `reviewed_by`/`reviewed_at` pair *and* a
non-empty `reason` set in the same statement -- verified directly
against SQLite in `tests/database/test_phase33_migration.py` (17
tests: fresh DB, upgrade-from-32 preserving prior data, CHECK
constraints, the admin-only guard trigger on both insert and update,
append-only enforcement on all 4 designated tables, evidence-snapshot
update-but-never-delete, FK/uniqueness constraints, and the discovery
that a case with any collected evidence can never itself be deleted --
because the implicit `ON DELETE CASCADE` to `_evidence_snapshots`
still fires that table's own delete-blocking trigger, so cases are
only ever cancelled/expired/withdrawn via status, never row-deleted).

## 3. Evidence hierarchy (Step 2)

`core_model/data_verification/__init__.py` defines, as pure tuples
(never inferred at runtime from string content):

- `EVIDENCE_TYPES` (15, Step 2's list).
- `EVIDENCE_AUTHORITY_LEVELS` (6, Step 2's list) with a fixed
  `AUTHORITY_PRECEDENCE` ordering (`primary` highest ->
  `manual_unverified` lowest) as an explicit tuple, never a heuristic.
- `EVIDENCE_TYPE_DEFAULT_AUTHORITY` maps each evidence type to its
  *typical* authority level (e.g. `licence_file` ->
  `primary`, `dataset_card` -> `official_supporting`, `repository_licence_metadata`
  -> `secondary`, `manual_admin_evidence` -> `manual_unverified`) --
  a starting default an admin/service may override per snapshot when
  the specific evidence genuinely warrants a different level (e.g. a
  `licence_url` pointing at the dataset's own dedicated licence page
  is `primary`, not merely `official_supporting`), never silently
  auto-escalated.
- `higher_or_equal_authority(a, b) -> bool` -- the one pure function
  every conflict-resolution and licence-status decision consults so
  "lower-authority evidence never silently overrides higher-authority
  evidence" is enforced by one tested function, not ad hoc comparisons
  scattered across services.

## 4. Identity, licence, permission, conflict, expiry enums (Step 4/6/7/8/12/14/15)

All pure tuples in `core_model/data_verification/__init__.py`:
`VERIFICATION_CASE_STATUSES` (12), `IDENTITY_STATUSES` (5),
`LICENCE_STATUSES` (9), `PERMISSION_TYPES` (16, Step 8's exact list),
`PERMISSION_STATUSES` (10) split into
`AUTOMATED_PERMISSION_STATUSES` (4) and
`ADMIN_ONLY_PERMISSION_STATUSES` (4, the structural gate), plus
`is_admin_only_permission_status()`; `CONFLICT_SEVERITIES` (5),
`REVERIFICATION_STATUSES` (5), `WITHDRAWAL_NOTICE_TYPES` (7),
`UPSTREAM_RELATIONSHIP_TYPES` (7).

## 5. Verification case lifecycle (Step 4/20)

`draft -> collecting_evidence -> needs_review -> in_review ->
(verified | verified_with_conditions | insufficient_evidence |
conflicting_evidence | blocked) | cancelled | expired | withdrawn`.
`ExternalDatasetVerificationService` owns transitions; every
transition is an `external_dataset_verification_events` row (mirrors
Phase 10's search-session-event pattern). `locked_at` is set exactly
once, at `finalize()`, after which the case, its identity checks, and
its permission assessments become immutable (checked the same way
Phase 10's schema checks `excluded`/terminal states -- a service-level
guard, since SQLite triggers keyed on "is this the finalize
transaction" are impractical; the repository refuses any further
`update_case`/`update_permission_assessment` call once
`locked_at IS NOT NULL`).

## 6. Evidence snapshot model + safe retrieval (Step 5/11/17)

`ExternalDatasetEvidenceService` collects one snapshot per
`(evidence_type, source_url)` via a new bounded transport
(`backend/services/dataset_verification_transport.py`):
domain must be either one of the candidate's own provider's Phase 9
registered domains, *or* an admin-registered "official upstream
domain" for this case (stored on the case/upstream row, validated by
format + a live DNS resolution + private/loopback/link-local/
multicast IP rejection via `ipaddress`/`socket.getaddrinfo` before
connecting) -- an arbitrary admin-pasted URL is otherwise rejected
before any network call. HTTPS preferred (HTTP allowed only if the
registered domain explicitly has no HTTPS record, logged as a
warning); redirects are followed at most once and the *final* URL is
re-validated against the same allowlist (never trusted blindly);
response bounded to `MAX_EVIDENCE_RESPONSE_BYTES`; only
`text/plain`/`text/markdown`/`text/html`/`application/json`/
`application/pdf` accepted; HTML through
`extract_html_snapshot_text()`; PDF through the mirrored embedded-text
extractor (OCR never attempted automatically -- Step 5's rule; a
manual, explicitly-flagged `ocr_derived=true` path exists only for
`add_manual_evidence()`, always `retrieval_status="manual"`, always
requiring a human-supplied text alternative reviewed before being
trusted). Every snapshot gets `content_checksum()`, `redact_secrets()`
over `metadata_json`, and `is_current`/`supersedes_evidence_id` for
revision tracking.

## 7. Identity verification (Step 6)

`ExternalDatasetIdentityVerificationService` checks the conservative
signal list (Step 6) against the linked Phase 10 candidate's own
fields (`provider_dataset_id` via `candidate_sources`, `organization`,
`repository_url`/`homepage_url` domain, `canonical_name`, `version`/
`revision`) plus any collected evidence's `source_domain`/
`source_title`. Each signal is stored as its own row
(`external_dataset_identity_checks`) with `matched`/`reason` --
title-only similarity is explicitly never sufficient for `verified`
(a dedicated test enforces this): `verified` requires at least one of
{exact provider ID, exact official-domain match} plus no conflicting
signal; anything weaker caps at `likely_match`/`partial`.

## 8. Licence normalization (Step 7)

`ExternalDatasetLicenceService` stores `declared_licence` (verbatim,
never altered) alongside `normalized_licence_identifier` -- populated
*only* from a small, explicit, hand-maintained SPDX exact-match table
(e.g. `"cc-by-4.0"`/`"CC BY 4.0"` -> `"CC-BY-4.0"`, `"apache-2.0"` ->
`"Apache-2.0"`) checked case/whitespace-insensitively against the
declared string -- never inferred, never guessed, never partial-matched.
No match leaves `normalized_licence_identifier = NULL` and
`licence_status` reflects why (`custom_needs_review` if evidence shows
a genuinely custom licence text was captured, `missing` if no licence
evidence exists at all, `conflicting` if two evidence snapshots at the
same or higher authority disagree).

## 9. Permission assessment model (Step 8/9)

`ExternalDatasetPermissionAssessmentService.assess()` (automated,
read-only over already-collected evidence + identity + licence state)
computes a `decision_basis` explanation and defaults every one of the
16 dimensions to one of the 4 automated-only statuses -- it can
*never* write `approved`/`approved_with_conditions`/`not_approved`/
`prohibited` (enforced by a dedicated `_ADMIN_ONLY_STATUSES` guard
inside the one repository write path, raising `ValidationError` if an
automated caller ever attempts it, plus the DB trigger from section 2
as defense in depth). `.review()` is the *only* method that may set an
admin-only status, and it requires `reviewed_by`/a non-empty `reason`
(`requires_reason` mirrors Phase 8/10A's own convention on
proposal-lifecycle actions) and always writes an
`external_dataset_verification_reviews` row (append-only, evidence
checksum set captured at review time for stale-detection).
`commercial_use` is never inferred from any other permission's value
(Step 9); the service asks/records the intended-use category
(internal_testing/research/free_public_service/paid_commercial_product/
redistributed_dataset/commercial_training_deployment) as an explicit
field on the assessment's `conditions_json`, defaulting
`commercial_use` to `needs_legal_review` whenever evidence is
non-conclusive rather than ever defaulting to an allowed state.

## 10. Upstream-source review (Step 10)

`ExternalDatasetUpstreamReviewService` -- one row per upstream source
a dataset aggregates from, `verification_status` independent of the
main case's identity status. `training_use`/`commercial_use`
assessment for the *main* dataset is capped at
`needs_legal_review` (never `likely_allowed`, let alone an admin
`approved`) while any linked upstream row has
`verification_status != "verified"` -- enforced in
`ExternalDatasetPermissionAssessmentService.assess()` by checking
`ExternalDatasetUpstreamReviewService.unresolved_upstream_exists()`
first.

## 11. Conflict detection (Step 12)

`ExternalDatasetConflictService.detect()` runs a fixed set of
deterministic pairwise comparisons across already-collected evidence
snapshots (declared licence vs. licence-file text keyword extraction,
provider-declared vs. repository-licence-file presence, dataset-card
permissive language vs. terms-of-use restrictive language via a
bounded keyword-signal check -- never semantic NLP) and upstream
rows, storing one `external_dataset_conflicts`-shaped row per
detected conflict (folded into `external_dataset_verification_events`
with `event_type="conflict_detected"` plus a dedicated
`conflict_severity`/`resolution_status` pair of columns on that same
event row, avoiding a 9th table for what is otherwise a specialized
event) with a `resolve()` method requiring a human reason; a `blocking`
severity, unresolved, prevents `finalize()`.

## 12. Verification report (Step 13/20)

`ExternalDatasetVerificationReportService.finalize()` is the one
place `locked_at` is set. It requires: no unresolved `blocking`
conflict, and (stale-state protection, Step 20) that every evidence
snapshot referenced by any admin-reviewed permission assessment still
has the same checksum it had at review time -- otherwise raises the
same "stale, re-review required" rejection Phase 8's proposal
`stale_check_json` pattern already established, never silently
finalizing over changed evidence. The finalized report snapshot is
stored as `report_json` on the case row (immutable once `locked_at`
is set) with every field explicitly tagged
`"verified_fact"`/`"provider_declared"`/`"assistant_inference"`/
`"admin_decision"`/`"unknown"` (Step 13's own requirement) so the
frontend/Assistant never conflates them.

## 13. Reverification & withdrawal (Step 14/15)

`ExternalDatasetReverificationService.check()` is lazy (read-time or
explicit refresh only -- no scheduler, per the task's explicit
exclusion): recomputes each referenced evidence snapshot's *live*
checksum only when explicitly asked (`POST .../reverify`), comparing
against the stored one; a mismatch flips `verification_expiry_status`
to `source_changed` and demotes every admin-approved permission back
to `needs_legal_review` (never silently keeps trusting it).
`ExternalDatasetWithdrawalService.record_notice()` appends an
append-only row and computes the required impact summary (Step 15)
purely from already-known state (existing lineage lookup reused from
Phase 10's own `search_session`/candidate linkage, never a new lineage
system).

## 14. Source & Rights / Governance integration (Step 23/24)

A finalized case's report may be used to *draft* (never silently
create) a `dataset_source_update`-shaped Admin Assistant proposal
(reusing the existing `register`-style action pattern) that an admin
must separately review/approve/execute through the *existing*
`data_sources`/`source_rights` write paths (`DatasetService`/
`DatasetAdminRepository`, completely untouched) -- Phase 11 itself
never writes those tables. Before drafting, the service checks for an
existing `data_sources` row with a matching `source_url`/
`organization_name` to avoid a duplicate proposal. Governance
integration is limited to 4 read-only, derived boolean fields on the
finalized report (`rag_use_eligible` etc., `True` only when the
matching permission status is `approved`/`approved_with_conditions`
*and* no unresolved blocking conflict exists) -- never a write to any
governance table, never a trigger for any downstream action.

## 15. Security controls (Step 17/26)

Every control from Step 17, implemented in
`backend/services/dataset_verification_transport.py`: domain
allowlist (Phase 9 registered + explicitly admin-registered upstream
domains only), HTTPS preference, single-hop redirect re-validation,
DNS resolution + `ipaddress.ip_address(...).is_private/is_loopback/
is_link_local/is_multicast/is_reserved` rejection before connecting,
5s timeout, `MAX_EVIDENCE_RESPONSE_BYTES` cap, MIME allowlist, zero
automatic retries (matches Phase 9/10's `MAX_RETRIES_PER_PROVIDER=0`
precedent), a fixed identifying User-Agent string, redaction,
checksum. Nothing here ever executes retrieved content: no `eval`,
`exec`, `subprocess`, template rendering, or archive extraction exists
in this module (a structural regex-scan test mirrors Phase 10's own
`test_no_dynamic_execution_or_shell_primitives_in_discovery_modules`).

## 16. Testing plan

Mirrors Phase 10's structure: migration tests (fresh/upgrade/CHECK/
append-only/FK), core_model policy tests (evidence hierarchy
precedence, enum admin-only split), service-layer tests per
service (identity/licence/permission/conflict/upstream/reverification/
withdrawal), a dedicated security test file (SSRF/redirect/oversized/
MIME/HTML-stripping/no-execution), API tests (auth/CSRF/pagination/
stale-state), Admin Assistant integration tests (tools + actions +
end-to-end propose/review/execute + the 4 language modes), frontend
component tests, and a manual Playwright pass (Flows A-G).

## 17. Phase 12 handoff

Explicitly deferred, per the task's own list: sample import,
quarantine, archive extraction, malware/PII scanning, RAG indexing/
sandbox, training dataset creation/run, model release, a background
reverification scheduler, legal advice, any form of automatic
licence/commercial approval, a secrets vault, browser login
automation. A future phase should: (a) use this phase's
`rag_use_eligible`/`training_use_eligible`/etc. signals as one
*input* to a real governance-gated import decision, never as the
decision itself; (b) implement the deferred `source_url` proposal
hand-off into a real, reviewed `data_sources` row per verified
candidate.

**Do not proceed to Phase 12 in this session.**
