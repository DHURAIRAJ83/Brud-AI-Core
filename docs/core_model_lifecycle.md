# Core Model Lifecycle

## Family, config, version

A family is a logical model line. A config is a deterministic validated architecture configuration tied to a registered tokenizer. A version combines a family, config, initialization seed, lifecycle state, checkpoints, and check evidence.

## Lifecycle

```text
draft → initialized → architecture_verified → smoke_tested → staging → active
```

Failures move to `failed`; active/staging versions can retire.

## Assignments

Phase 8 assignments are architecture-only:

- `architecture_default`
- `smoke_training_default`
- `future_pretraining_base`

There is no `public_chat` assignment in Phase 8 or Phase 9.

## Phase 9 promotion

A verified completed pretraining checkpoint may be promoted into a new staging model version labeled `base_pretrained`, `not_instruction_tuned`, and `not_chat_ready`. Promotion preserves the source architecture version, tokenizer reference, dataset reference through the pretraining job, and checkpoint checksum evidence. It does not make the model a chatbot model.

## Phase 11 candidate selection

Phase 11's `base_training_service.select_candidate()` calls this same
promotion path — it does not add a second promotion mechanism. A base
training candidate can only be `selected_base_candidate` or
`selected_with_warnings` (never a plain "selected") after passing both
Phase 10's training-process quality gate and Phase 11's language/
generalization learning checks; a candidate that fails either is
`rejected` and never promoted. Every promoted candidate still carries
`not_instruction_tuned: true` and `not_chat_ready: true`, and no phase
before or including Phase 11 assigns any model version to the
`public_chat` assignment key. See
[base_training_candidate_selection.md](base_training_candidate_selection.md).

## Phase 12 instruction-tuned lineage

Phase 12's `instruction_tuning_service.select_candidate()` promotes into a
**new** `core_model_versions` row (new lineage; the base model row and its
checkpoint file are never modified) carrying
`{"base_pretrained": true, "instruction_tuned": true, "evaluation_required": true,
"not_public_chat_ready": true, "source_experiment_public_id": ..., "source_base_model_public_id": ...}`,
`lifecycle_status = "staging"`. Only a base candidate produced by Phase 11
(`lifecycle_status IN ('staging','active')` and
`architecture_summary_json.base_pretrained == true`, with a verified
checkpoint) is eligible as an instruction-tuning source; an already
instruction-tuned model cannot be selected as a Phase 12 source. Candidate
status is `instruction_tuned_candidate` or `instruction_tuned_with_warnings`
(never a plain "selected"), or `rejected`. No phase up to and including
Phase 12 assigns any model version to the `public_chat` assignment key. See
[instruction_candidate_selection.md](instruction_candidate_selection.md).

## Phase 13 evaluation (no new lineage row)

Phase 13 does not promote a new `core_model_versions` row and does not
change lifecycle status. It reads an existing Phase-12-promoted row
directly — eligibility is `lifecycle_status IN ('staging','active')` and
`architecture_summary_json.base_pretrained`, `.instruction_tuned`, and
`.evaluation_required` all `true`, with a verified checkpoint (matched by
`model_checksum_sha256` against the candidate's own
`weights_checksum_sha256`) — and records its findings entirely in the new
`model_evaluation_*` tables. The candidate's `architecture_summary_json`
is never rewritten by Phase 13, so `not_public_chat_ready` stays exactly
as Phase 12 set it, and the readiness gate's outcome
(`evaluation_passed_with_limits`/`evaluation_warning`/`evaluation_blocked`)
is recorded as a separate, append-only assessment — never as a lifecycle
transition. No phase up to and including Phase 13 assigns any model
version to the `public_chat` assignment key. See
[chat_readiness_assessment.md](chat_readiness_assessment.md).
