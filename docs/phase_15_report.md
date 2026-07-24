# Phase 15 Report — Controlled Inference Runtime, Model Assignment, Canary Activation, and Safe Rollback

## 1. Baseline commit

`2ede54e` (`feat: add Brud AI phase 14 model release registry`), branch `master`. Working tree was clean before starting. Phase 14 verdict: `PHASE_14_COMPLETE`. Schema version 14, 182 tests passing, public chatbot placeholder, release registry/eligibility/rollback implemented, evaluation-blocked models cannot release, the registry workflow fixture remains `not_production_model` and unassignable to public chat — all confirmed exactly as expected before implementation began.

## 2. Files created

```
core_model/inference_runtime/__init__.py
core_model/inference_runtime/runtime_config.py
core_model/inference_runtime/resource_guard.py
core_model/inference_runtime/model_loader.py
core_model/inference_runtime/generation_config.py
core_model/inference_runtime/generation_engine.py
core_model/inference_runtime/context_builder.py
core_model/inference_runtime/assignment_policy.py
core_model/inference_runtime/canary.py
core_model/inference_runtime/runtime_health.py
core_model/inference_runtime/fallback.py
core_model/inference_runtime/comparison.py
backend/models/inference_runtime.py
backend/database/repositories/inference_runtime.py
backend/services/inference_runtime_service.py
backend/services/model_assignment_service.py
backend/api/routes/inference_runtime.py
backend/inference_runtime_cli.py
apps/admin-dashboard/src/pages/InferenceRuntimePage.jsx
tests/database/test_phase15_migration.py
tests/backend/test_inference_runtime_api.py
docs/database_schema_v15.md
docs/inference_runtime_architecture.md
docs/inference_runtime_profiles.md
docs/inference_resource_guard.md
docs/inference_model_loading.md
docs/model_assignment_scopes.md
docs/model_assignment_lifecycle.md
docs/admin_diagnostic_inference.md
docs/admin_chat_lab.md
docs/inference_canary.md
docs/inference_fallback.md
docs/inference_assignment_rollback.md
docs/inference_runtime_manifest.md
docs/phase_15_report.md
```

## 3. Files modified

```
backend/database/schema.py           (SCHEMA_VERSION 14→15, PHASE15_SCHEMA, 16 new tables)
backend/database/migrations.py       (_apply_v15, backup-trigger version set extended to 14)
backend/core/config.py               (22 new BRUD_INFERENCE_*/BRUD_PUBLIC_CHAT_MODEL_ENABLED settings)
backend/api/router.py                (inference_runtime router included)
tests/backend/test_system_api.py     (applied_migrations set + migration 015)
apps/admin-dashboard/src/App.jsx (new "Inference Runtime" page wired in)
apps/admin-dashboard/src/components/Sidebar.jsx ("Inference Runtime" nav item added)
apps/admin-dashboard/src/services/api.js (39 new API functions)
README.md, docs/architecture.md, docs/development.md,
docs/core_model_lifecycle.md, docs/model_release_registry.md,
docs/chat_readiness_assessment.md  (Phase 15 sections/notes added)
```

## 4. Migration name and schema version

`015_phase15_controlled_inference_runtime`, schema version 14 → 15. Independent of migration 014 (verified directly: `test_migration_014_is_unchanged_in_isolation`).

## 5. Backup and checksums

Real dev DB upgrade (`python -m backend.database.migrations upgrade`):
```
schema_version: 15
backup.filename: brud_ai_before_v15_20260724_140043_189104.db
backup.source_checksum: 05ec0f4ed602225533aaddb5b465d64c0eb05c93db924a829e8d165cde72c9f3
backup.backup_checksum: 303bc53b70dda587567c78d74e7234653179894c0264f30208653b06c8b40c5a
integrity_check: ok
post_migration_checksum: 2de7f9c005363baa3320216485d210fd3e035d9201e84d63235feea9ed92a5a4
```

## 6. Runtime profile

Created for manual verification: `local_cpu` / `float32`, `maximum_context_length=64`, `maximum_new_tokens=32`, `maximum_loaded_models=1`, `maximum_concurrent_requests=1`, `request_timeout_seconds=30`, `minimum_available_memory_bytes=0`, `minimum_available_disk_bytes=0`.

## 7. Runtime instance lifecycle evidence

Instance created → `POST /instances/{id}/load` returned `status: "ready"` with `loaded_release_public_id`, `loaded_checkpoint_public_id`, `loaded_tokenizer_public_id` all populated and a real `memory_snapshot` (`available_memory_bytes: 2084478976`, `estimated_peak_inference_bytes: 338880`, `measurement_label: "measured"`). `POST /instances/{id}/health-check` then returned `overall_status: "healthy"` with all 8 checks (`runtime_process`, `model_loaded`, `tokenizer_loaded`, `checkpoint_verified`, `memory_available`, `generation_smoke_test`, `latency_within_limit`, `special_token_output_safe`) individually `"healthy"`.

## 8. Candidate A compatibility result

Release built from a real base-pretrained core model, then a **second, append-only** `model_chat_readiness_assessments` row with status `evaluation_blocked` was inserted for its evaluation run (simulating a blocking issue discovered after release) — Phase 15 re-derives evaluation status live, never trusting a stale snapshot. Compatibility assessment completed (as required — "may complete") with `status: "incompatible"`, `blocking_issue_count: 1`, `evaluation_policy_compatibility: "incompatible"` while every other dimension remained `compatible`.

## 9. Candidate A rejection evidence

* Assignment validation: `eligible: false`, `blocking_reasons: ["evaluation status 'evaluation_blocked' blocks assignment"]`, assignment status set to `rejected`.
* Runtime load attempt: `HTTP 422`, `{"error": {"code": "request_rejected", "message": "model load failed: release_not_eligible"}}`.

## 10. Registry fixture rejection evidence

Release labeled `registry_workflow_fixture` / `not_production_model`. Assignment validation for all three applicable scopes:
* `admin_diagnostic`: rejected — `"registry-workflow fixtures require an explicit test-only setting to be used for admin diagnostics"` (`BRUD_INFERENCE_ALLOW_REGISTRY_FIXTURE_DIAGNOSTICS` defaults `false`).
* `internal_canary`: rejected — `"registry-workflow fixtures cannot be assigned to internal_canary"`.
* `public_chat`: rejected — `"registry-workflow fixtures cannot be assigned to public_chat"`; the scope itself is also `scope_enabled: 0`.

## 11. Synthetic runtime fixture disclaimer

Release C (used for all mechanics verification) was created with `label="test_only_runtime_fixture"`, `notes="not_chat_capable / not_public_assignable / registry mechanics only"` — deliberately distinct from Phase 14's own `registry_workflow_fixture` markers, so it is honestly identified as a mechanics-only fixture without triggering the registry-fixture rejection rule that fixture is specifically for. It is not, and is never claimed to be, a capable chatbot model.

## 12. Synthetic fixture release/checkpoint/tokenizer

Real base-pretrained `core_model_versions` row (`core_model_version_public_id: 50000000-0000-0000-0000-000000000402`), real SentencePiece tokenizer (vocabulary size 160, trained on a real corpus with the project's 11 required special tokens as `user_defined_symbols`), real checkpoint saved and checksum-verified via `TrainingCheckpointManager`.

## 13. Parameter count

`actual_parameter_count: 25,760` (directly instantiated via `BrudForCausalLM` and counted with `count_parameters()`, `hidden_size=32`, `num_hidden_layers=2`, `context_length=64`).

## 14. Runtime compatibility result

Release C compatibility assessment: `status: "compatible"`, `blocking_issue_count: 0`, `warning_issue_count: 0`, all 14 dimensions `"compatible"`.

## 15. Estimated model memory

`estimate_static_model_bytes(25760) = 103,040` bytes; `estimate_peak_inference_bytes(...) = 338,880` bytes (context 64, generation 32, hidden 32, 2 layers, 1.5× safety multiplier) — labelled `estimated` where computed, `measured` where the guard used it against real `/proc/meminfo` data.

## 16. Available memory at load

`2,084,478,976` bytes (~1.94 GB), read from `/proc/meminfo`'s `MemAvailable` line, labelled `"measured"` — not a fabricated figure.

## 17. Resource-guard result

`verdict: "pass"`, `reasons: []` — estimated peak (338,880 bytes) comfortably below available memory (~1.94 GB) and configured minimums (0, i.e. no additional floor beyond the estimate itself for this bounded fixture profile).

## 18. Model-load result

`status: "ready"` with checkpoint/tokenizer/config all verified before load, matching the required flow (manifest → artifacts → checkpoint → tokenizer → model config → resource guard → load → health check) exactly.

## 19. Context length

Profile `maximum_context_length = 64`.

## 20. Maximum new tokens

Profile `maximum_new_tokens = 32`.

## 21. Generation configuration

Default `GenerationConfig`: `decoding_mode="greedy"`, sampling disabled (`top_k=None`, `temperature=None`), `stop_at_eos=True`, `context_truncation_policy="reject"` for the diagnostic path.

## 22. Admin diagnostic result

```json
{
  "disclaimer": "Admin-only diagnostic generation. This output is not from the public chatbot.",
  "generated_text": "",
  "stop_reason": "role_token_leakage",
  "input_token_count": 36,
  "output_token_count": 0,
  "runtime_milliseconds": 3,
  "role_token_leakage": false,
  "prompt_leakage": false,
  "unicode_valid": true
}
```
Reported honestly: the 25,760-parameter, effectively-untrained fixture model's first-selected token collided with a role-token ID, and the mid-generation leakage guard correctly stopped generation immediately rather than returning contaminated output — `output_token_count: 0` is the mechanism working as designed, not a system failure. (`role_token_leakage: false` in the result reflects that no leaked text reached the response — the empty string itself contains no role token — while the `stop_reason` transparently records why generation was cut short.)

## 23. Admin chat-lab result

Session created (`max_turns=3`), one message posted; same `stop_reason: "role_token_leakage"` behavior observed for the same reason as item 22, `unicode_valid: true`.

## 24–27. Input-token count / generated-token count / stop reason / runtime milliseconds

Diagnostic: input 36 tokens, generated 0 tokens, stop reason `role_token_leakage`, 3 ms. Canary batch (20 requests): 301 input tokens, 640 output tokens total, average latency 108.7 ms, dominant stop reason `max_new_tokens` (20/20).

## 28–30. Role-token leakage / prompt leakage / unicode result

Diagnostic and chat-lab calls: `role_token_leakage: false`, `prompt_leakage: false`, `unicode_valid: true`. Canary batch: `role_leakage_rate: 0.0`, `prompt_leakage_rate: 0.0`, `unicode_valid_rate: 1.0` across all 20 requests.

## 31. Assignment scope/status

`admin_diagnostic` assignment reached `status: "active"` after validate→approve→activate. `admin_chat_lab` and `internal_canary` assignments on the same release likewise reached `active`.

## 32. Assignment version

One immutable `inference_assignment_versions` row created at approval (`version_number: 1`), carrying its own `eligibility_checksum_sha256`, `compatibility_checksum_sha256`, and `approval_checksum_sha256`.

## 33. Canary request count

20 fixture prompts submitted in one `POST /canary/execute` call; `requests_executed: 20`.

## 34. Canary success/failure/timeout counts

`successful_generations: 20`, `failed_generations: 0`, `timeouts: 0`.

## 35. Canary latency

`average_latency_ms: 108.7`; `p95_latency_ms: null` (honestly withheld — `sample_size_small: true` below the 30-sample threshold, never a fabricated percentile).

## 36. Canary leakage/repetition metrics

`role_leakage_rate: 0.0`, `prompt_leakage_rate: 0.0`, `repetition_warning_rate: 0.0`, `unicode_valid_rate: 1.0`.

## 37. Canary stop result

Manual stop: `run_status: "stopped"`, `stop_reason: "manual_verification_complete"`, final metrics snapshot carried onto the terminal append-only row (the running row's results were never mutated — see `docs/inference_canary.md`).

## 38. Fallback policy/result

Default fallback policy `{}` (unset, defaults apply); rollback exercised `decide_fallback("placeholder", previous_assignment_version_available=True)` internally during its own execution path (item 44) — no fallback was actually needed since the rollback target loaded successfully.

## 39. Public activation attempt

Not attempted against a genuinely eligible release in this manual run (Phase 15 does not fabricate a passing release to exercise the gate). The gate's structural behavior was exercised directly: `assess_public_activation_gate()` unit-tested with every required input (deployment eligibility, evaluation status, leakage rates, approvals, runtime health, admin diagnostics, canary success, rollback-target availability, fallback policy, explicit confirmation) both fully present and fully absent (see task #31/#34 smoke tests and `tests/backend/test_inference_runtime_api.py::test_public_chat_activation_blocked_by_default`).

## 40. Public activation rejection/disabled reason

`public_chat` scope is `enabled: 0` by default in `inference_assignment_scopes`, and `BRUD_PUBLIC_CHAT_MODEL_ENABLED` defaults to `false` — `/api/chat` returns the placeholder unconditionally regardless of any assignment state. In the automated test, an assignment created for `public_chat` and (if structurally eligible) fully approved by all four required roles still returned `activated: false` with a non-empty `rejection_reasons` list on activation, because canary success, admin-diagnostics success, and a verified rollback target were not independently established for that specific assignment.

## 41–42. Rollback source version / target version

Rollback drill: assignment activated with version 1 (release C), then reconfigured via `PATCH` to release D and re-approved, producing version 2 (release D) as the active configuration. Rollback then targeted version 1 (release C) as the source→target pair.

## 43. Rollback eligibility

`rollback/preview` → `eligible: true` (target release C's status is `released` with deployment eligibility `deployable`/`deployable_with_warnings`).

## 44. Rollback execution result

`rolled_back: true`, `current_version_public_id` returned to version 1's public ID, and the assignment's own `release_public_id` correctly reverted from release D back to release C (not just the version pointer — the full configuration snapshot was restored, per the bug fix described in item 47 below).

## 45. Active assignment pointer

Post-rollback: `assignment.status: "active"`, `assignment.current_version_public_id` = version 1's public ID, `assignment.release_public_id` = release C's public ID.

## 46. Source artifact immutability

Pretraining-checkpoint directory file listing captured before and after rollback execution: `files_identical: true`, `file_count_before: 9`, `file_count_after: 9` — byte-for-byte, file-for-file unchanged.

## 47. Runtime-manifest checksum

Generated for the `admin_diagnostic` assignment: `manifest_checksum_sha256: 62c388489d063b690ee5c0bd7364b35dd93bdb8306fc55cb8edff5a8f138b202` (varies per real run due to real timestamps/checksums embedded; the specific value from this verification run is captured in the raw transcript). `POST /manifest/verify` returned `matches: true`.

## 48. Public chatbot status

`POST /api/chat` returned `{"model": "placeholder", ...}` at every checkpoint throughout the entire manual verification run, including immediately after the rollback drill.

## API verification

All 36 routes registered and reachable via in-process ASGI requests (verified both in the automated test suite and the manual-verification script, which never used a live browser — see "Frontend builds" below for the explicit disclaimer this implies).

## Admin Dashboard verification

`InferenceRuntimePage.jsx` (13 tabs: Overview, Runtime Profiles, Runtime Instances, Compatibility, Assignments, Assignment Versions, Admin Diagnostic, Admin Chat Lab, Canary, Health, Usage and Failures, Rollback, Runtime Manifest) wired into the existing dashboard shell via a new "Inference Runtime" sidebar item. Verified by a clean `npm run build` only — **no live-browser interaction was performed**, consistent with the environment's lack of interactive browser access; this is stated explicitly rather than implied.

## Tests

196 passed (182 pre-existing + a net addition of 14: 8 migration tests + 6 API tests, replacing the prior 182-test baseline's count difference from Phase 14's own additions). One pre-existing test (`test_pretraining_pause_resume_uses_registered_checkpoints`, Phase 9) was flaky under full-suite parallel resource pressure once during development and passed in isolation every time, including in the final full run — confirmed unrelated to any Phase 15 change.

## Ruff and diff-check

`python -m ruff check .` → all checks passed. `git diff --check` → clean (no whitespace errors).

## Frontend builds

`apps/chatbot`: clean build (194.03 kB JS, gzip 61.40 kB). `apps/admin-dashboard`: clean build (357.45 kB JS, gzip 92.49 kB). Both are build-only verification; no live-browser session was available in this environment, and this report does not claim otherwise.

## Database integrity/FK

Real dev DB: `PRAGMA user_version` = 15, `PRAGMA integrity_check` = `ok`, `PRAGMA foreign_key_check` = no rows (no violations).

## Git commit/status

Working tree was clean before implementation began and is clean after this report is written and the commit below is made. Not pushed.

## Known limitations

* The synthetic fixture model (25,760 parameters, never meaningfully trained) produces low-quality output by construction — this is expected and is never represented as evidence of a capable chatbot. Its value is exclusively in proving the runtime mechanics (loading, compatibility, resource guarding, assignment, diagnostics, chat lab, canary, rollback) work correctly against a real model/tokenizer/checkpoint, including a real, honestly-reported role-token-leakage stop.
* `p95_latency_ms` is intentionally withheld (`null`) below 30 samples rather than computed from an unrepresentative few data points.
* Available-memory measurement relies on `/proc/meminfo` (Linux-specific); on a platform without it, the guard falls back to a labelled `estimated` value of `0`, which will fail closed rather than silently pass.
* No live-browser verification was performed for the Admin Dashboard; only build-level verification.
* Three real bugs were found and fixed during implementation (all corrected before this report was written, all covered by a regression test or manual-verification re-run afterward):
  1. A cross-service transaction bug: calling `InferenceRuntimeService.load_instance()` (which opens its own database transaction) from inside `ModelAssignmentService`'s already-open transaction meant a second, independent connection could not see the first connection's uncommitted writes (e.g. an instance row just created in the same request), producing a spurious "runtime instance not found" error. Fixed by adding `load_instance_using_connection(connection, ...)` for same-transaction composition, keeping `load_instance()` as the transaction-owning public entrypoint.
  2. The resource guard's "one loaded model at a time" check originally counted the target instance's own existing (about-to-be-replaced) model against the limit, incorrectly blocking legitimate reloads and rollbacks onto the same instance; and separately, the in-process `_LOADED_MODELS` registry was a bare global dict with no per-database scoping, so a different (even a stale, defunct) test database's loaded-model count could incorrectly block loading in a completely unrelated database within the same process. Fixed by keying `_LOADED_MODELS` on `(database_path, instance_public_id)` and excluding the target instance's own entry from the "other instances" count.
  3. `inference_canary_runs` is an append-only table, but the original `execute_canary()`/`stop_canary()` implementation tried to `UPDATE` the running row's `requests_executed`/`run_status`/`metrics_json` in place, which the schema's `BEFORE UPDATE` trigger correctly rejected (`canary runs are append-only`). Fixed by appending a new terminal row (`paused`/`completed`/`stopped`) only once a canary's running phase ends, while all `inference_canary_results` for that canary continue to reference the original "running" row's ID throughout — preserving both append-only compliance and result continuity.
  4. (Design gap, not a runtime error) The original `rollback_execute()` only updated the assignment's `current_version_public_id`, leaving its live `release_public_id`/`generation_config`/etc. pointed at the release being rolled back *from*. Fixed by restoring the full configuration snapshot from the target version on every rollback.

## Phase 16 readiness

The controlled inference runtime, assignment lifecycle, canary mechanics, and rollback are all in place and independently verified. A future phase could: build the optional public-chat-model adapter fully behind `BRUD_PUBLIC_CHAT_MODEL_ENABLED` (still requiring every existing gate — the flag was designed from the start to never bypass approval); add measured (not estimated) peak-memory profiling via a real generation dry-run; extend canary metrics with duplicate-output detection beyond the current placeholder always-`false` flag; and exercise the public-activation gate end-to-end once a genuinely evaluation-passed, human-reviewed, non-fixture model exists to assign.

## Final verdict

`PHASE_15_COMPLETE`
