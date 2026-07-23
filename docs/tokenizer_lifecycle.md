# Tokenizer Lifecycle

## Family and version model

A tokenizer family is a logical line. A tokenizer version stores algorithm, vocabulary size, dataset-version reference, corpus checksum, artifact checksums, special tokens, configuration, and metrics summary.

## Status transitions

```text
draft → validating
validating → training
training → evaluating
evaluating → staging
staging → active
active → retired
retired → archived
```

Failures move a version or job to `failed`. Failed versions cannot activate.

## Activation and rollback

Activation is explicit. Only a staging or eligible retired version may activate. Activating a version retires the previous active version in that tokenizer family. Rollback is modeled as explicitly activating a verified retired or staging version.

## Assignments

Assignments are separate from lifecycle. Initial assignment keys are `core_model_training`, `chat_input`, `dataset_preview`, and `default`. Null assignments are valid until future phases wire tokenizers into model training.

Phase 8 consumes registered staging, active, retired, or archived tokenizer versions for core model configuration compatibility checks. Tokenizer assignment changes remain independent from core model activation.

Phase 9 consumes registered tokenizer versions for bounded pretraining compatibility checks. Jobs may not accept arbitrary tokenizer paths, and public APIs return only public IDs and checksum summaries.

Phase 11 adds `TokenizerService.evaluate_suitability()`, which reuses the same processor/dataset-row/evaluation helpers to score a registered tokenizer against an *arbitrary* dataset version (not necessarily the tokenizer's own training dataset), without writing to `tokenizer_evaluations` (that table stays scoped to a tokenizer's own dataset). This backs the base-training tokenizer decision (`reuse_existing_tokenizer` / `train_new_tokenizer_version` / `blocked_tokenizer_unsuitable`) — see [base_training_experiments.md](base_training_experiments.md).

Phase 12 does not add a new tokenizer-suitability path — an instruction-tuning experiment always inherits `tokenizer_version_id` directly from its base model (`core_model_versions.tokenizer_version_id`), immutable for the life of the experiment, since the base checkpoint's embeddings are already tied to that exact vocabulary. What Phase 12 does add is `instruction_format_templates.special_token_validation_json`, computed by `validate_template_against_tokenizer()` against the tokenizer's real persisted `special_tokens_json` — never the `SPECIAL_TOKENS` Python default — so a template referencing a token absent from a specific trained tokenizer is caught before any run is created. See [instruction_templates.md](instruction_templates.md).

## Exports

Exports create checksum-verified bundles using safe generated names. APIs expose export metadata and downloadable manifests without revealing absolute filesystem paths.
