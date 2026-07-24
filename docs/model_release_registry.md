# Model Registry and Release Families (Phase 14)

## Registry is not deployment

Registering a candidate, or even releasing it, never deploys, serves, or
connects anything to the public chatbot. **A registered release is not
automatically deployable or available to the public chatbot** — this
statement is shown on every Admin Dashboard Model Registry tab and is
enforced structurally: nothing in `ModelReleaseService` writes to
`chat_sessions`, `chat_messages`, or any model-assignment table, and
`POST /api/chat` is verified (by test, and by the Phase 14 manual
verification run) to keep returning `model: "placeholder"` after a full
candidate → release → rollback lifecycle.

## Release families

A release family groups compatible releases under one name/slug,
intended use, supported languages, and compatibility policy. Families
are never inferred from filenames or model names — an admin creates one
explicitly via `POST /admin/model-releases/families`.

```
draft --activate/patch--> active --> deprecated --> archived
```

`model_release_families.current_release_public_id` is the family's
"current selected release" pointer. It is a plain `TEXT` column, not a
hard foreign key (matching the project's existing convention for
similar soft cross-references, e.g. `instruction_tuning_candidates
.selected_checkpoint_public_id`), and it is updated **only** by two
service methods: `create_release()` (release promotion) and
`execute_rollback_plan()` (validated rollback) — never by a direct
`PATCH`.

## Release candidates

A candidate is created from an already-registered `core_model_versions`
row — never from a raw filesystem path or arbitrary artifact. Creation
resolves the candidate's checkpoint automatically:

1. First, by the direct `pretraining_checkpoints.core_model_version_id`
   foreign key (the case for a freshly-pretrained base candidate).
2. If none is found, by matching `pretraining_checkpoints
   .model_checksum_sha256` against the candidate's own
   `weights_checksum_sha256` (the case for a Phase-12-promoted
   instruction-tuned candidate, whose own row has no direct checkpoint
   FK — exactly Phase 12's `_promote_instruction_candidate` shape).

A core model version with `lifecycle_status` of `retired`, `archived`,
or `failed` is rejected outright at creation time — a retired or failed
model can never become a release candidate.

## Separation of concerns (deliberately not one status field)

Phase 14 keeps six concepts on six separate fields, never collapsing
them into one "status":

```
core_model lifecycle       core_model_versions.lifecycle_status
instruction-tuning status  instruction_tuning_candidates.status
evaluation readiness       model_chat_readiness_assessments.status
release-candidate status   model_release_candidates.status
deployment eligibility     model_releases.deployment_eligibility
public-chat assignment     (unchanged — always "none" through Phase 14)
```

A model may legitimately be `core_model.lifecycle_status = staging`,
`evaluation = evaluation_blocked`, `release_candidate.status = blocked`,
`deployment_eligibility = not_deployable`, and
`public_chat_assignment = none` — all at once. This is the expected,
correct state for an unproven model, not a bug.
