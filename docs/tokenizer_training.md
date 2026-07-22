# Tokenizer Training

Phase 7 supports bounded local SentencePiece tokenizer training.

## Dry run

Dry run verifies:

- selected dataset version is immutable;
- corpus exists and checksum matches;
- corpus is non-empty;
- vocabulary size and character coverage are valid;
- special tokens are configured;
- SentencePiece is installed;
- tokenizer artifact directories are available.

Dry run never activates a tokenizer.

## Training behavior

Training writes temporary artifacts first, validates the generated `.model` and `.vocab`, verifies required special tokens, computes checksums, and then moves files into the registered tokenizer artifact directory. Successful training creates a staging tokenizer version, not an active one.

Partial artifacts are cleaned on failure where practical. Existing registered artifacts are not overwritten silently.

## Low-memory defaults

Defaults use one local thread, bounded corpus sizes, bounded line lengths, and no external downloads. Manual verification can use a small vocabulary when the sample corpus is small.
