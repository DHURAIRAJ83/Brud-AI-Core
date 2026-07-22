# Pretraining Configuration

Phase 9 supports CPU-safe bounded configuration:

- optimizer: `adamw`
- scheduler: `constant`, `linear_warmup_decay`, or `cosine`
- device: `cpu`
- dtype: `float32`
- dataloader workers: `0`
- overlength policy: `drop_oversized` or `split_oversized`

Default verification-sized jobs use batch size 1, short sequence lengths, bounded gradient accumulation, and explicit step limits.

Configuration is validated before queueing. Dataset, tokenizer, model references, and config are immutable after queueing. Non-finite loss or gradients cause controlled failure.

Resource limits are controlled by `BRUD_PRETRAINING_*` settings and are documented in `docs/development.md`.
