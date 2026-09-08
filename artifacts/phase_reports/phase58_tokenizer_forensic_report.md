# Phase 58 Active Tokenizer Forensic Report

**Workstream:** 2 — Active Tokenizer Forensic Audit  
**Timestamp:** 2026-08-30T17:28:00Z  
**Status:** ⚠️ FORENSIC COMPLETE — v1 STRUCTURAL FAILURE QUANTIFIED

---

## 1. Tokenizer v1 Specifications

- **Model Path:** `data/tokenizers/versions/tok/v1/tokenizer.model`
- **Algorithm:** SentencePiece BPE
- **Vocabulary Size:** **64 tokens**
- **Character Coverage Setting:** Default heuristic (~0.9995 with insufficient training data)
- **Byte Fallback:** Disabled (`byte_fallback=False`)
- **Special Token Registry:**
  - `PAD`: ID `0` (`<pad>`)
  - `UNK`: ID `1` (`<unk>`)
  - `BOS`: ID `2` (`<bos>`)
  - `EOS`: ID `3` (`<eos>`)
  - Reserved symbols: IDs `4..10` (`<system>`, `<user>`, `<assistant>`, `<ta>`, `<en>`, `<tgl>`, `<mixed>`)

---

## 2. Complete Inventory of the 64 v1 Tokens

```
ID  0: <pad>      ID 16: an         ID 32: ed         ID 48: g
ID  1: <unk>      ID 17: gl         ID 33: ix         ID 49: k
ID  2: <bos>      ID 18: is         ID 34: தம         ID 50: m
ID  3: <eos>      ID 19: கம         ID 35: ழ்         ID 51: s
ID  4: <system>   ID 20: க்         ID 36: ▁m         ID 52: ண
ID  5: <user>     ID 21: வண         ID 37: ▁          ID 53: வ
ID  6: <assistant>ID 22: ish        ID 38: l          ID 54: E
ID  7: <ta>       ID 23: கம்        ID 39: a          ID 55: S
ID  8: <en>       ID 24: ▁வண        ID 40: h          ID 56: d
ID  9: <tgl>      ID 25: glish      ID 41: ்          ID 57: t
ID 10: <mixed>    ID 26: க்கம்      ID 42: e          ID 58: v
ID 11: el         ID 27: ▁வணக்கம்    ID 43: க          ID 59: x
ID 12: lo         ID 28: En         ID 44: i          ID 60: y
ID 13: ▁h         ID 29: Sa         ID 45: n          ID 61: த
ID 14: ello       ID 30: ak         ID 46: o          ID 62: ழ
ID 15: ▁hello     ID 31: am         ID 47: ம          ID 63: ி
```

---

## 3. Forensic Assessment: What Was Missing

1. **Entire Numerical System Omitted:** Digits `0, 1, 2, 3, 4, 5, 6, 7, 8, 9` are completely missing. All numbers map to `<unk>`.
2. **Major Tamil Alphabet Omitted:** Only 8 base Tamil characters are present (`க`, `த`, `ம`, `ண`, `வ`, `ழ`, `ி`, `்`). Basic letters such as `அ` (first letter of Tamil), `ர`, `ப`, `ச`, `ள`, `ய`, `ல`, `ந`, `ட`, `ற` are absent.
3. **Core English Letters Omitted:** `b`, `c`, `f`, `j`, `p`, `q`, `u`, `w`, `z` are absent. Words like `"water"`, `"blue"`, `"cup"`, `"apple"` cannot be tokenized.
4. **No Byte Fallback:** Without byte fallback, any unindexed character instantly collapses into token `1` (`<unk>`).

**Conclusion:** Tokenizer v1 was trained on an extreme micro-toy toy prompt rather than a complete alphabet. It is fundamentally incapable of general text representation.
