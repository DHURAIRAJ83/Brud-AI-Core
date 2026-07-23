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
