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

## Exports

Exports create checksum-verified bundles using safe generated names. APIs expose export metadata and downloadable manifests without revealing absolute filesystem paths.
