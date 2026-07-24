# Model Assignment Lifecycle (Phase 15)

```
draft -> validating -> approved -> active <-> paused
                \-> rejected            \-> rolled_back / expired / archived
```

## Immutability after approval

`patch_assignment()` allows editing `generation_config`/`context_policy`/
`fallback_policy`/`canary_percentage`/`release_public_id` while the
assignment is `draft`, `active`, or `paused` — but any edit made while
`active`/`paused` resets `status` back to `draft`, forcing a fresh
`validate → approve` cycle. This is the only way to change an approved
assignment's release or configuration; there is no in-place mutation of
an `approved` row. Each approval produces a new immutable
`inference_assignment_versions` row (auto-incrementing
`version_number`) — prior versions' evidence (checksums, config
snapshot) is never deleted or overwritten.

## Validation (`validate_assignment()`)

Re-derives eligibility **live** from the release's current state
(`assess_assignment_eligibility()`) every time — it never trusts a
cached status. A structurally blocked assignment is set to `rejected`
with the full list of blocking reasons recorded on the
`inference_assignment_events` row; it is not an exception the caller
must catch, since "reject a blocked release" is an expected, correctly-
functioning outcome, not a system failure.

## Approval (`approve_assignment()`)

Reuses Phase 14's `core_model.release.approval_policy` unchanged
(`ApprovalPolicy`, `is_policy_satisfied()`,
`validate_approval_submission()`) — no second approval-policy
implementation. Required roles are `("release",)` for every scope
except `public_chat`, which requires every role in
`BRUD_INFERENCE_REQUIRED_PUBLIC_APPROVAL_ROLES` (default `technical,
evaluation, security, release`). A blocking-eligible assignment cannot
receive an `approve`/`approve_with_warning` decision at all — re-checked
independently at approval time, not just at validation time.

## Activation

`activate_assignment()` requires `approved` or `paused`. For
`public_chat`, activation additionally routes through the separate
public-activation gate (`docs/model_assignment_lifecycle.md`'s sibling,
the "Public-chat activation gate" section of
`docs/inference_runtime_architecture.md`) — a rejection there returns
`activated: false` with reasons, it does not raise, and the assignment's
status is left `rejected` rather than `active`. For every other scope,
activation simply flips `status` to `active`; it does not itself load a
model — the first diagnostic/chat-lab/canary call for that assignment
triggers an on-demand load via `_ensure_loaded()`.

## Assignment events

`created, validated, approved, activated, paused, resumed,
canary_started, canary_stopped, fallback_used, rollback_started,
rollback_completed, rollback_failed, expired, rejected` — append-only,
one row per transition, each carrying the acting admin's public ID and
(where relevant) the blocking/rejection reasons.
