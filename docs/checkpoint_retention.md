# Checkpoint Retention

## Overview

`checkpoint_retention_actions` (append-only) records every retention preview
and apply decision. Classification logic lives in
`core_model/checkpoints/retention.py:classify`, called from
`backend/services/training_evaluation_service.py`. There is no endpoint that
deletes a checkpoint by ID directly — retention only ever classifies
checkpoints as `protected` or `eligible`, and "apply" only archives
(`pretraining_checkpoints.status='archived'`) checkpoints already classified
`eligible`.

## Always protected

A checkpoint is `protected` (never eligible for archival) if any of:

* it is the job's latest checkpoint (`is_latest=1`);
* it is the job's best-validation checkpoint (`is_best=1`);
* its weights checksum was promoted to a `core_model_versions` row
  (`source_job_public_id` in that row's `architecture_summary_json` matches
  this job);
* it is the source checkpoint of a recovery attempt currently `validating`/
  `recovering`;
* its `checkpoint_kind` is `final`.

Everything else is bucketed by `checkpoint_kind` (`periodic`,
`best_validation`, `pause`) against configurable retention counts, newest
first:

```
BRUD_PRETRAINING_KEEP_PERIODIC   (default 3)
BRUD_PRETRAINING_KEEP_BEST       (default 1)
BRUD_PRETRAINING_KEEP_FINAL      (default 1)
BRUD_PRETRAINING_KEEP_PAUSE      (default 1)
```

Once a bucket's quota is filled (newest-first), any further checkpoint in that
bucket is classified `eligible`.

## Workflow

```
POST /jobs/{id}/retention/preview
      ↓ classifies every checkpoint, records a preview action per checkpoint
GET result: { items: [{ public_id, classification, protection_reason }] }
      ↓ operator selects checkpoint public IDs classified "eligible"
POST /jobs/{id}/retention/apply  { checkpoint_public_ids: [...] }
      ↓ re-classifies fresh (never trusts a stale preview) and rejects
        any public ID that isn't currently "eligible"
```

`retention/apply` always re-runs `classify()` at apply time — it never
archives based on a client-cached preview, so a checkpoint that became
protected between preview and apply (e.g. promoted in the meantime) is
rejected with a `ValidationError`.

## Dry run

`BRUD_PRETRAINING_RETENTION_DRY_RUN` defaults to `true`. When true, `apply`
still validates and records a `checkpoint_retention_actions` row for every
requested checkpoint, but does not flip `pretraining_checkpoints.status`. Set
it to `false` to allow real archival.

## Archive, not delete

Applying retention sets `status='archived'` and `archived_at`; it never
removes the checkpoint's files from disk. Physical cleanup of archived
checkpoint directories is intentionally out of scope for this phase.
