# Fallback Policy (Phase 15)

`core_model/inference_runtime/fallback.py` — deterministic, no
retries, no silent substitution of an unrelated model.

## Supported policies

`placeholder` (default for public chat), `previous_active_assignment`,
`safe_error`.

## `decide_fallback()`

```
decide_fallback("previous_active_assignment",
                 previous_assignment_version_available=False)
  -> FallbackDecision(action="placeholder",
                       reason="no previous assignment version available, "
                              "defaulting to placeholder")
```

A requested `previous_active_assignment` fallback degrades safely to
`placeholder` when no prior version exists — it never fails open by
serving whatever happens to be loaded, and it never raises in a way
that would leave the caller without a defined outcome.

## On runtime failure

The runtime never retries indefinitely, never loads an unapproved
model to "fill in," and never silently switches to an unrelated model.
`build_fallback_event()` records `{assignment_public_id, fallback_action,
reason, failure_code}` on the relevant `inference_assignment_events`
row every time a fallback is invoked — most visibly during a rollback
whose target load fails (see `docs/inference_assignment_rollback.md`).

## Public-chat default

Unless a release is genuinely activated for `public_chat` (which Phase
15 does not do against real development data — see
`docs/phase_15_report.md`), `/api/chat` continues to serve the Phase 1
placeholder response unconditionally; there is no fallback path to
reason about because there is no active public-chat assignment to fall
back from.
