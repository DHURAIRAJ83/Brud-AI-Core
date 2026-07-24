# Evaluation Suites (Phase 13)

An evaluation suite is a versioned, checksummed bundle of generation
configuration, automated thresholds, human-review rubric, and
readiness-gate configuration. It is the unit that must stay stable across
runs for a comparison to be meaningful.

## Lifecycle

```
draft --validate--> validated --activate--> active
```

* **draft**: editable. `PATCH /admin/model-evaluation/suites/{id}` only
  succeeds while a suite is `draft` — `ModelEvaluationService.patch_suite`
  raises `ValidationError` otherwise. This mirrors the existing project
  pattern (`PretrainingService.patch_job`'s `status != 'draft'` gate) rather
  than inventing a new immutability mechanism.
* **validated**: `validate_suite` calls
  `core_model.model_evaluation.suite.validate_generation_policy` against the
  suite's `generation_configuration` and rejects any suite that enables
  sampling, temperature, streaming, or unbounded/oversized generation.
  Bounded, deterministic, greedy generation is the only supported policy.
* **active**: `activate_suite` requires at least
  `BRUD_EVAL_MIN_TOTAL_FIXTURES` fixtures across all of the suite's fixture
  sets, then stamps `activated_at`. Only an active suite can be used to
  create a run — this is what keeps the suite's thresholds and generation
  policy stable underneath every run created against it.

`model_evaluation_suites` is the one mutable table in Phase 13's schema
besides `model_evaluation_runs`; there is no database-level trigger
enforcing suite immutability once active — the service layer's
status-gated `patch_suite`/`validate_suite` is the actual enforcement,
exactly as Phase 9–12 already do for jobs/experiments.

## Suite checksum

`core_model.model_evaluation.suite.suite_checksum()` hashes the suite's
name/version/description/supported_languages/generation_configuration/
automated_thresholds/human_review_rubric/readiness_gate_configuration —
the full set of fields that must not silently drift once runs start
depending on the suite. This checksum is persisted at creation time and
is one of the fields `assess_compatibility()` (see
`docs/model_evaluation_reproducibility.md`) checks when comparing two
runs.

## Fixture sets belong to a suite, not a run

A `model_evaluation_run` references a suite (via
`model_evaluation_suite_id`) but not a fixture set directly — there is no
schema column for it, because a suite's fixture library can grow over
time via multiple fixture-set submissions. Instead, the fixture set a run
was created against is recorded inside the run's own
`generation_configuration_json` blob (`fixture_set_public_id`), alongside
the actual bounded generation policy for that run. This keeps the schema
additive (no new column, no migration risk) while still making every run
traceable to the exact fixture set it evaluated.
