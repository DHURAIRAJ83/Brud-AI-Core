# Phase 15 — Final Text/NLP Production Readiness

## 1. Architecture

Phase 15 is a governance layer over two existing subsystems that were
discovered, not built, in this phase: `ModelReleaseService` (release
candidate/manifest/eligibility/approval/rollback-plan mechanics) and
`ModelAssignmentService` (assignment/canary/activation/rollback mechanics —
its own docstring predates this conversation's phase numbering and reads
"Phase 15 model-assignment lifecycle", an unrelated internal numbering). The
model track is therefore a thin governance wrapper, exactly like Phase 14's
relationship to `PretrainingService`. The production RAG track had no
governed equivalent (`RagRetrievalService.activate_profile()` is a bare,
ungoverned status flip) and is genuinely new. See
`docs/production/phase15_text_nlp_production_readiness_plan.md` for the full
baseline-inspection reasoning written before any code.

## 2. The invariants this phase never crosses

- RAG Sandbox accepted ≠ Production RAG approved.
- Production RAG release candidate built ≠ Production RAG activated.
- Checkpoint accepted ≠ Model release approved.
- Model release approved ≠ Production model activated.
- Canary active ≠ Full rollout complete.
- Training success ≠ Production readiness.
- Deployment success ≠ Security verification complete.

Each is enforced structurally: separate tables for each decision, status
guards in every service method that require the *previous* gate's row to
carry the correct status before the *next* action is even attempted, and
`ProductionDeploymentReadinessService`/`ProductionReadinessReportService`
never treat the absence of a check as a pass — an unassessed subsystem
blocks `ready`, it does not default to it.

## 3. Schema (migration 038, schema version 37 → 38)

19 new, additive tables: `production_rag_promotion_requests`,
`production_rag_promotion_approvals` (immutable once approved except
transitioning to `expired`/`superseded`), `production_rag_release_candidates`,
`production_rag_validation_results` (append-only), `production_rag_activation_events`
(append-only), `production_model_release_requests`,
`production_model_release_approvals` (immutable once approved except
`expired`/`superseded`), `production_model_activation_events` (append-only),
`production_model_post_activation_checks` (append-only),
`production_rollback_plans`, `production_rollback_events` (append-only),
`production_artifact_security_checks` (append-only),
`production_backup_readiness_checks` (append-only),
`production_deployment_readiness_checks` (append-only),
`production_regression_runs`, `production_regression_results` (append-only),
`production_readiness_reports` (append-only, versioned via
`UNIQUE(report_version)`), `production_acceptance_reviews` (append-only),
`production_readiness_events` (append-only, generic catch-all for
system-wide/non-per-entity checks such as API-abuse readiness and secret
scans, which have no natural per-entity target).

## 4. Real bugs found and fixed during this build

1. **Missing evaluation-manifest linkage.** `ProductionModelReleaseRequestService.create_request()`
   accepted a `model_evaluation_run_public_id` field in its input dict but
   never threaded it into `ModelReleaseCandidateCreate`, silently dropping
   it. Caught when `assess_eligibility()` correctly blocked on
   `evaluation_manifest_missing` for a candidate that should have had
   evaluation evidence attached. Fixed by passing the field through.
2. **Missing `generate_model_card()` argument.** `ProductionModelReleaseValidationService`
   called `ModelReleaseService.generate_model_card(candidate_id, admin_id)`,
   missing the required `overrides: ModelCardOverrides` positional argument
   entirely (a `TypeError` waiting to happen the moment the validation path
   was actually exercised, not caught by import-time checks).
3. **Wrong `verify_manifest()` result key.** The validation service read
   `manifest_check.get("verified")`; the real key is `"matches"`. A
   validated-but-actually-checksum-mismatched candidate would have been
   silently marked `validated` instead of `validation_failed`.
4. **Constructor arity mismatches.** `InferenceRuntimeService.__init__`
   requires `(repository, release_repository, settings)`; three new
   services (`ProductionModelCanaryService`, `ProductionModelActivationService`,
   and this file's own tests) initially called it with only
   `(repository, settings)`, which would have raised `TypeError` on first
   real use, not on import.
5. **CHECK-constraint event-type mismatches.** `production_model_activation_events.event_type`
   and `production_rollback_events.event_type` are enum-constrained; the
   activation service's first draft used invented values
   (`"activation_started"`, `"executed_automatically"`) that do not appear
   in either CHECK list. Fixed to the schema's real vocabulary
   (`"pre_activation_snapshot"`, `"executed"`).
6. **`run_health_check()` result-status mismatch.** `overall_status` values
   (`healthy`/`degraded`/`unhealthy`) were written directly into
   `production_model_post_activation_checks.result_status`, whose CHECK
   constraint only allows `passed`/`passed_with_warning`/`failed`/
   `not_applicable`. Fixed with an explicit mapping.
7. **Inverted canary-threshold-bounds check.** `ProductionApiAbuseReadinessService`'s
   first draft asserted `0 < threshold <= 1` for the canary abuse
   thresholds; `inference_canary_max_role_leakage_rate`/
   `..._prompt_leakage_rate` default to `0.0` (zero tolerance — the
   *strictest*, most protective setting), which the strict-inequality check
   incorrectly flagged as unbounded/misconfigured. Fixed to `0 <= x <= 1`.
8. **Naive secret-field-name scan false-positived on this codebase's own
   domain vocabulary.** A first draft reused `SECRET_KEYS` (which includes
   `"token"`) to scan domain-model field names; in an NLP codebase, `token`
   overwhelmingly means *tokenizer output*, not an auth token, producing 31
   false positives (`maximum_tokens`, `tokenizer_version_public_id`, etc.).
   Fixed with a narrower, domain-appropriate marker set specific to that one
   scan (`secret`/`password`/`api_key`/`apikey`/`authorization`, no
   `"token"`).
9. **Missing approval expiry/staleness re-check at model activation time.**
   Found while writing this phase's own dedicated security tests (§9, not
   by an external report): the RAG activation path
   (`ProductionRagActivationService.activate()`) re-verifies the approval's
   `expires_at` and `target_fingerprint` immediately before activating,
   correctly rejecting a stale or expired approval. The model activation
   path (`ProductionModelActivationService.activate()`) did not — it only
   checked the release request's cached `status` field, which stays
   `"approved"` even if the underlying approval has since expired or the
   request's bound evidence (`target_assignment_keys`, candidate linkage)
   changed after approval was granted. Fixed by adding the identical
   expiry + fingerprint-recomputation re-check the RAG path already had,
   with two new dedicated regression tests
   (`test_model_activation_rejects_a_stale_approval_fingerprint`,
   `test_model_activation_rejects_an_expired_approval`) proving the fix.

## 5. Production RAG promotion, build, validation, and activation

`ProductionRagEligibilityService` (read-only) → `ProductionRagPromotionService`
(create/submit/request-approval/approve, own fingerprint distinct from the
Phase 13 report checksum) → `ProductionRagCandidateService.build_candidate()`
(real orchestration through the existing `RagIngestionService`: chunk set →
embedding run → vector index → keyword index, using the codebase's own
`deterministic_test_embedding` provider for a genuinely runnable, non-fabricated
end-to-end test path) → `ProductionRagValidationService` (structural checks
only — checksum/profile presence, never a live retrieval call, since
`RagRetrievalService.retrieve()` hard-requires an *already-active* profile,
which a not-yet-activated candidate can never satisfy) →
`ProductionRagActivationService.activate()` (snapshots the current active
profile → re-verifies approval status/expiry/fingerprint →
`RagRetrievalService.activate_profile()` → real post-activation retrieval
smoke checks → automatic rollback to the snapshotted previous profile on any
failure) → `.rollback()` (reactivates the previous profile; correctly raises
if no previous profile was ever snapshotted, i.e. this is the very first
activation in that knowledge space).

## 6. Model release request, validation, approval, canary, activation, and rollback

`ProductionModelReleaseEligibilityService` re-verifies the Phase 14
acceptance chain independently (defense in depth) →
`ProductionModelReleaseRequestService.create_request()` calls
`ModelReleaseService.create_candidate()` directly, binding the Phase 14
`model_candidate_public_id` straight through as `core_model_version_public_id`
→ `ProductionModelReleaseValidationService` composes
`collect_artifacts`/`verify_artifacts`/`generate_model_card`/
`validate_model_card`/`assess_eligibility`/`generate_manifest`/
`verify_manifest`, matching the exact order the existing `/model-releases`
API already uses → `ProductionModelReleaseApprovalService` (a Phase-15-scoped
approval, separate from `ModelReleaseService`'s own role-based
`submit_approval()` — both gates must be satisfied; neither substitutes for
the other) → `ProductionModelCanaryService` (thin wrapper around
`ModelAssignmentService.start_canary()`/`execute_canary()`/`stop_canary()`)
→ `ProductionModelActivationService.activate()` (requires an
already-`verified` `production_rollback_plans` row, re-verifies the
approval's expiry/fingerprint — see bug #9 — calls
`ModelAssignmentService.activate_assignment()`, runs a real
`InferenceRuntimeService.run_health_check()`, and automatically rolls back
via `ModelAssignmentService.rollback_execute()` on a failed health check) →
`.rollback()` (explicit, admin-initiated rollback to the plan's bound
target version).

Both activation services deliberately accept an **already-existing**,
already-approved `assignment_public_id` / `embedding_model_public_id` rather
than creating one — the same "reuse a real prerequisite, never rebuild it"
pattern, avoiding any re-implementation of `ModelAssignmentService`'s own
approval logic.

## 7. Artifact security, API-abuse readiness, and secret scanning

`ProductionArtifactSecurityService` independently re-verifies (confinement,
unexpected-executable presence, checksum recomputation) every artifact
`ModelReleaseService.collect_artifacts()` already collected for a candidate,
plus a dedicated backup-file check and a RAG-candidate checksum-presence
check — a genuine second opinion, never trusting the original
`verification_status` alone. `ProductionApiAbuseReadinessService` inspects
real Pydantic field constraints (`model_json_schema()["properties"][...]["maxLength"]`)
on the chat/RAG-session/diagnostic request models, real `Settings` values
(CSRF configuration, canary abuse thresholds), and statically scans every
route file for a download-shaped endpoint referencing checkpoint/tokenizer/
RAG-payload internals — a real defense-in-depth check, not a documentation
claim. `ProductionSecretScanService` functionally re-verifies the existing
`redact_secrets()` mechanism still redacts, scans the built admin-dashboard
bundle (when one exists) for secret-shaped value patterns, and scans domain
model field names for secret-shaped names (see bug #8).

## 8. Backup, restore, deployment readiness, system health, and regression

`ProductionBackupReadinessService`/`ProductionRestoreReadinessService` reuse
`backend/api/routes/system.py`'s own `_latest_backup()` glob convention;
the restore check copies the latest backup into an isolated
`tempfile.TemporaryDirectory()`, opens the copy with a **separate**
`sqlite3`/`database_connection()` call, and runs `PRAGMA integrity_check`
plus a `migration_status()` spot-check — the live database is never opened
for write. `ProductionDeploymentReadinessService.assess()` only ever reads
back what Steps 17–21's own services already recorded; an unassessed
subsystem is `blocking`, not silently passing.
`ProductionRegressionService` runs bounded, admin-supplied pytest batches as
real `subprocess.run(..., timeout=...)` invocations (never a whole-repo
`pytest tests/`, which this same session's Phase 14 segment twice observed
being killed by this sandboxed environment with zero output) and records a
batch that could not complete within its timeout as
`status='environment_incomplete'`, structurally distinct from a genuine
`'failed'` test result.

## 9. Final readiness report and acceptance review

`ProductionReadinessReportService.compile_report()` composes a fresh
`ProductionDeploymentReadinessService.assess()` plus the latest regression
run's results into one versioned, checksummed, immutable
`production_readiness_reports` row (`recommendation` derived from real
deployment/regression state, never hand-set); `ProductionAcceptanceReviewService.submit_review()`
binds to the **latest** report only (rejecting review of a superseded
report with a clear error) and computes a `target_fingerprint` from the
report's own checksum plus whatever model/RAG state is currently active —
the explicit final Admin decision this whole phase exists to produce.

## 10. Admin Assistant integration

8 new controlled actions, deliberately scoped to proposal/submission and
read-verify-only safety checks — there is no action anywhere in this phase
for approving a promotion or release, building or validating a RAG
candidate, starting a canary, activating or rolling back anything, or
submitting the final production-acceptance review:
`create_production_rag_promotion_request`,
`submit_production_rag_promotion_request`,
`create_production_model_release_request`,
`submit_production_model_release_request`,
`check_production_release_candidate_artifact_security`,
`run_production_api_abuse_readiness_check`,
`run_production_secret_redaction_check`,
`compile_production_readiness_report`. Each is wired through the existing
propose → preview → confirm-with-stale-check → execute → verify → audit
pipeline (`ACTION_EXECUTORS`, `STALE_CHECK_FINGERPRINTS`,
`PREVIEW_GENERATORS`), reusing the RAG-sandbox-experiment fingerprint
function directly where the target type already matches, and a documented
no-op fingerprint for the three system-wide (non-per-entity) safety checks.

## 11. API surface

62 routes under `/api/admin/production-readiness`, admin-only,
CSRF-protected, organized by concern (`/rag/...`, `/model/...`,
`/rollback-plans/...`, `/artifact-security/...`, `/api-abuse-readiness/...`,
`/secret-scan/...`, `/backup-readiness/...`, `/restore-readiness/...`,
`/deployment-readiness/...`, `/system-health`, `/regression/...`,
`/readiness-reports/...`). No route accepts or returns a raw model
checkpoint, tokenizer, dataset file, or RAG payload — every response is a
governance/status JSON object.

## 12. Frontend

`ProductionReadinessPage.jsx`, a 10-tab page (Overview, RAG Promotion, RAG
Candidates, Model Release, Canary & Activation, Artifact Security, API
Abuse & Secrets, Backup & Deployment, Regression, Readiness Report &
Acceptance) wired into `App.jsx`/`Sidebar.jsx` under a new top-level
"Production Readiness" nav entry, and ~65 new `services/api.js` functions.
Building this surfaced four real `api.js` export-name collisions with
pre-existing, unrelated exports (`rollbackPlan`/`validateRollbackPlan` from
the Model Registry page's own rollback-plan feature;
`createRegressionRun`/`regressionRun`/`regressionResults` from the Feedback
page's own, unrelated "regression suite" feature; a local `const PR`
constant colliding with Pretraining Readiness's own `const PR`) — all
caught by a real `vite build`, not by unit tests alone, and fixed by
renaming to `production*`/`PRR`-prefixed names.

## 13. Tests (comprehensive list)

- `tests/database/test_production_readiness_repository.py` — 15 tests
- `tests/backend/test_production_rag_eligibility_and_promotion.py` — 7 tests
- `tests/backend/test_production_rag_validation_activation_rollback.py` — 4 tests
- `tests/backend/test_production_model_release_request.py` — 5 tests
- `tests/backend/test_production_model_release_validation_activation.py` — 8 tests
- `tests/backend/test_production_artifact_security_and_readiness.py` — 8 tests
- `tests/backend/test_production_backup_restore_and_deployment_readiness.py` — 9 tests
- `tests/backend/test_production_regression_and_readiness_report.py` — 13 tests
- `tests/backend/test_production_readiness_api.py` — 10 tests
- `tests/backend/test_production_readiness_admin_assistant.py` — 6 tests
- `tests/backend/test_production_readiness_security.py` — 7 tests
- `apps/admin-dashboard/src/pages/ProductionReadinessPage.test.jsx` — 8 tests

92 backend/database tests plus 8 frontend tests, all independently verified
passing (this sandboxed environment does not reliably tolerate one single
combined multi-hundred-test invocation — the same constraint documented in
Phase 14 §8/§21 — so verification was performed in the same targeted,
per-file batches used throughout this phase, with cross-batch consistency
confirmed by re-running the full repository/model-activation/admin-assistant/API
suites together in three smaller groups). Full admin-dashboard suite: 147
tests passing across all 16 frontend test files (unchanged pre-existing
tests plus this phase's new file), and a clean production `vite build`.
`ruff check` passes clean on every new/modified Python file.

## 14. Manual verification

No browser automation tool was available in this session (same constraint
as Phase 14 §23). Verified instead against the real running backend
(`scripts/run_backend.sh`, port 8000) and frontend (`vite`, port 5174)
against the project's real development database
(`data/database/brud_ai.db`), which was thereby genuinely, permanently
migrated from schema version 37 to 38 as part of this verification —
created a real admin account (`phase15-verifier`), logged in over real
HTTP, confirmed an unauthenticated `GET /api/admin/production-readiness/overview`
is rejected with `401`, confirmed an authenticated `POST` without a CSRF
header is rejected with `403`, confirmed the authenticated overview
endpoint returns real (non-fabricated) zero-state data on a fresh
migration, and confirmed a real `POST .../api-abuse-readiness/assess` call
runs the actual static scan against the actual live codebase and returns
`"result_status":"passed"` with all six real checks true. Confirmed
`ProductionReadinessPage.jsx` and the frontend index both serve cleanly
(HTTP 200) through Vite's dev transform. Both dev servers were stopped
after verification.

## 15. Known limitations

- Training/evaluation datasets remain small-scale relative to production
  LLM norms; the final readiness report's `recommendation` field reflects
  the scale of data genuinely available in this project, not an
  aspirational production scale.
- The RAG track's real end-to-end test path uses the codebase's own
  `deterministic_test_embedding` provider; a real embedding-model swap
  should be re-validated (a fresh `ProductionRagValidationService.run_validation()`
  call) before any production RAG activation that uses a different
  provider.
- Canary result sample sizes are small by construction (bounded
  fixture-prompt counts); canary metrics should be read as directional
  signal, not a statistically final verdict.
- API-abuse readiness is a static/configuration assessment (bounded request
  fields, CSRF configuration, canary thresholds, download-endpoint
  scanning), not a live load test or penetration test.
- No real external backup-encryption mechanism is configured in this
  environment; artifact security honestly reports backup encryption as
  unassessed rather than fabricating a pass.
- `ProductionRegressionService` batches are admin-supplied; this phase does
  not itself define or ship a canonical "full Phase 15 regression batch
  plan" beyond what its own test suite already exercises per-file.
- Inherited from Phase 14: training/evaluation datasets remain small-scale;
  Phase 13's contamination/citation-conflict signals remain advisory
  context only, never a training- or production-eligibility decision on
  their own.

## Out of scope (explicitly, not attempted)

Image/Audio/Video/Multimodal (any code, tables, services, routes, or
frontend pages), billing/subscriptions/public pricing, any new external
model/embedding/GPU/cloud provider, automatic cloud deployment, an A/B
experimentation platform, advanced SOC/SIEM tooling, public model/checkpoint/
dataset-file download endpoints, customer-side/desktop/mobile model
packaging, full legal certification.

---

**PHASE_15_COMPLETE_WITH_LIMITATIONS**

Limitations: no browser-automation tool was available for true
click-through UI verification (HTTP-level and frontend-unit-test
verification were used instead, per §14); regression batches are
admin-supplied rather than a shipped canonical Phase 15 batch plan (§15);
backup encryption-at-rest is honestly reported as unassessed rather than
verified, since no such mechanism is configured in this environment (§15).

Do not proceed to Image, Audio, Video, Multimodal, billing, or unrelated
enhancements.
