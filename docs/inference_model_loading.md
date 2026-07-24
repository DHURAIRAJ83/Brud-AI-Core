# Model Loading (Phase 15)

## Required flow

```
assignment
  -> release
  -> release manifest verify
  -> artifact inventory verify
  -> checkpoint verify
  -> tokenizer verify
  -> model config verify
  -> resource guard
  -> load model
  -> runtime health check
```

`InferenceRuntimeService.load_instance()` (public entrypoint, opens its
own transaction) and `load_instance_using_connection()` (for callers
that already hold an open connection — see
`docs/inference_runtime_architecture.md`) implement this exact sequence
via `gather_release_facts()`, never skipping a step and never accepting
a release whose status isn't `released` or whose evaluation status is
`evaluation_blocked`.

## Registered artifacts only

Checkpoints load from `settings.resolved_pretraining_dir /
candidate["checkpoint_safe_name"]` via the existing
`TrainingCheckpointManager` (checksum-verified `load_states()`/`verify()`
— no second checkpoint verifier). Tokenizers load via
`TokenizerService.processor_for_version()` (the existing tokenizer
registry — no second tokenizer registry). Neither the API nor the CLI
accepts a filesystem path from a caller; every path is derived from a
registered public ID.

## Failure handling (`classify_load_outcome()` / `_fail_load()`)

Any failed step records an `inference_failures` row with one of the 23
fixed failure codes (`manifest_mismatch`, `artifact_verification_failed`,
`checkpoint_corrupt`, `tokenizer_invalid`, `vocabulary_mismatch`,
`special_token_mismatch`, `memory_guard_failed`, …), sets the instance's
`status` to `failed`, clears its `_LOADED_MODELS` entry, and raises
`ValidationError` — a partial load never leaves the instance in a
half-loaded, ambiguous state.

## Vocabulary and special-token validation

`verify_vocabulary_compatibility()` requires the model config's
`vocabulary_size` to exactly equal the tokenizer's registered
`vocabulary_size`. `missing_special_tokens()` requires `<bos>`, `<eos>`,
`<system>`, `<user>`, `<assistant>` to all resolve to a real token ID
(`processor.piece_to_id(token) >= 0`) — these same IDs become the
generation engine's `forbidden_role_token_ids` set, so a model that
somehow reproduces a role token during generation is caught immediately
rather than only in a post-hoc check.

## Unloading

`unload_instance()` clears the `_LOADED_MODELS` entry (releasing the
model/tokenizer/processor references so they become eligible for
garbage collection), resets the instance's loaded-release/checkpoint/
tokenizer fields to `null`, and records the health state — it never
deletes any artifact on disk. Loading a different release onto an
already-loaded instance (rollback, or an operator reassigning a
profile's single instance) goes through the identical verify-then-load
sequence above; nothing is exempted for a "reload."
