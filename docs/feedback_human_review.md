# Human Review Queues and Reviews

## Review queues

11 queue types (`general_quality`, `language`, `tamil_quality`,
`tanglish_quality`, `citation`, `retrieval`, `safety`, `privacy`,
`memory`, `dataset_candidate`, `regression`). A queue has its own
`draft/active/archived` lifecycle, independent of any single feedback
event.

## Review assignments

Each assignment records the queue, the feedback event, the reviewer,
priority, due date, and a conflict-of-interest flag. Statuses:
`assigned|in_progress|completed|reassigned|cancelled|expired`.
`BRUD_FEEDBACK_MAX_ACTIVE_REVIEW_ASSIGNMENTS` bounds concurrent open
assignments (default 20).

## Human reviews are append-only

`feedback_human_reviews` never updates an existing row: every review a
reviewer submits is a new immutable row, so multiple reviewers'
opinions on the same feedback event all remain visible
(`FeedbackReviewService.get_reviews()`), never silently overwritten or
averaged into one value.

Score fields (1-5): correctness, relevance, language quality, safety,
citation, retrieval, memory-use, and a required overall score.
Verdicts: `valid_feedback|partially_valid|invalid_feedback|needs_second_review|privacy_blocked|safety_blocked|candidate_recommended|regression_recommended`.

## Disagreement is measured, never smoothed away

`core_model.feedback.quality_scoring.assess_review_disagreement()`
computes `none|minor|material|requires_adjudication` from explicit
signals: classification disagreement, verdict disagreement, and score
variance (thresholds at 1.0 for minor, 2.0 for material). A material
split between two reviewers is never averaged into a single "midpoint"
score — it surfaces as its own status, verified directly in the
automated test suite and in manual verification (a 5-vs-1 overall
score split with conflicting verdicts produces `material` or
`requires_adjudication`, never `none`).
