# Phase 15 — Final Text/NLP Production Readiness: Plan

Written before any Phase 15 code, per Step 1. All baseline inspection below
was done by direct source reading (`Read`/`Bash`/`grep`), not by spawning a
research subagent, matching the approach used for Phase 14.

## 0. The single most important discovery

The request's baseline claims "Production model activation... have not been
implemented by Phases 8–14." **That is not accurate relative to the actual
repository state.** Direct inspection found two large, already-complete
systems:

- `backend/services/model_release_service.py::ModelReleaseService` already
  implements the *entire* release-candidate pipeline: `create_candidate`,
  `collect_artifacts`, `verify_artifacts`, `assess_eligibility`,
  `generate_model_card`, `generate_manifest`/`verify_manifest`,
  `submit_approval`, `create_release`, `deprecate_release`/`retire_release`,
  `compare_releases`, `build_bundle`/`verify_bundle`, and —
  critically — `create_rollback_plan`/`validate_rollback_plan`/
  `approve_rollback_plan`/`execute_rollback_plan`. `create_release()` sets
  `model_releases.status='released'` (meaning *deployable*, not *deployed*)
  and never touches `core_model_versions.lifecycle_status` or
  `inference_model_assignments` — release and activation are already two
  separate concerns in this codebase.
- `backend/services/model_assignment_service.py::ModelAssignmentService`
  (its own docstring literally reads *"Phase 15 model-assignment
  lifecycle"* — this repository has its own, older internal phase
  numbering, unrelated to this conversation's Phase 12/13/14 arc) already
  implements `create_assignment`/`validate_assignment`/`approve_assignment`/
  `activate_assignment`, `start_canary`/`execute_canary`/`stop_canary`/
  `canary_results`, `rollback_preview`/`rollback_execute`, and a chat-lab
  diagnostic session flow. `core_model.inference_runtime.assignment_policy.
  assess_public_activation_gate()` is a deterministic, non-overridable,
  ~20-dimension gate (evaluation status, safety issues, prompt/role-leakage
  rates, human-review coverage, approval-role satisfaction, runtime
  compatibility/health, admin-diagnostics success, canary success +
  thresholds, rollback-target availability, fallback-policy presence,
  explicit confirmation) — its own docstring says *"must not fabricate a
  passing release merely to test public activation... a missing measurement
  fails the gate, it never passes it."* This already **is** the "production
  model activation" system the request assumes doesn't exist.

**Consequence for scope**: this phase's model-release/model-activation work
is a *thin governance wrapper* around these two existing services — the
same pattern Phase 14 used for `PretrainingService`/`InstructionTuningService`
— never a reimplementation. What Phase 15 adds on the model side is
specifically the *handoff* from a Phase 14 accepted checkpoint
(`core_model_versions.lifecycle_status='staging'`) into
`ModelReleaseService.create_candidate()`, plus its own binding/audit table
so "Model release approval must not imply RAG activation" (trivially true —
disjoint tables/services) and so the final readiness report has one place to
read a consistent Phase-15-scoped view from.

The **production RAG side has no equivalent existing governance**:
`backend/services/rag_retrieval_service.py::RagRetrievalService.
activate_profile()` is a bare, ungoverned, single-click `status='active'`
flip with no checksum binding, no staleness protection, and no visible
rollback-to-previous-profile mechanism. This is where Phase 15's RAG work is
genuinely new, not a thin wrapper.

## 1. Existing systems inventory (reused, never duplicated)

| Concern | Existing owner | Reuse strategy |
|---|---|---|
| RAG sandbox acceptance | `backend.services.rag_sandbox_acceptance_service.RagSandboxAcceptanceService`, `RagSandboxRepository` | Read-only: `get_latest_acceptance()`/`get_latest_report()` gate assessment eligibility |
| RAG ingestion/chunking/indexing | `RagIngestionService` | Called by the new production-RAG-candidate build step, exactly as `GovernedRagHandoffService` already calls it for Phase 7 |
| RAG retrieval profiles/activation | `RagRetrievalService` (`create_profile`, `validate_profile`, `activate_profile`, `retrieve`) | `activate_profile()` called only from behind the new governed approval gate |
| Model release candidate/manifest/eligibility/approval/rollback-plan | `ModelReleaseService`, `ModelReleaseRepository` | Called directly; Phase 15 candidate creation binds a Phase-14 `model_candidate_public_id` straight through as `core_model_version_public_id` |
| Model assignment/canary/activation/rollback | `ModelAssignmentService`, `InferenceRuntimeService` | Called directly for canary + activation + rollback; Phase 15 never re-implements `assess_public_activation_gate` |
| Checkpoint acceptance / model-candidate registration | Phase 14 (`IncrementalTrainingCheckpointAcceptanceService`) | Read-only source of eligible candidates |
| Database health/backups | `backend/api/routes/system.py` (`_latest_backup`, `PRAGMA integrity_check`) | Same file-glob convention (`brud_ai_before_v*_*.db`) and same PRAGMAs reused inside `ProductionBackupReadinessService`/`ProductionRestoreReadinessService` |
| Secret redaction | `backend.core.json_utils.redact_secrets`/`SECRET_KEYS` | Reused as-is in every new `_audit()` helper; `ProductionSecretScanService` reuses the same key-marker list plus a value-pattern scan over built frontend assets |
| Admin Assistant propose/confirm/execute pipeline | `AdminAssistantService`, `core_model.admin_assistant.action_registry` | New actions registered the same way Phase 14's were, respecting `BLOCKED_ACTION_SUBSTRINGS = ("train", "pretrain")` (irrelevant here, but the pattern of never letting the assistant itself flip an activation state is followed deliberately — see §6) |
| Audit | `AuditLogRepository.append()` (auto-redacts) | Reused verbatim, no new audit table |

## 2. Production RAG promotion design

New, because no governed equivalent exists. Mirrors Phase 13/14's own shape
exactly: `production_rag_promotion_requests` (draft → awaiting_review →
approved → building_candidate → candidate_ready/validation_failed →
ready_for_activation → rejected/cancelled/expired/superseded) →
`production_rag_release_candidates` (built via `RagIngestionService`,
`production_visible=false` until activated) → `production_rag_validation_results`
(retrieval smoke tests, citation/unsupported-claim/injection re-checks
reusing Phase 13's own evaluation primitives, kept as separate checksummed
runs — never conflated with the original sandbox evaluation) →
`production_rag_promotion_approvals` (separate table, own fingerprint,
stale-rejected on any bound-field change) → `ProductionRagActivationService`
(pre-activation snapshot of whichever profile is currently `active` →
verify approval+checksums+fingerprint → `RagRetrievalService.activate_profile()`
→ post-activation checks → on failure, reactivate the snapshotted previous
profile) → `production_rag_activation_events` (append-only).

## 3. Model release design

Thin: `ProductionModelReleaseRequestService.create_request()` re-verifies
the Phase 14 acceptance chain (`incremental_training_checkpoint_acceptances`
latest decision is `accepted_candidate`/`accepted_with_conditions`, no
`major_regression` comparison — same check Phase 14's own acceptance
service already performed, re-verified here as defense in depth since state
could theoretically change between phases) and calls
`ModelReleaseService.create_candidate(core_model_version_public_id=
<phase14 model_candidate_public_id>, ...)` directly. From there,
`ProductionModelReleaseValidationService` and
`ProductionModelReleaseApprovalService` are thin wrappers that call
`ModelReleaseService.assess_eligibility()`/`verify_artifacts()`/
`verify_manifest()`/`submit_approval()`/`create_release()` and record a
Phase-15-scoped, separately-fingerprinted approval row on top (this is what
makes "model release approval" a *distinct, later, Phase-15-owned* decision
rather than reusing `ModelReleaseService`'s own approval bookkeeping as the
final word).

## 4. Activation and rollback sequence

**RAG**: snapshot current active profile id → verify approval not expired
and fingerprint matches → `activate_profile(candidate)` → run bounded
retrieval/citation smoke checks against the newly active profile → on
failure, `activate_profile(previous)` and record a rollback event; on
success, record a `production_rag_activation_events` row.

**Model**: `ProductionModelActivationService` captures the current
`inference_model_assignments` row for the target scope → calls
`ModelAssignmentService.start_canary()`/`execute_canary()` where the target
scope is `public_chat` (Step 14) → on canary success, calls
`ModelAssignmentService.activate_assignment()` → runs
`InferenceRuntimeService.run_health_check()` → on failure, calls
`ModelAssignmentService.rollback_execute()` to restore the previous
assignment and records the failure; on success, records a
`production_model_activation_events` row. No new activation mechanism is
invented — every actual state transition is one call into the existing
service.

## 5. Artifact-security strategy

New. `ProductionArtifactSecurityService` walks the concrete artifact
directories already used by existing services
(`settings.resolved_pretraining_dir` for checkpoints,
`settings.resolved_tokenizer_dir` for tokenizer artifacts,
`settings.resolved_release_artifact_dir`/`resolved_release_bundle_dir` for
release bundles, `settings.resolved_dataset_export_dir` for dataset
exports, `settings.resolved_backup_dir` for backups) and checks: file mode
bits (no world-write, no world-read where the file is meant to be
admin-only), that the path is not under any directory FastAPI serves
statically (cross-checked against `backend.main`'s mounted static routes —
there are none for these directories, confirmed by inspection), and that a
checksum is present and verifies. Never claims encryption exists unless a
concrete, checkable signal (e.g., a filesystem-level encryption flag) is
present — none is, in this environment, so encryption status is honestly
reported `not_configured`, not `passed`.

## 6. Deployment-readiness checks

New, read-only aggregation over already-existing signals: `Settings` fields
(CORS origins, cookie/session settings, CSRF enablement — all already
enforced elsewhere, this only *reports* their configured state),
`shutil.disk_usage`, `os.cpu_count()`, `PRAGMA integrity_check`/
`foreign_key_check`, current model assignment health, current RAG profile
status. No new enforcement is added here (enforcement already exists in the
auth/CSRF middleware); this is a readiness *report*, not a new gate.

## 7. Backup/recovery checks

`ProductionBackupReadinessService` reuses `system.py`'s own
`_latest_backup()` glob convention and `Settings.database_auto_backup`.
`ProductionRestoreReadinessService` performs an *isolated* restore: copies
the latest backup file to a scratch path under `tempfile.mkdtemp()`, opens
it with a **separate** `sqlite3.connect()`, and runs
`PRAGMA integrity_check`/`PRAGMA foreign_key_check` plus a spot-check of the
`schema_migrations`/`user_version` — the live database file is never opened
for write, never copied over, and the temp copy is deleted after the check.

## 8. Regression strategy

`ProductionRegressionService` orchestrates *pytest invocations as
subprocesses* (via `subprocess.run`, matching how a human would run them —
no attempt to re-implement pytest's collection/execution internally),
recording one `production_regression_results` row per named batch (e.g.
`"phase15_backend"`, `"phase15_frontend"`, `"existing_rag"`,
`"existing_training"`) with exact pass/fail/error counts parsed from
pytest's own summary line. A batch that could not complete (killed by the
environment) is recorded as `status='environment_incomplete'`, distinct
from `status='failed'` — the final report must never conflate the two. This
directly follows Step 24's own instruction ("identify environment-only
failures separately from product failures"), which this session's own
Phase 14 regression attempts already demonstrated is a real, recurring
constraint in this environment (two whole-suite `pytest tests/` runs were
killed with zero output before completing).

## 9. Manual-browser strategy

Browser automation was unavailable in the Phase 14 segment of this same
session and remains unavailable now. Verification will again be performed
against real running `uvicorn`/`vite` dev servers over HTTP (real admin
login, real CSRF enforcement, real endpoint responses), exactly as done for
Phase 14 §23 — documented honestly as HTTP-level verification, not claimed
as browser-flow completion.

## 10. Final readiness-report structure

One `production_readiness_reports` row aggregating: schema version, active
RAG profile id + candidate id + validation summary + approval summary +
activation result, active model assignment + release candidate + release
validation + release approval + canary result + activation result, artifact
security summary, backup/restore readiness, deployment readiness, system
health, regression summary (batch-by-batch), known limitations, and one
`recommendation` value. `production_acceptance_reviews` is the separate,
later, explicit Admin decision against that specific report's checksum —
identical two-step shape to Phase 13's report+acceptance and Phase 14's
report+checkpoint-acceptance.

## 11. Known limitations and blockers going in

- No production traffic exists in this development environment to canary
  against — `ModelAssignmentService.start_canary()`/`execute_canary()` will
  be exercised with synthetic/bounded diagnostic traffic only, same as any
  other admin-diagnostic use of that existing service.
- No real external backup-encryption mechanism is configured; artifact
  security will honestly report `not_configured` for encryption-at-rest
  rather than fabricate a pass.
- Full-repository regression runs have twice been killed by this
  environment before completing (see §8) — the regression service is
  designed around bounded, resumable batches specifically because of this
  observed constraint, not hypothetically.
- Browser automation unavailable (see §9).

## 12. Explicit multimodal deferral

No Image/Audio/Video/Multimodal code, tables, services, routes, or frontend
pages are created anywhere in this phase. The final readiness report's
`recommendation` field only ever certifies Text/NLP readiness; its schema
has no field that could be mistaken for a multimodal completion claim.
