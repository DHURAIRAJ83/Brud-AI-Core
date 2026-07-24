# Model Evaluation Reproducibility (Phase 13)

## Run comparison

`core_model/model_evaluation/comparison.py` is genuinely new logic — it
does not reuse Phase 10's `TrainingEvaluationService.compare_runs`, which
compares `pretraining_jobs`, a different entity — but mirrors the same
compatibility-level + field-diff shape Phase 10/11/12 already established.

`assess_compatibility()` checks two tiers:

* **Hard fields** (all must match for `compatible`): suite version public
  ID, generation-config checksum, tokenizer version public ID, fixture-set
  checksum, and a combined threshold-configuration checksum
  (`sha256(automated_thresholds_json + readiness_gate_configuration_json)`).
* **Soft fields** (checked only if the hard tier fails): suite version and
  tokenizer version public ID. Matching soft fields yields
  `partially_compatible`; otherwise `incompatible`.

Only a `compatible` result is `ranked=true` — an admin can trust a direct
ranking between two runs only when every hard field lines up exactly.

## Manifest

`ModelEvaluationService.generate_manifest()` builds a JSON manifest per
run containing: run/suite/candidate/checkpoint/tokenizer/fixture-set
public IDs and checksums, the generation configuration and its checksum,
metric/issue counts (including the blocking-issue count), the latest
chat-readiness status, and explicit `known_limitations` (surface relevance
is not factual correctness; safety checks are keyword-based and
non-exhaustive; unsupported-claim risk is a bounded heuristic, not
hallucination detection). `not_public_chat_ready: true` is always present
in the manifest — a hardcoded field, never derived from a mutable value.

The manifest is hashed with SHA-256 and stored append-only in
`model_evaluation_manifests`. `verify_manifest()` recomputes the checksum
of the newest stored manifest row and reports whether it still matches —
the same tamper-detection pattern Phase 10–12 use, verified in
`tests/backend/test_model_evaluation_api.py` by appending a
deliberately-mismatched manifest row (the table is append-only, so
tampering is simulated as a new row, not an `UPDATE`) and confirming
`verify_manifest()` correctly reports `matches: false`.

## Settings surface (`BRUD_EVAL_*`)

All numeric thresholds used by `FixtureValidationThresholds`,
`FixtureCoverageThresholds`, and `ReadinessThresholds` are backed by
`Settings` fields rather than hardcoded inside `core_model/model_evaluation/`
(which stays free of any `Settings` import, per the project's established
"pure functions take explicit threshold dataclasses" discipline):

```
eval_min_total_fixtures, eval_preferred_total_fixtures,
eval_min_tamil_fixtures, eval_min_english_fixtures, eval_min_tanglish_fixtures,
eval_min_mixed_fixtures, eval_min_safety_fixtures, eval_min_robustness_fixtures,
eval_max_prompt_chars, eval_max_reference_chars, eval_max_new_tokens_ceiling,
eval_generation_timeout_seconds, eval_min_instruction_following_score,
eval_min_language_compliance_score, eval_min_surface_relevance_score,
eval_max_unsupported_claim_rate, eval_max_over_refusal_rate,
eval_max_prompt_leakage_rate, eval_max_duplicate_output_rate,
eval_min_unicode_integrity_rate, eval_min_human_review_coverage,
eval_max_human_review_disagreement
```

## Bounded generation, no sampling

`generate_greedy()` (reused unchanged from Phase 12,
`core_model.instruction_tuning.generation`) is the only generation path
Phase 13 calls: no sampling, no temperature, no KV-cache, a hard
`max_new_tokens` cap, a wall-clock timeout, and a stop at EOS or the
model's context limit. `validate_generation_policy()` rejects any suite
that tries to configure otherwise — reproducibility requires that the
same fixture against the same checkpoint always produces the same output.

## Reused by Phase 14's release manifest, not duplicated

Phase 14's `model_release_manifests` includes the evaluation manifest's
own checksum (`evaluation_manifest_checksum_sha256`) and the linked
evaluation run's readiness status verbatim — it never re-runs evaluation
or recomputes a evaluation checksum itself. The same immutability,
tamper-detection (append new row, recompute, compare), and
no-secrets/no-paths discipline documented above for
`model_evaluation_manifests` is followed identically by
`core_model.release.manifest` for release manifests. See
[model_release_manifests.md](model_release_manifests.md).
