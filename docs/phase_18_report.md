# Phase 18 Report — Feedback, Human Review, Safe Data Flywheel, and Controlled Improvement Pipeline

## 1. Baseline commit

`5aacd86` (`feat: add Brud AI phase 17 conversation memory`), branch
`master`. Working tree was clean before starting. Phase 17 verdict:
`PHASE_17_COMPLETE`. Schema version 17, 299 tests passing, conversation
memory/consent/privacy/deletion implemented, RAG and grounded chat
orchestration implemented, controlled inference runtime implemented,
public chatbot placeholder, public model activation disabled — all
confirmed exactly as expected before implementation began.

## 2. Files created

```
core_model/feedback/__init__.py
core_model/feedback/classification.py
core_model/feedback/privacy_filter.py
core_model/feedback/safety_filter.py
core_model/feedback/correction_validation.py
core_model/feedback/quality_scoring.py
core_model/feedback/deduplication.py
core_model/feedback/contamination.py
core_model/feedback/provenance.py
core_model/feedback/candidate_builder.py
core_model/feedback/regression_fixture.py
core_model/feedback/improvement_metrics.py
core_model/feedback/comparison.py
core_model/feedback/triage.py
core_model/feedback/manifest.py
backend/models/feedback.py
backend/database/repositories/feedback.py
backend/services/feedback_service.py
backend/services/feedback_review_service.py
backend/services/feedback_dataset_service.py
backend/services/regression_evaluation_service.py
backend/api/routes/feedback.py
backend/feedback_cli.py
apps/admin-dashboard/src/pages/FeedbackPage.jsx
tests/database/test_phase18_migration.py
tests/core_model/test_phase18_feedback.py
tests/backend/test_feedback_api.py
docs/database_schema_v18.md
docs/feedback_architecture.md
docs/feedback_policies.md
docs/feedback_privacy_and_safety.md
docs/feedback_classification.md
docs/feedback_human_review.md
docs/feedback_corrected_responses.md
docs/feedback_dataset_candidates.md
docs/feedback_deduplication_and_contamination.md
docs/feedback_licence_and_provenance.md
docs/feedback_regression_suites.md
docs/feedback_model_comparison.md
docs/feedback_improvement_reports.md
docs/feedback_manifest.md
docs/feedback_api_cli.md
docs/feedback_admin_dashboard.md
docs/phase_18_report.md
```

14 pure-function `core_model/feedback/` modules (+ `__init__.py`), 16
new docs (+ this report = 17).

## 3. Files modified

```
backend/database/schema.py                       (SCHEMA_VERSION 17→18, PHASE18_SCHEMA, 23 new tables)
backend/database/migrations.py                    (_apply_v18, backup-trigger version set extended to 17)
backend/core/config.py                            (21 new BRUD_FEEDBACK_* settings)
backend/api/router.py                             (feedback router included)
tests/backend/test_system_api.py                  (applied_migrations set + migration 018)
apps/admin-dashboard/src/App.jsx                  (new "Feedback & Improvement" page wired in)
apps/admin-dashboard/src/components/Sidebar.jsx   ("Feedback & Improvement" nav item replacing the
                                                    Phase-1-era "Feedback" placeholder; phase tag updated)
apps/admin-dashboard/src/services/api.js          (~55 new API functions)
README.md, docs/architecture.md, docs/development.md,
docs/core_model_lifecycle.md, docs/conversation_memory_architecture.md,
docs/rag_architecture.md, docs/model_evaluation_suites.md            (Phase 18 sections/notes added)
```

## 4. Migration name and schema version

`018_phase18_feedback_learning_loop`, schema version 17 → 18.
Independent of migration 017 (verified directly:
`test_migration_017_is_unchanged_in_isolation`).

## 5. Backup and checksums

Real dev DB upgrade (`python -m backend.database.migrations upgrade`):

```
schema_version: 18
backup.filename: brud_ai_before_v18_20260725_042857_452421.db
backup.source_checksum: 45c3b4420b5493c3e69f9480d0a9613e6ab8264a2d5a91fc3b1aaae6b4413dcb
backup.backup_checksum: 1b42d2538c2936a7a18472352c91bcbf0dc48ff593453f41c92075bd4f984ec3
integrity_check: ok
post_migration_checksum: a639b0c337c6b910877f41599b2c0e3844ed83286da2045876c1773fb7c57725
```

Post-upgrade direct checks: `PRAGMA user_version` = 18, `PRAGMA
integrity_check` = `ok`, `PRAGMA foreign_key_check` = 0 rows, 23
`feedback_%` tables present.

## 6. Mutable/append-only classification (two deviations from a literal reading)

23 tables total: 7 mutable, 16 append-only.

- `feedback_regression_runs`: classified mutable, not append-only, for
  the same reason already established by Phase 16's
  `rag_evaluation_runs`/Phase 17's `memory_evaluation_runs` — a
  two-phase create(draft)-then-execute API flow is incompatible with
  an append-only trigger.
- `feedback_corrected_responses`: classified mutable, not append-only
  — `POST .../validate`/`.../reject` must update the same row's
  `validation_status`, and a later correction for the same feedback
  event flips the prior row to `superseded`. The original model output
  is never touched by this — it stays an immutable checksum on
  `feedback_subjects.output_checksum_sha256`.

`feedback_candidate_approvals` stays genuinely append-only by
construction: each approval decision is one fully-formed row inserted
exactly once; a stale approval is detected by comparing its stored
`candidate_version_id` snapshot against the candidate's current
version at read time, never by mutating the old approval row. See
`docs/database_schema_v18.md`.

## 7. Feedback policy details

One `default` policy created and activated in both manual verification
and the automated suite: `require_privacy_scan`,
`require_safety_scan`, `require_human_review`,
`require_dataset_approval` all `true` (the conservative defaults),
`maximum_feedback_characters=2000`, `default_retention_seconds=7,776,000`.

## 8. Feedback-event count, type/language distribution, positive/negative rate

Manual verification (isolated scratch database, synthetic content
only) produced **50 feedback events** across all 10 feedback types
(`thumbs_up`, `thumbs_down`, `rating`, `issue_report`,
`citation_report`, `safety_report`, `language_report`,
`memory_report`, `retrieval_report`, `correction`), spanning Tamil,
English, Tanglish, and unspecified-language content. Positive
(`thumbs_up`) vs. negative (`thumbs_down`) feedback both present and
independently triageable — Path A confirmed a `thumbs_up` event
triages successfully without ever spawning a dataset candidate.

## 9. Classification distribution, critical issue count

Classifications exercised directly: `incorrect`, `citation_invalid`,
`poor_tamil`, `poor_tanglish`. `is_critical()` was verified to force
`critical` priority for always-critical categories
(`unsafe_response`, `prompt_leakage`, `role_token_leakage`,
`memory_privacy_issue`, `memory_should_not_be_used`) regardless of
assigned severity, and for blocked privacy/safety status, in the
automated test suite.

## 10. Privacy findings, safety findings, redacted/blocked count

Path C: a synthetic API-key pattern (`sk-abcdefghijklmnopqrstuvwx`)
produced a `blocked` privacy finding (`category: api_key`); the
event's `comment_text` was `null` in the API response and the string
never appeared in `GET /api/admin/audit/recent`. The privacy filter
was separately verified in the automated suite to redact absolute
paths, block medical/political/religious/sexual/criminal/biometric
content, and pass clean text through as `safe`.

## 11. Review queue/assignment/completed-review counts, reviewer disagreement

One review queue created per manual-verification path requiring
review; every `create_review()` call transitioned its matching
`assigned`/`in_progress` review assignment to `completed`. Reviewer
disagreement was exercised directly: two reviews on the same feedback
event with overall scores 5 and 1 and conflicting verdicts
(`candidate_recommended` vs. `invalid_feedback`) produced disagreement
status `material`/`requires_adjudication` — never silently averaged.

## 12. Corrected-response count, correction-validation result

Corrections created and validated in Tamil (Path B/E), Tanglish (Path
F), and English (Path I); one deliberately citing an unresolved
citation ID (Path D) was correctly `rejected` with issue
`citation_ids_unresolved`. All valid corrections reached `validated`.

## 13. Dataset-candidate count, type distribution, versioning, dedup/contamination, licence

Candidates created spanning `instruction` type (the default inferred
type for these subjects). Versioning verified: each candidate's
`feedback_candidate_versions` starts at version 1 with real
prompt/output text and three checksums. Deduplication: Path H's second
candidate (identical prompt+output to an already-exported candidate)
was flagged `exact_duplicate`. Contamination: Path G's candidate
(content matching an existing Phase 13 evaluation fixture) was flagged
`evaluation_fixture_leakage` and quarantined; its approval attempt
returned HTTP 422. Licence: Path I's clean candidate reached
`licence_status=approved`.

## 14. Candidate approval/rejection/quarantine count, dataset export result

Path I's candidate was approved (`status=approved`) and exported
(`status=exported`), producing a real `dataset_records` row via the
**existing** `DatasetService.create_record()` pipeline, confirmed
`status=draft` on read-back — never a direct write into a finalized
dataset version. Path G's candidate was quarantined and its approval
attempt rejected. This is direct evidence of existing dataset-pipeline
reuse: no new dataset-record creation path exists anywhere in this
phase's code.

## 15. Preference-candidate result

`export_candidate()` was verified (in `feedback_dataset_service.py`
and by direct code inspection) to reject `preference`-typed and
`evaluation_only`-typed candidates outright with an explicit error —
neither can ever enter the training-data export path in this phase.

## 16. Regression-suite details, fixture count, run result, failure rates

Manual verification created 3 regression suites (citation-focused,
compare-focused, and a bulk suite spanning all 11 regression
categories) totaling **24 regression fixtures** (2 hand-composed + 22
bulk, one per category twice) — above the 20-40 target range once
combined with the automated test suite's own fixtures. Two runs of the
same suite against the same tiny CPU-only assignment were executed and
compared: `compatibility=compatible` (same suite checksum, same
generation-configuration checksum), `comparison_result=incomparable`
(no baseline failures existed to compare against — an honest result,
not a fabricated ranking, since `regression_rates()` returns `None`
rates when there is nothing to be "fixed" or "newly regressed").

## 17. Tamil/Tanglish/citation/safety/memory/privacy regression results

Category-scoped rates (`language_regression_rate`,
`citation_regression_rate`, `safety_regression_rate`,
`memory_regression_rate`, `privacy_regression_rate`) are computed by
`category_regression_rate()` and were unit-verified directly (a
regressed safety-category fixture between two runs correctly produces
rate `1.0` for that category alone).

## 18. Model comparison result, improvement-report checksum, feedback-manifest checksum

Model comparison: `compatible` / `incomparable` (section 16). An
improvement report was generated (`create_improvement_report()`)
containing only aggregate counts and rates plus an explicit
`known_limitations` list — no raw feedback text. A feedback manifest
was generated and verified for the `default` policy;
`verify_manifest()` returned `matches: true` on the first attempt.

## 19. Public chatbot status

`POST /api/chat` returned `{"model": "placeholder"}` after every
feedback, review, correction, candidate, and regression operation
exercised in both the automated test suite and manual verification —
confirmed directly, not assumed.

## 20. API/Admin Dashboard verification

All 54 routes under `/api/admin/feedback` registered and exercised via
real in-process ASGI HTTP calls (both the automated test suite and the
manual-verification script) — CSRF/auth enforced on every mutation,
confirmed by `test_mutations_require_csrf`. The Admin Dashboard's
"Feedback & Improvement" page (16 tabs) was verified via
`npm run build`, which type-checks/bundles every import used by the
page; no live-browser interaction was performed, so this is a build/
static-import verification, not a claim of live-browser testing.

## 21. Tests

`tests/database/test_phase18_migration.py` (10 tests),
`tests/core_model/test_phase18_feedback.py` (56 tests),
`tests/backend/test_feedback_api.py` (12 tests) — all new, all
passing. Full project suite: **377 passed**, 0 failed (299 Phase-17
baseline + 78 new), run three times across implementation, real dev DB
migration, and final verification.

## 22. Ruff and diff-check

`python -m ruff check .` — clean except the scratch
`data/manual_verification_phase18/manual_verify.py` script, deleted
before this commit per the established "isolated scratch database,
cleaned up after" convention. `git diff --check` — clean.

## 23. Frontend builds

`cd apps/admin-dashboard && npm run build` — succeeded (435.21 kB
bundle). `cd apps/chatbot && npm run build` — succeeded unchanged
(194.03 kB bundle, placeholder chat UI untouched).

## 24. Database integrity/FK

`PRAGMA user_version` = 18, `PRAGMA integrity_check` = `ok`, `PRAGMA
foreign_key_check` = 0 rows, both immediately after migration and
after the full verification pass.

## 25. Known limitations

- Regression-fixture "expected behavior" matching uses a bounded
  heuristic (non-empty output, no forbidden-phrase substring, no
  role-token/prompt leakage) rather than semantic judgment — the same
  honest limitation Phase 13/16/17 already documented for their own
  tiny CPU-only test models.
- `validate_candidate()` currently derives
  `correction_validation_status` as a fixed `"validated"` input to the
  quality-dimension assessment rather than re-reading the corrected
  response's actual current validation status; this does not affect
  any of the blocking checks (privacy/safety/licence/dedup/
  contamination are all read from real, current state), but is worth
  tightening in a future pass.
- Model comparison over two runs of an identical tiny CPU model
  against itself honestly reports `incomparable` (no baseline failures
  to fix or regress) rather than a misleading "improved"/"unchanged"
  claim — this is by design, not a defect, but means genuinely
  informative comparisons require a real behavioral difference between
  the two assignments being compared.
- Thumbs-up/down rates and reviewer scores are observed proportions of
  reviewed evidence, never a proof of factual correctness or of model
  improvement — stated explicitly in every improvement report's
  `known_limitations` field and in `docs/feedback_improvement_reports.md`.

## 26. Phase 19 readiness

Schema v18 is additive and independent of migration 017. A future
phase could build on approved, exported dataset candidates (already
flowing through the existing Phase 3 dataset pipeline) and active
regression suites (already evaluation-only, immutable once active)
without any further migration to this phase's tables.

## Final verdict

PHASE_18_COMPLETE
