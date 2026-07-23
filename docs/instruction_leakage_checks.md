# Prompt/Role Leakage, Repetition, and Memorization Checks (Phase 12)

None of these checks prove complete prompt-injection safety, factual
correctness, or production readiness — they are conservative, deterministic,
bounded-threshold signals only.

## Role and prompt leakage (`core_model/instruction_tuning/evaluation.py`)

- `no_role_token_leakage` — fails if any of `<system>`, `<user>`,
  `<assistant>` appear literally in a generated response.
- `no_system_prompt_leakage` — uses `difflib.SequenceMatcher` to find the
  longest common substring between the generated text and (a) the system
  text and (b) the user/prompt text; fails if either exceeds
  `min_match_chars` (20 by default) — a conservative, cheap detector of
  "the model echoed its instructions back," not a proof of leak-proofness.

Aggregated across a run's fixture generations:
`role_leakage_rate` must be exactly `0` to pass
`BRUD_INSTRUCTION_TUNING_MAX_ROLE_LEAKAGE_RATE` (default `0.0` — any role
token leak is treated as a real defect, not a rate to tolerate).
`prompt_leakage_rate` is allowed up to `BRUD_INSTRUCTION_TUNING_MAX_PROMPT_LEAKAGE_RATE`
(default `0.1`) before warning, and up to `0.5` before the
`prompt_leakage_bounded` learning check turns from `warning` to `fail`.

## Repetition

`no_excessive_repetition` computes the most-frequent-token ratio in a
generated response (via `collections.Counter`) and flags `warning` above
`BRUD_INSTRUCTION_TUNING_MAX_REPETITION_RATE` (default `0.2`). This is a
cheap, real signal for degenerate outputs (a model that has learned very
little useful behavior often repeats a single token or short phrase) — it is
not a fluency or coherence score.

## Memorization (`core_model/instruction_tuning/memorization_checks.py`)

- `exact_training_response_reproduction_rate` — fraction of held-out fixture
  generations whose SHA-256 hash exactly matches a training response's hash.
  Only hashes are compared; no raw matched text is ever surfaced in reports.
- `duplicate_output_rate` — fraction of a run's own generations that
  duplicate each other. A high rate here (observed directly during manual
  verification: a tiny Micro model on a tiny dataset genuinely produced
  near-identical outputs across most fixtures) is an honest sign of a
  degenerate, under-trained model, not a bug in the check.
- `longest_matching_span_ratio` — longest common substring between a
  generation and any sampled training response, reported only as a *ratio*
  of the generation's length, never the matched text.
- Train/validation(-response)-loss gap combined with near-zero training loss
  triggers `low_train_high_validation_response_loss_gap`.

`memorization_risk_bounded` (one of the 12 learning checks) is `pass` only
when zero memorization warnings fired; any warning present makes that check
`warning`, which — combined with Phase 10's process-quality gate — can push
a candidate from `instruction_tuned_candidate` to
`instruction_tuned_with_warnings`.
