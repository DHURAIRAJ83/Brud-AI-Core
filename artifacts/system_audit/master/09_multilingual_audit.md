# Master Brud AI System Audit — 09: Multilingual Capability Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal NLP Architect & Multilingual Systems Specialist  
**Confidence Rating:** HIGH CONFIDENCE (Verified by tokenizer vocab, routing heuristics, and model probe outputs)  

---

## 1. Multilingual Support Breakdown: Separation of Capabilities

To avoid conflating distinct NLP capabilities, this audit strictly separates:
- **Detection / Classification:** Identifying language category from raw input.
- **Transliteration:** Converting between Tamil script and Latin-script Tanglish.
- **Translation:** Transferring meaning across languages.
- **Understanding:** Extracting intents, facts, and entities from prompts.
- **Generation:** Synthesizing coherent, fluent output text.

| Language Dimension | Detection / Routing | Normalization / Transliteration | Understanding | Translation | Generation (Neural Weights) |
|---|---|---|---|---|---|
| **Tamil (ta)** | ✅ **ROBUST** (Unicode script ratio $\ge 15\%$) | ✅ **ROBUST** (NFC normalization, zero-width strip) | 🟡 **MODERATE** (Keyword & intent matching) | 🟡 **RULE-BASED** (10-concept lexicon in E3 engine) | 🔴 **WEAK** (Repetition 0.51–0.90 in raw weights; 0.0000 with decoding controls) |
| **English (en)** | ✅ **ROBUST** (Latin script without Tanglish tokens) | ✅ **ROBUST** (Standard NFKC / ASCII) | 🟡 **MODERATE** (Heuristic matching & RAG) | 🟡 **RULE-BASED** (10-concept lexicon in E3 engine) | 🔴 **WEAK** (528k parameter model generates simple phrases only) |
| **Tanglish (tgl)** | ✅ **ROBUST** (Latin script + 32-word Tanglish lexicon) | ✅ **ROBUST** (Canonical phonetic map, e.g. `ammaa` -> `amma`) | 🟡 **MODERATE** (Maps to Tamil intents via normalizer) | 🟡 **RULE-BASED** (Phonetic engine in E3 engine) | 🔴 **WEAK** (Severely fragmented in raw weights) |
| **Mixed (ta + en)** | ✅ **ROBUST** (Both Tamil & Latin $\ge 15\%$) | ✅ **ROBUST** (Bilingual token separator) | 🟡 **MODERATE** (Extracts both Tamil and English slots) | 🟡 **RULE-BASED** (Bilingual pair templates in E3) | 🔴 **WEAK** (Grammar blending often causes repetition) |

---

## 2. Deep Dive into Linguistic Subsystems

### A. Language Detection (`core_model/rag/language_routing.py`)
- Uses deterministic Unicode block counting:
  - Tamil block: `\u0B80` to `\u0BFF`.
  - Latin block: `\u0041` to `\u007A`.
- If both are present above 15% threshold $\to$ `"mixed"`.
- If only Latin is present, checks against `DEFAULT_TANGLISH_LEXICON` (32 high-frequency conversational markers: *vanakkam, eppadi, irukku, nalla, sapteengala, etc.*). If hits found $\to$ `"tgl"`, otherwise `"en"`.
- **Verdict:** Deterministic, fast, and 100% test-verified.

### B. Tokenization (`core_model/tokenization/tokenizer_v2.py`)
- Vocabulary size: Exactly **1,024** tokens.
- BPE merges trained specifically to capture Tamil consonant-vowel combinations (*uyirmei* syllables) alongside standard English subwords.
- Byte-fallback mechanism ensures zero out-of-vocabulary (`<unk>`) crashes on emojis or unseen Unicode characters.
- **Limitation:** At 1,024 tokens, English words often fragment into multiple 2-to-3 character pieces, requiring more tokens per sentence compared to a 32k or 50k tokenizer.

### C. Translation & Transliteration Engine (`core_model/admin_assistant/dataset_expansion_engine.py`)
- **Transliteration:** Phonetic mapping dictionary converts Tamil words to canonical Tanglish (`அம்மா` $\to$ `amma`, `வீடு` $\to$ `veedu`).
- **Polysemy Discrimination:** Context-aware disambiguation rules for polysemic Tamil words:
  - `பால்`: Discriminates between milk (dairy) and gender (grammar) based on co-occurring tokens (`குடி` vs `ஆண்/பெண்`).
  - `படி`: Discriminates between study (verb), step/stair (noun), and measure (quantity).
  - `திங்கள்`: Discriminates between Monday (day) and Moon/Month (astronomy/calendar).
- **Critical Caveat:** This engine is **rule-based** for a curated set of concepts. It is not an open-domain neural translator.
