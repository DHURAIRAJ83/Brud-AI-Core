# Model Comparison

`core_model/feedback/comparison.py` mirrors the compatibility-level +
field-diff shape already established by `core_model.rag.comparison`
(Phase 16) and `model_evaluation_comparisons` (Phase 13). Direct
ranking requires the exact same regression suite and generation
configuration — an admin can trust "improved"/"regressed" only when
both runs were scored against identical evidence.

## Compatibility

`assess_compatibility()` returns `compatible` only when both runs
share the same regression-suite checksum and generation-configuration
checksum; `partially_compatible` when only the soft fields
(assignment scope, RAG profile, memory policy) match; otherwise
`incompatible`.

## Comparison result

`classify_comparison_result()` never produces a ranking claim for
incompatible evidence — it returns `incomparable` outright.
For compatible runs, `core_model.feedback.improvement_metrics.regression_rates()`
computes `fixed_failure_rate`, `persistent_failure_rate`, and
`new_regression_rate` over the fixtures shared by both runs (a fixture
present in only one run is excluded from the comparable set, never
silently treated as fixed or as a new regression); the result is
`improved`, `mixed`, `unchanged`, or `regressed` depending on which
rates are non-zero. When there are no shared baseline failures to
compare (rates return `None`), the result is honestly `incomparable`
rather than fabricating a claim — observed directly in manual
verification Path J, where two runs of the same tiny CPU model against
itself produced `incomparable` rather than a misleading ranking.

## Per-category rates

`category_regression_rate()` computes the same fixed/regressed logic
scoped to one regression category at a time (language, citation,
safety, memory, privacy), surfaced on `feedback_model_comparisons` as
`language_regression_rate`, `citation_regression_rate`,
`safety_regression_rate`, `memory_regression_rate`, and
`privacy_regression_rate`.
