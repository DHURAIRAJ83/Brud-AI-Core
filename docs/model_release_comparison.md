# Release Comparison (Phase 14)

`core_model/release/comparison.py` is genuinely new logic — it does not
reuse Phase 10's `training_run_comparisons` or Phase 13's
`model_evaluation_comparisons`, both of which compare different entities
(pretraining jobs and evaluation runs, respectively) — but mirrors the
same compatibility-level + field-diff shape those tables already
established.

## Compatibility levels

```
compatible            — tokenizer version, model-config checksum, and
                         evaluation-suite identity all match
partially_compatible   — tokenizer version matches, but the hard fields
                          above do not all match
incompatible            — neither tier matches
```

## Direct ranking requires comparable evaluation evidence

`compare_releases()` sets `ranked = true` only when compatibility is
`compatible` **and** both releases carry the same
`evaluation_suite_public_id`. Two releases evaluated under different
evaluation suites are never ranked against each other, even if every
other field lines up — the project's evaluation results are only
comparable when they were produced by the same fixture set and
threshold configuration (see `docs/model_release_reproducibility.md`
equivalent discipline in Phase 13). This is a deliberate, conservative
choice: it is better to report "not directly rankable" than to imply a
false equivalence between two differently-scored candidates.

## What is compared

Model architecture, parameters, context length, tokenizer, dataset
lineage, training token counts, instruction-dataset counts, evaluation
suite/version, language metrics, safety metrics, readiness, artifact
size, resource requirements, known limitations, and deployment
eligibility — recorded as a field-by-field diff
(`build_field_diff()`), never collapsed into a single opaque score.

## Append-only

Every comparison is persisted as a new `model_release_comparisons` row
— comparisons are historical evidence, not a live/mutable computation
that could silently change after the fact.
