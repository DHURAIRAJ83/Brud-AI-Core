# Leakage, Repetition, and Degeneration Checks (Phase 13)

`core_model/model_evaluation/degeneration_checks.py` reuses Phase 12's
`no_excessive_repetition`/`valid_unicode`/`eos_termination`
(`core_model.instruction_tuning.evaluation`) and `duplicate_output_rate`
(`core_model.instruction_tuning.memorization_checks`) directly rather than
duplicating them, and adds two new checks Phase 12 did not need because
its fixtures were plain sentences, not adversarial-repetition probes:

* `token_loop_detected` — a run of `min_run_length` (default 5) identical
  consecutive tokens.
* `phrase_loop_detected` — an n-gram (`phrase_size`, default 3) repeated
  `min_repeats` (default 3) or more times anywhere in the response.

`evaluate_run_level_degeneration()` computes the run's overall
`duplicate_output_rate` (near-identical responses across unrelated
fixtures — a collapse signal) and `eos_termination_failure_rate` (how
often generation stopped for a reason other than a natural end-of-sequence
token). `generic_response_collapse()` flags a run where too many distinct
prompts produced the same response text.

## Leakage checks (reused from Phase 12)

`no_role_token_leakage` and `no_system_prompt_leakage` are imported
directly from `core_model.instruction_tuning.evaluation` — Phase 13 does
not redefine role-token or prompt-leakage detection. A leaked role token
(`<system>`/`<user>`/`<assistant>`) is always `severity="blocking"` in
Phase 13's issue log, since it indicates the model exposed internal
training structure verbatim to the user. Copied system-prompt or
user-prompt content raises `system_prompt_leakage` (when a `system_prompt`
was set on the fixture) or `prompt_leakage` otherwise, at `severity="error"`.

## Run-level metrics

`role_leakage_rate`, `prompt_leakage_rate`, `system_prompt_leakage_rate`,
and `unicode_integrity_rate` are all recorded as `overall` run-level
metrics, each derived from the per-fixture pass/fail flags rather than
recomputed independently — one source of truth per signal.
