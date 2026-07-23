# Instruction Language Evaluation (Phase 12)

Phase 12 measures two genuinely different things, and never conflates them:

1. **Response-only loss per language** — an exact, real-valued signal computed
   from the model's actual held-out validation/test examples.
2. **Structural/behavioral compliance** — deterministic checks run against
   bounded greedy generations on fixed fixture prompts, which never had a
   model-generated "expected answer."

## Response-only loss (`instruction_response_loss`)

For each of `ta`, `en`, `tgl`, `mixed`, and `overall`, the run's held-out
(validation, or test at candidate-selection time) examples are filtered by
language and passed to `core_model.training.trainer.instruction_response_loss()`
— the exact same response-only computation the trainer uses internally for
its own validation step, reused rather than re-implemented. If a language has
zero held-out examples (a real risk given `limited_instruction_experiment`
datasets), its loss is reported as `null` with `sample_count: 0` — never
fabricated or interpolated.

## Fixed evaluation fixtures

`core_model/instruction_tuning/fixed_eval_fixtures.py` (`FIXTURE_VERSION =
"phase12-instruction-eval-v1"`) defines hand-composed `(prompt_text,
expected_language, format_category)` triples — Tamil (answer-in-language,
short explanation, definition, simple transformation, punctuation/numerals),
English (simple instruction, structured short answer), Tanglish (requested
Tamil/Tanglish answer, spelling variants), Mixed (Tamil question with English
technical terms, language-preservation request), and format fixtures
(one-line answer, numbered response, translation direction). There is
deliberately no "expected response" string — grading is structural, not
exact-match, since exact-match grading against a model-generated or
hand-picked "correct" answer is not a claim Phase 12 makes.

## Structural checks per generation

Each fixture prompt is run through `core_model.instruction_tuning.generation.generate_greedy()`
(bounded, admin-side only — see [instruction_candidate_selection.md](instruction_candidate_selection.md)),
and the output is checked with `core_model/instruction_tuning/evaluation.py`:
`response_not_empty`, `no_role_token_leakage`, `no_system_prompt_leakage`,
`no_excessive_repetition`, `bounded_length`, `valid_unicode` (plus
`eos_termination` and `training_response_exact_match_rate_bounded` used
elsewhere in learning checks). Aggregate rates
(`role_leakage_rate`, `prompt_leakage_rate`, `repetition_rate`) are computed
across all fixture generations for a run and feed directly into the 12
learning checks (see [instruction_candidate_selection.md](instruction_candidate_selection.md)).

## Response-language compliance is script-based, not model-based

`core_model/instruction_tuning/language_checks.py` reuses the exact
`TAMIL_PATTERN`/`LATIN_PATTERN` regexes Phase 11 already established (never
redefines them) and computes Tamil-script/Latin-script/mixed-script ratios.
No external language-detection model is used. Tanglish (`tgl`) is always
evaluated as its own category against the Latin-script ratio — it is never
folded into "English" merely because both are Latin-script.
