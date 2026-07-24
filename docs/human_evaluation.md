# Human Evaluation (Phase 13)

`core_model/model_evaluation/human_review.py` stores nothing itself —
reviews are persisted append-only by `model_evaluation_human_reviews` via
the repository layer. The module only aggregates already-persisted rows
and decides which outputs *require* a review.

## Multiple reviews, visible disagreement

Any number of reviews may be submitted for the same output. `aggregate_reviews()`
computes the average `overall_score` and reports `disagreement=true`
whenever reviewers produced more than one distinct `verdict`, or their
`overall_score`s differ by 2 or more points. Disagreement is **never
silently averaged away** — it is a first-class field in the aggregate, and
`aggregate_run_reviews()` rolls it up into a run-level
`disagreement_rate` (the fraction of reviewed outputs with disagreement),
which the chat-readiness gate reads directly
(`max_human_review_disagreement`).

## What must be reviewed

`required_review_output_ids()` is the union of four sets, computed during
`execute_run()`:

1. Every output tied to a `blocking`-severity automated issue.
2. Every output flagged as a safety failure
   (`safety_checks.evaluate_safety_fixture`'s `is_blocking_violation`).
3. One sample output per (language, category) pair observed in the run —
   guaranteeing every combination gets at least a human glance, not just
   the automated score.
4. Candidate-selection borderline cases (reserved for future
   candidate-selection wiring; currently an empty set, since Phase 13 does
   not itself select or promote a candidate).

`review_coverage()` compares this required set against the reviews
actually submitted and returns a `coverage_ratio` plus the specific
`missing_output_ids` — never just a pass/fail boolean, so an admin can see
exactly what still needs attention.

## Rubric

`RUBRIC_VERSION = "phase13-rubric-v1"`. Each review scores relevance,
(optional) correctness, instruction-following, language quality, safety,
and an overall 1–5 score, plus a verdict
(`pass`/`pass_with_warning`/`fail`/`needs_second_review`). The rubric
version is stored on every review row, so a future rubric change never
silently reinterprets historical review scores.
