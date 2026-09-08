# Phase 39 — SentencePiece Tokenizer Report

## 1. Tokenizer Configuration & Target Architecture
- **Model Type**: SentencePiece BPE (Byte-Pair Encoding).
- **Target Vocab Size**: ~32,000 tokens for production corpus; scaled dynamically for smaller test corpora.
- **Special Tokens**:
  - `pad_id`: 0 (`<pad>`)
  - `bos_id`: 1 (`<bos>`)
  - `eos_id`: 2 (`<eos>`)
  - `unk_id`: 3 (`<unk>`)
  - User-defined symbols: `<system>` (id 4), `<user>` (id 5), `<assistant>` (id 6).

---

## 2. Multi-Language Tokenization & Artifact Manifest
- **Tamil Coverage**: Subword decomposition for agglutinative Tamil morphology.
- **English Coverage**: Standard BPE segmentation.
- **Tanglish & Code-Switching**: Tokenized without unknown token explosion.
- **Artifact Manifest**:
  - `tokenizer.model`: SHA-256 verified.
  - `tokenizer.vocab`: Vocabulary mapping table.
  - `manifest.json`: Checksum and training corpus lineage.
