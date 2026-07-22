# Brud AI Database Schema v9

Schema v9 is additive on top of schema v8. It adds bounded core-model pretraining control-plane tables and does not rebuild or drop existing dataset, tokenizer, or core-model architecture tables.

## New tables

- `pretraining_jobs`: immutable references to dataset version, tokenizer version, core model version, bounded config, lifecycle status, worker lease fields, latest loss, progress, and completion timestamps.
- `pretraining_job_events`: append-only job lifecycle history.
- `pretraining_metrics`: bounded per-step metrics such as training loss, learning rate, tokens/sec, processed tokens, and memory samples.
- `pretraining_checkpoints`: registered optimizer-aware training checkpoint metadata, safe names, checksums, latest/best flags, and status.
- `pretraining_evaluations`: validation-loss and checkpoint-comparison summaries.
- `pretraining_evaluation_results`: bounded metric rows for each evaluation.
- `training_worker_leases`: local worker claim and heartbeat metadata.

## Safety guarantees

Public APIs expose public IDs only. Numeric database IDs, absolute paths, raw dataset text, optimizer tensors, model tensors, passwords, session tokens, and CSRF tokens are not returned.

Pretraining jobs can use only ready or archived dataset versions, verified tokenizer metadata, and architecture-verified core-model versions. Checkpoints use server-generated safe names under configured project storage.

## Lifecycle

Job statuses:

```text
draft → validating → queued → running → completed
running → pause_requested → paused → queued
running → cancel_requested → cancelled
running → failed
```

Completed jobs are not restarted. Resume restores from the latest registered job checkpoint.

## Append-only evidence

`pretraining_job_events` is protected by immutable update/delete triggers. Metrics and checkpoints are regular persisted evidence; checkpoint contents are verified with SHA-256 checksums.
