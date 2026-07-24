# Rollback (Phase 14)

Rollback in Phase 14 is **metadata-level only**. Executing a rollback
plan never starts or stops a model server, never changes an environment
variable, never restarts a process, never assigns the public chatbot's
model, and never deletes a source artifact — it changes exactly two
things: the source release's `status` and the family's
`current_release_public_id`.

## Rollback plan lifecycle

```
draft --validate--> validated --approve--> approved --execute--> executed
                 \-> rejected
```

`create_rollback_plan()` immediately runs
`core_model.release.rollback.assess_rollback_target()` against the
proposed target release and stores the result — if the target is
ineligible, the plan is created already `rejected`, so an admin never
has to guess why validation will fail later.

## Target eligibility rules

A rollback target must:

* have previously been `released` or `deprecated` (never `draft`,
  `rolled_back`, `retired`, or `archived`);
* not be archived;
* have verified artifacts (the target candidate's latest eligibility is
  `eligible` or `eligible_with_warnings`);
* have a verified manifest (checksum recomputation matches);
* be compatible with the release family;
* have a deployment eligibility other than `not_deployable`;
* not be evaluation-blocked;
* have no unresolved blocking issue.

Any single failing condition makes `assess_rollback_target()` return
`eligible: false` with the specific reasons listed — never overridden
by approval. Rolling back to a corrupt or blocked release is rejected
at plan-creation time, before validation is even attempted.

## Execution

`execute_rollback_plan()` requires the plan to be `approved`, then, in
one transaction:

1. Marks the source release `status = "rolled_back"`.
2. Updates the family's `current_release_public_id` to the target
   release's public ID.
3. Records an append-only `model_release_rollback_events` row (previous
   release, new release, approval evidence, executing admin).
4. Audits the action.

No filesystem operation occurs. Verified directly in the Phase 14
manual verification run: the target release's checkpoint directory's
file listing was captured before and after `execute_rollback_plan()` and
found byte-for-byte identical (same filenames, nothing added or
removed).

## Current-release pointer

`model_release_families.current_release_public_id` can change only
through `create_release()` (a fresh release becomes current
automatically — "release promotion") or a validated, approved, executed
rollback plan. A `PATCH /families/{id}` request cannot set this field
directly.
