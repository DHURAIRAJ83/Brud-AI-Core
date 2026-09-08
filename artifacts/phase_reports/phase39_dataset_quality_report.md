# Phase 39 — Dataset Quality Pipeline & Splitting Report

## 1. Quality Filters & Screening Rules
1. **UTF-8 & Unicode Normalization**: NFC Unicode normalization; rejection of unparseable byte sequences.
2. **Empty & Malformed Records**: Stripping whitespace; filtering records shorter than minimum token length.
3. **Deduplication**: Exact hash match and near-duplicate detection via MinHash/n-gram indexing.
4. **PII & Secret Detection**: Screening for API keys (`sk-`, tokens, private keys, passwords).
5. **Prompt Injection Screening**: Screening against known injection prefixes and malicious system override attempts.
6. **Garbage & Repetition**: Rejection of high-entropy gibberish and repeating character loops.

---

## 2. Deterministic Train / Validation / Test Splitting
- **Split Ratio**: 80% Train / 10% Validation / 10% Test.
- **Leakage Prevention**: Verified zero intersection across token sets (`train ∩ val == ∅`, `train ∩ test == ∅`, `val ∩ test == ∅`).
- **Benchmark Isolation**: Phase 38 fixed evaluation fixtures (`phase11-fixed-eval-v1`) strictly excluded from all training partitions.
