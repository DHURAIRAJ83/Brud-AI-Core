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

There is no `public_chat` assignment in Phase 8.
