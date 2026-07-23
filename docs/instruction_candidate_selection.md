# Instruction-Tuning Candidate Selection and Diagnostic Generation (Phase 12)

## The 12 learning checks

`core_model/instruction_tuning/learning_checks.py::run_learning_checks()`
produces exactly these 12 checks (pass/warning/fail), mirroring the
dataclass-threshold pattern Phase 9–11 already established:

`response_only_masking_verified`, `training_loss_improves`,
`validation_response_loss_finite`, `language_metrics_complete`,
`instruction_format_compliance`, `role_token_leakage_bounded`,
`prompt_leakage_bounded`, `repetition_bounded`, `memorization_risk_bounded`,
`checkpoint_integrity`, `base_model_lineage_complete`,
`resource_limits_respected`.

`response_only_masking_verified` is the Phase 12-specific check: it passes
only if the run recorded both nonzero `assistant_target_tokens` and nonzero
masked `prompt_tokens` — a coarse but real proof that response-only masking
actually happened, not just that training ran.

## Candidate statuses

Exactly one of:

- **`instruction_tuned_candidate`** — no blocking-code check failed, no
  severe leakage, Phase 10's training-process quality gate is not
  `blocked`/`warning`, and no non-pass learning check or memorization
  warning fired.
- **`instruction_tuned_with_warnings`** — usable, but Phase 10's readiness
  is `warning`, or any non-blocking learning check is `warning`/`fail`, or a
  memorization warning fired.
- **`rejected`** — Phase 10's readiness is `blocked`, or a blocking-code
  check (`response_only_masking_verified`, `training_loss_improves`,
  `validation_response_loss_finite`, `checkpoint_integrity`,
  `base_model_lineage_complete`) failed, or role-token leakage is nonzero,
  or prompt-leakage rate exceeds 0.5, or the base checkpoint could not be
  re-verified unchanged, or no run ever completed.

**Even a selected candidate remains `evaluation_required` and
`not_public_chat_ready`.** Selection is evidence-based, not a claim of
readiness.

## Selection procedure

1. Among completed runs, pick the lowest validation-loss run.
2. Evaluate its held-out **test** split for the first time
   (`include_test=True` — the only place the test split is ever used).
3. Call Phase 10's `TrainingEvaluationService.assess_quality()` — training-
   process integrity only, unchanged from Phase 10.
4. Re-verify the base checkpoint's checksum (`TrainingCheckpointManager.verify()`)
   and record `base_checkpoint_checksum_before`/`_after` — both values are
   identical by construction (see [instruction_tuning_training.md](instruction_tuning_training.md)).
5. Derive the status from all of the above.
6. If not `rejected`, promote: insert a **new** `core_model_versions` row
   (new lineage; the base model's row and checkpoint file are never
   modified) with
   `architecture_summary_json = {"base_pretrained": true, "instruction_tuned": true,
   "evaluation_required": true, "not_public_chat_ready": true, ...}`,
   `lifecycle_status = "staging"`. This reuses the exact checkpoint-verify
   call `PretrainingService.verify_checkpoint()` wraps — no new
   verification logic, only a new flag dict and lineage row.

## Bounded diagnostic generation

`core_model/instruction_tuning/generation.py::generate_greedy()` is the only
decode loop anywhere in the codebase (`BrudForCausalLM` has no `generate()`
method; `core_model/inference/__init__.py` remains the Phase 1
`NotImplementedError` stub). Requirements enforced by construction:

- Greedy only — `argmax` of the last-position logits, no sampling, no
  temperature.
- Bounded token count (`BRUD_INSTRUCTION_TUNING_GENERATION_MAX_NEW_TOKENS`,
  default 32) and wall-clock timeout
  (`BRUD_INSTRUCTION_TUNING_GENERATION_TIMEOUT_SECONDS`, default 5s).
- Stops at EOS, at the model's context limit, or the token/time bound —
  whichever comes first; a prompt that alone exceeds the context limit is
  rejected (`prompt_too_long`), never silently truncated.
- Only a registered, **verified** instruction-tuned checkpoint may be used
  (`diagnostic_generate` raises if `checkpoint_verified` is false).
- `POST /runs/{id}/diagnostic-generate` is admin-only (`require_admin` +
  CSRF, same as every other mutation) and never writes to
  `chat_sessions`/`chat_messages`/any model-assignment table — there is
  simply no code path that could persist a diagnostic generation as a
  conversation or assign it to public chat.
- The response always carries the literal notice: *"Admin-only bounded
  diagnostic generation. This is not the public chatbot."*

This output is evaluation evidence only. It is never called production
inference, and `/api/chat` is verified (directly, by test) to remain the
unchanged placeholder after a full candidate promotion.
