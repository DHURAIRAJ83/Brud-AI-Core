# PHASE 40 TOKENIZER QUALIFICATION REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 4 — Production SentencePiece Tokenizer  
**Engine:** `SovereignTokenizerTrainer` (`core_model/tokenizer/sovereign_tokenizer_trainer.py`)  

---

## 1. Tokenizer Specification & Architecture

| Parameter | Configuration | Verification Status |
| :--- | :--- | :--- |
| **Tokenizer Type** | SentencePiece BPE | Verified |
| **Normalization Rule** | `nmt_nfkc` | Verified |
| **Character Coverage** | 0.9995 | Preserves rare Tamil conjuncts |
| **Target Vocabulary** | ~32,000 (production target) | Configurable / Tested with pilot & candidate vocabularies |
| **Thread Concurrency** | 2 Workers (`num_threads=2`) | Matches host physical CPU core capacity |
| **Special Tokens** | `<pad>` (0), `<unk>` (1), `<bos>` (2), `<eos>` (3) | Verified IDs |
| **User Defined Symbols** | `<system>`, `<user>`, `<assistant>` | Verified IDs > 3 |

---

## 2. Multilingual Tokenization Evaluation

The tokenizer trainer evaluates unknown token (`<unk>`) rates across 4 linguistic categories:
1. **Tamil:** Clean segmentation of Unicode syllables and vowel markers.
2. **English:** Standard Latin subwords and root representations.
3. **Tanglish:** Romanized Tamil tokens represented with common subwords.
4. **Code-Switching:** Mixed Tamil-English technical phrases tokenized smoothly.

---

## 3. Artifact Manifest & Lineage

Every generated tokenizer bundle produces:
- `tokenizer.model`: Binary SentencePiece model file
- `tokenizer.vocab`: TSV vocabulary table
- `manifest.json`: Metadata document containing model SHA-256, vocab SHA-256, and evaluation metrics

### Tokenizer Safety Invariant:
The Phase 39 baseline tokenizer is **never overwritten** until the new tokenizer bundle completes validation, passes compatibility checks against `BrudModelConfig`, and is explicitly signed off.
