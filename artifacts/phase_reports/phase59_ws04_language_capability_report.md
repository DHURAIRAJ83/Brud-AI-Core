# Phase 59 WS04 — Language Capability & Code-Switching Report

**Workstream:** 04 — Instruction-Following, Task Coverage & Capability Alignment Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **LANGUAGE CAPABILITY AUDITED — QUALIFIED WITH DOCUMENTED TANGLISH LIMITATION**

---

## 1. Executive Summary

This report establishes the linguistic capability and bilingual code-switching audit across Tamil (`ta`), English (`en`), Tanglish (`tgl`), and Mixed Tamil/English (`mixed`) in the Phase 59 candidate instruction dataset (`artifacts/candidates/phase59/phase59_instruction_records_v001.jsonl`).

Brud AI is architected as a sovereign Tamil-first model. Capability alignment requires verifying that the dataset actively supervises native Tamil script, bilingual technical terminology, and English grounding without linguistic collapse or artificial data generation.

---

## 2. Language Capability Cross-Section

| Language Track | Record Count | Percentage | Supervised Tokens | Task Diversity | Domain Diversity | Lexical Richness | Measured UNK Rate |
|---|---|---|---|---|---|---|---|
| **Mixed (Bilingual)** | **278** | **70.2%** | **15,743** | 4 tasks | 18 domains | 3,412 unique words | **0.0000%** |
| **English (`en`)** | **57** | **14.4%** | **1,527** | 4 tasks | 10 domains | 894 unique words | **0.0000%** |
| **Tamil (`ta`)** | **56** | **14.1%** | **1,376** | 4 tasks | 9 domains | 912 unique words | **0.0000%** |
| **Tanglish (`tgl`)** | **5** | **1.3%** | **73** | 1 task | 2 domains | 58 unique words | **0.0000%** |
| **Total** | **396** | **100.0%** | **18,719** | **5 tasks** | **19 domains** | **4,141 words** | **0.0000%** |

---

## 3. Detailed Language Audits

### 1. Tamil Language Capability (`ta` & `mixed` - 335 records)
- **Script Coverage:** 84.6% of records contain native Tamil Unicode characters (`\u0b80` to `\u0bff`).
- **Linguistic Breadth:** Spans classical Sangam literature, Thirukkural couplets, modern governance notices, and grammatical rules (case endings, verb tenses).
- **Subword Encoding:** Tokenizer v2 encodes complex Tamil conjuncts (e.g. `"ஸ்ரீ"`, `"க்ஷ்"`, `"ஔ"`) with 0 UNK tokens.

### 2. English Language Capability (`en` & `mixed` - 391 records)
- **Alphabet Coverage:** 98.7% of records contain English characters, primarily representing technical terminology in bilingual records and pure English QA in 57 records.
- **Syntactic Structures:** Well-formed standard English sentences in factual directives, scientific definitions, and dialogue.

### 3. Tanglish Language Audit (`tgl` - 5 records)
- **Sample Count:** Exactly 5 records (1.3% of the dataset).
- **Phonetic Representation:** Romanized Tamil phonetics (e.g. `"Indha vaaram"`, `"pathi sollunga"`).
- **Limitation Finding (`LIM-WS04-01`):** While Tokenizer v2 representability is 100% (0 UNK), 5 examples constitute a micro-demonstration of tokenization compatibility, **NOT** sufficient training data to claim broad, fluent Tanglish conversational capability.
- **Policy Compliance:** In accordance with Section 06 directives ("Do not invent additional Tanglish data"), these 5 examples are preserved without synthetic expansion.

---

## 4. Bilingual Code-Switching & Terminology Analysis

The 278 `mixed` records represent the natural linguistic reality of modern technical communication in Tamil Nadu. The audit identified four primary code-switching modalities:

1. **Parenthetical Technical Grounding (124 records):**
   - Tamil concept accompanied by parenthetical English term:
   - Example: `"பிளாக்செயின் (Blockchain): மாற்ற முடியாத, பரவலாக்கப்பட்ட..."`
   - Example: `"செயற்கை நுண்ணறிவு (Artificial Intelligence): மனித அறிவாற்றலைப் போன்ற..."`
2. **Tamil Explanations of English Technical Paradigms (72 records):**
   - Pure English prompt paired with bilingual explanation or Tamil technical definition.
3. **Embedded English Loanwords in Tamil Sentences (58 records):**
   - English technical terms integrated into Tamil grammatical case structures:
   - Example: `"API மூலம் தரவு பரிமாற்றம் செய்யப்படுகிறது."`
4. **Bilingual Conversational Directives (24 records):**
   - Directives testing code-switched comprehension.

---

## 5. Language Verdict

**STATUS: QUALIFIED WITH LIMITATIONS.** Tamil, English, and bilingual code-switching are strongly supported. Tanglish is qualified for representability only, with conversational fluency formally designated as a documented limitation (`LIM-WS04-01`).
