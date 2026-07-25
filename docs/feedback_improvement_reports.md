# Improvement Reports

`RegressionEvaluationService.create_improvement_report()` produces a
bounded aggregate report: feedback submission/positive/negative
counts, critical-issue count, privacy/safety-blocked counts, dataset
candidate counts (created/approved), the linked regression comparison
result (if any), and an explicit `known_limitations` list — never raw
feedback text, never a raw corrected response.

## Metrics are observed proportions, not proof

`core_model/feedback/improvement_metrics.py` computes every rate
(`positive_feedback_rate`, `valid_feedback_rate`,
`review_completion_rate`, `candidate_approval_rate`,
`regression_fixture_rate`, `median_review_time_seconds`, etc.) as an
observed proportion of reviewed, structured evidence. A thumbs-up rate
is never interpreted as a measure of factual accuracy — every report's
`known_limitations` list states this explicitly, and no code path in
this phase treats feedback ratings alone as proof that a model
improved.

## No promotion on feedback scores alone

Nothing in this phase promotes a model version based on feedback
scores. Model comparison (`docs/feedback_model_comparison.md`) is the
only mechanism that produces an "improved"/"regressed" classification,
and it requires compatible regression-suite evidence, never feedback
ratings.
