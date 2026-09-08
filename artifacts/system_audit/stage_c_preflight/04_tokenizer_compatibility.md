# Stage C Pre-Flight Audit — 04: Tokenizer Compatibility Audit

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Tokenizer v2 Identification & Lock

```text
TOKENIZER_MODEL_PATH = data/tokenizers/versions/tok/v2/tokenizer.model
TOKENIZER_VOCAB_PATH = data/tokenizers/versions/tok/v2/tokenizer.vocab
TOKENIZER_MODEL_SHA  = 65342625ebb88eaab0996f0f6c5f3ef24ae9fd3203bc8377a0db353601e9ffd4
TOKENIZER_VOCAB_SHA  = 85edd38a52dcadab79e8141a5089b613e2e5523b8dfe71c3a9274f2d89f2a0ca
VOCAB_SIZE           = 1024
BYTE_FALLBACK        = ENABLED (100% UNK elimination)
```

---

## 2. Tokenizer Compatibility Across Context Lengths (T=128 vs T=512)

The Tokenizer v2 model is a subword BPE model trained via SentencePiece with byte fallback. Its vocabulary mapping (`vocab_size=1024`) is **independent of context sequence length ($T$)**.

| Property | T = 128 (Baseline) | T = 512 (E4 / E5 Target) | Compatibility Status |
|---|---|---|---|
| Vocabulary Size | 1024 tokens | 1024 tokens | ✅ Bit-for-bit identical |
| Special Tokens | `<pad>=0, <unk>=1, <s>=2, </s>=3` | `<pad>=0, <unk>=1, <s>=2, </s>=3` | ✅ Identical |
| Control Tokens | `<user>, <assistant>` | `<user>, <assistant>` | ✅ Identical |
| Multilingual UTF-8 Handling | NFC Normalized, Tamil virama clean | NFC Normalized, Tamil virama clean | ✅ Identical |
| Token ID Range | `[0, 1023]` | `[0, 1023]` | ✅ Identical |
| Max Sequence Encoding | Truncated at 128 tokens | Truncated at 512 tokens | ✅ Fully compatible |

---

## 3. Tokenizer Impact on Scaling

1. **No Tokenizer Retraining Required:** Tokenizer v2 remains 100% locked and frozen for E4 and E5.
2. **Padding & Truncation Hygiene:** In `build_dataloader`, sequences are padded to `max_seq=512` with label `-100` masking for prompt tokens and EOS (`3`) termination for responses.
3. **Byte Fallback Integrity:** Tamil script characters, Tanglish transliterations, and mixed English/Tamil tokens encode cleanly without generating `<unk>` tokens.
