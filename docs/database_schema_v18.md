# Database Schema v18 — Feedback Improvement Pipeline

Migration `018_phase18_feedback_learning_loop`, schema version 17 → 18,
independent of migration 017 (verified directly:
`test_migration_017_is_unchanged_in_isolation`). Adds 23 tables: 7
mutable, 16 append-only.

## Tables

Mutable (7):

- `feedback_policies` — collection/retention/candidate-conversion
  rules. `lifecycle_status` CHECK `draft|validated|active|deprecated|archived`.
- `feedback_events` — the feedback item itself. `feedback_type` CHECK
  10 values, `status` CHECK 10 values, `privacy_status`/`safety_status`
  aggregate columns updated as findings are recorded.
- `feedback_review_queues` — `queue_type` CHECK 11 values,
  `lifecycle_status` CHECK `draft|active|archived`.
- `feedback_review_assignments` — `status` CHECK 6 values
  (`assigned|in_progress|completed|reassigned|cancelled|expired`).
- `feedback_dataset_candidates` — `status` CHECK 9 values
  (`draft|validating|review_required|approved|approved_with_warnings|rejected|quarantined|exported|archived`).
- `feedback_regression_suites` — `lifecycle_status` CHECK
  `draft|validated|active|retired|archived`.
- `feedback_regression_runs` — **deviation**: classified mutable, not
  append-only, for the same reason already established by Phase 16's
  `rag_evaluation_runs` and Phase 17's `memory_evaluation_runs` — a
  genuine two-phase create-then-execute API flow (`POST .../runs`
  creates a `draft` row, `POST .../execute` updates it to a terminal
  status) is incompatible with an append-only trigger.

Append-only (16): `feedback_subjects`, `feedback_classifications`,
`feedback_attachments`, `feedback_human_reviews`,
`feedback_corrected_responses` (see deviation below),
`feedback_privacy_findings`, `feedback_safety_findings`,
`feedback_quality_assessments`, `feedback_candidate_versions`,
`feedback_candidate_issues`, `feedback_candidate_approvals`,
`feedback_regression_fixtures`, `feedback_regression_results`,
`feedback_model_comparisons`, `feedback_improvement_reports`,
`feedback_manifests`.

`feedback_corrected_responses` is a **second deviation**: created
`draft`, then `POST .../validate` or `POST .../reject` must update the
same row's `validation_status` (and a later correction for the same
feedback event flips the prior row to `superseded`). This never
touches the original model output — that stays an immutable checksum
on `feedback_subjects.output_checksum_sha256` — only the correction
proposal's own lifecycle is mutable.

`feedback_candidate_approvals` stays append-only by construction: each
approval decision is one fully-formed row inserted exactly once
(mirrors `rag_answer_citations`); a stale approval is detected by
comparing its stored `candidate_version_id` snapshot against the
candidate's current version at read time, never by mutating the old
approval row.

## The subject-snapshot decision

`feedback_subjects` holds one immutable snapshot row per feedback
event, created before the event itself, containing only public-ID
references and checksums for whichever of the 7 subject types
(`inference_result`, `rag_grounded_answer`, `conversation_response`,
`evaluation_output`, `memory_orchestration_response`,
`release_candidate`, `model_release`) the feedback is about — never a
dozen mostly-null FK columns, and never raw hidden system prompts or
private content. `subject_type` + `subject_reference_public_id` is
validated against the real owning table at the service layer (never
an arbitrary string or filesystem reference).

## Real dev DB upgrade

```
python -m backend.database.migrations upgrade
schema_version: 18
integrity_check: ok
```

Post-upgrade: `PRAGMA user_version` = 18, `PRAGMA integrity_check` =
`ok`, `PRAGMA foreign_key_check` = 0 rows, 23 `feedback_%` tables
present.
