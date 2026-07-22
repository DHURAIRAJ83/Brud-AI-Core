# Tokenizer Corpus

Tokenizer corpora are generated only from ready or archived immutable dataset versions.

## Field extraction

- `pretrain`: primary text content.
- `instruction`: instruction, optional input, and output as separate lines.
- `chat`: user and assistant text as separate lines.
- `translation`: source and target text separately.
- `tanglish_pair`: Tanglish input, normalized Tamil input, and response separately.
- `safety` and `preference`: available relevant text fields separately.

Empty lines are excluded. Oversized lines are truncated only with recorded warnings.

## Determinism

Rows are read in dataset-version item order. Corpus files are UTF-8. The corpus manifest records line counts, character counts, language distribution, record-type distribution, warning counts, and SHA-256 checksum.

The same dataset version and corpus configuration produce the same corpus checksum.

## Storage

Corpus artifacts are written under the configured tokenizer corpus directory. Public APIs expose checksums and safe metadata, not absolute paths.
