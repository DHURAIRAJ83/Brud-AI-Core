# Assignment Rollback (Phase 15)

Rollback is **assignment-level**, not release-level (contrast Phase
14's release-level rollback, `docs/model_release_rollback.md`) — it
selects a previous `inference_assignment_versions` row, not a previous
`model_releases` row directly.

## Preview (`rollback_preview()`)

Verifies the target version belongs to the assignment being rolled
back, and that its release is still `released` with deployment
eligibility `deployable`/`deployable_with_warnings` — never assumes the
target is still good just because it once was.

## Execute (`rollback_execute()`)

1. Re-verifies target-release eligibility (same check as preview,
   independently — defense in depth, not a shared cached result).
2. Records a `rollback_started` event.
3. Resolves the assignment's runtime instance and attempts to load the
   target release onto it via `load_instance_using_connection()` — the
   full verify-then-load pipeline, not a shortcut.
4. On success: restores the assignment's `model_release_id`,
   `inference_runtime_profile_id`, `generation_config_json`,
   `context_policy_json`, `fallback_policy_json`, and
   `canary_percentage` **from the target version's own stored
   snapshot** (not just the release pointer) — every column of the
   assignment reverts, not only which release it points to. Sets
   `status="active"` and `current_version_public_id` to the target.
   This full-snapshot restore was added after a real bug was caught:
   an earlier version only updated `current_version_public_id`, leaving
   the assignment's live `release_public_id` pointed at the release
   being rolled back *from* (see `docs/phase_15_report.md`).
5. On load failure: records an `inference_failures` row
   (`model_load_failed`), sets `status="paused"` (not `active`, not
   silently left on the failed release), and records
   `rollback_failed` — the public chatbot (which was never touched)
   remains exactly as safe as before the attempt.

## Never touches artifacts on disk

Rollback changes only database rows and the in-process
`_LOADED_MODELS` slot for the affected instance. Verified directly: a
manual rollback drill captured the pretraining checkpoint directory's
full file listing before and after execution and confirmed it
byte-for-byte, file-for-file identical (see
`docs/phase_15_report.md`).

## History is never deleted

Every prior `inference_assignment_versions` row remains queryable via
`GET /assignments/{public_id}/versions` after a rollback — rollback
changes which version is *active*, never which versions *exist*.
