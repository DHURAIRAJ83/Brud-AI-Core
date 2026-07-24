# Release Approval Policy (Phase 14)

`core_model/release/approval_policy.py` supports a configurable approval
policy — one admin approval is the minimum for limited local development
(`BRUD_RELEASE_REQUIRED_APPROVAL_ROLES` defaults to `"release"` alone),
while a stricter deployment can require `technical,evaluation,security,
release` roles all to sign off. Regardless of policy strictness, blocking
conditions are never overridable by any approval.

## Four roles, four decisions

```
roles:     technical, evaluation, security, release
decisions: approve, approve_with_warning, reject, request_changes
```

Each approval records the admin's public ID, the candidate, the role,
the decision, an optional comment, and — critically — the eligibility
checksum (and manifest checksum, if one exists) that was current at
submission time.

## Submission-time validation

`validate_approval_submission()` rejects:

* an `approve`/`approve_with_warning` decision when the candidate's
  status is `blocked` (`blocking_candidate_cannot_be_approved`);
* an `approve_with_warning` decision with an empty comment
  (`warning_approval_requires_comment` — a warning approval must say
  *why* the warning is acceptable);
* a self-approval when `BRUD_RELEASE_ALLOW_SELF_APPROVAL` is `false`.

## Policy satisfaction

`is_policy_satisfied()` looks at each required role's **latest**
decision (a later approval for the same role supersedes an earlier one,
matching how the append-only table naturally accumulates history) and
reports satisfied only when every required role has a non-rejecting
latest decision. `submit_approval()` checks this after every submission
and promotes the candidate to `approved` the moment policy is satisfied
— never automatically, and never past a `blocked` status.

## Stale approvals

`is_approval_stale()` compares an approval's stored eligibility/manifest
checksums against the candidate's *current* ones. If the candidate's
evidence has changed since the approval was recorded — a re-run
eligibility assessment, a regenerated manifest — the approval is
considered stale, and `create_release()` refuses to proceed until fresh
approvals are recorded against the current evidence. This prevents an
approval granted against one version of the evidence from silently
authorizing a release built on different evidence.

## Append-only

`model_release_approvals` is append-only — a rejected or superseded
approval is never deleted or edited, only followed by a new row; the
full approval history (including reversals) remains inspectable.
