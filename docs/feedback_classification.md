# Feedback Classification and Triage

## Classification categories

30 categories in `core_model.feedback.CLASSIFICATION_CATEGORIES`,
covering correctness (`incorrect`, `partially_correct`,
`unsupported_claim`, `hallucination_like`), language quality
(`wrong_language`, `poor_tamil`, `poor_tanglish`), citations
(`citation_missing`, `citation_invalid`, `citation_wrong`), retrieval
(`retrieval_irrelevant`, `retrieval_missing`), safety
(`unsafe_response`, `over_refusal`, `under_refusal`, `prompt_leakage`,
`role_token_leakage`), memory (`memory_wrong`, `memory_outdated`,
`memory_privacy_issue`, `memory_not_used`,
`memory_should_not_be_used`), and format/length (`format_failure`,
`too_long`, `too_short`, `unclear`, `repetition`).

A feedback event may carry multiple classifications — each is its own
append-only `feedback_classifications` row, never a single overloaded
status field.

## Critical categories

`CRITICAL_CLASSIFICATION_CATEGORIES` (`unsafe_response`,
`prompt_leakage`, `role_token_leakage`, `memory_privacy_issue`,
`memory_should_not_be_used`) are always safety-critical regardless of
the admin-assigned severity — `core_model.feedback.classification.is_critical()`
never relies on severity alone for these.

## Deterministic triage

`core_model/feedback/triage.py` computes priority and queue routing
through fixed, documented rules — never an opaque ML ranking:

1. Blocked privacy/safety -> `critical`.
2. Any always-critical category -> `critical`.
3. Otherwise, the explicit admin-assigned severity, raised to a floor
   of `high` on regression recurrence, or `medium` on high frequency
   (3+ similar open items) or a 1-star rating.

`route_to_queue_type()` maps a fixed, ordered category-to-queue table
(e.g. `poor_tamil` -> `tamil_quality`, `unsafe_response` -> `safety`)
and falls back to `general_quality` when nothing more specific
applies.
