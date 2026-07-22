# Pretraining Dataset Stream

Training reads only the train split from a ready or archived dataset version. Validation reads only the validation split.

The stream is deterministic:

- dataset items are read by stored sequence number;
- record text fields are canonicalized by record type;
- token blocks are packed deterministically;
- final partial batches are padded;
- labels ignore padded targets.

Phase 9 uses bounded registered tokenizer compatibility metadata for service validation. The current local test stream uses deterministic token IDs for tiny fixtures; production-quality tokenizer-backed streaming is a Phase 10 hardening target.

Oversized sequences follow the explicit configured policy. Silent truncation is not allowed.
