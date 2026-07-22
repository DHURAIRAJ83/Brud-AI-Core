# Tokenizer Architecture

Phase 7 introduces a local tokenizer foundation for Tamil, English, Tanglish, and mixed-language data.

## Library choice

Brud AI uses SentencePiece through the `sentencepiece` Python package. It supports `bpe` and `unigram`; BPE is the default because it is predictable and works well for small local validation runs.

## Special tokens

The fixed Phase 7 policy is:

```text
<pad>, <unk>, <bos>, <eos>, <system>, <user>, <assistant>, <ta>, <en>, <tgl>, <mixed>
```

`pad`, `unk`, `bos`, and `eos` are assigned stable IDs through SentencePiece trainer configuration. The remaining symbols are registered as user-defined symbols.

## Tamil policy

Tokenizer training uses UTF-8 corpus files and does not transliterate Tamil. The selected SentencePiece normalization is documented in each tokenizer version configuration and is smoke-tested so Tamil text can encode and decode without corruption.

## Boundaries

The tokenizer is not connected to the public chatbot in Phase 7. No core model architecture, language-model pretraining, RAG, or external provider is implemented.
