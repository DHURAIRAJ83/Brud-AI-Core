# Regression Suites

Regression fixtures are evaluation-only evidence and must not
automatically become training records — displayed verbatim on the
admin dashboard's Regression Suites/Runs tabs and enforced structurally:
`FeedbackDatasetService.export_candidate()` rejects any
`evaluation_only`-typed candidate outright, and regression fixtures
never pass through `create_candidate()`/`export_candidate()` at all.

## Categories

11 categories: `language_regression`, `tamil_quality_regression`,
`tanglish_regression`, `instruction_following_regression`,
`citation_regression`, `retrieval_regression`, `safety_regression`,
`memory_regression`, `privacy_regression`, `format_regression`,
`repetition_regression`.

## Fixture structure

Each fixture (`core_model.feedback.regression_fixture.build_regression_fixture()`)
records category, language, input text, a controlled context, expected
behavior, optional forbidden behavior, optional expected citations,
optional expected memory behavior, severity, and the source feedback
event public IDs it was derived from — plus a checksum. Fixture input
text is screened through the same privacy scan feedback content goes
through, since fixtures are quoted directly in future evaluation runs
and admin dashboards; a fixture whose input text is blocked is never
created.

## Suite lifecycle

`draft -> validated -> active -> retired -> archived`. Fixtures may
only be added while a suite is `draft`/`validated`; validation computes
a deterministic checksum over all fixture checksums, and once
`active`, a suite (and its fixtures, already append-only) is
immutable.

## Execution

`RegressionEvaluationService.execute_run()` loads the assigned
`admin_diagnostic` runtime instance (reusing Phase 15's
`ModelAssignmentService.ensure_instance_loaded()`/
`InferenceRuntimeService.run_generation()` unchanged) and runs every
fixture's input text through it, recording pass/fail via
`core_model.feedback.regression_fixture.evaluate_fixture_result()` — a
fixture only passes if the expected behavior was observed AND no
forbidden behavior occurred; either failure alone fails it. Results
are append-only `feedback_regression_results` rows.
