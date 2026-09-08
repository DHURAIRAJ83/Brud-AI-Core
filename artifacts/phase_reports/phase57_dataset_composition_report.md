# Phase 57 Dataset Composition Report

**Workstream:** 9 — Dataset Composition Analysis  
**Timestamp:** 2026-08-30T16:55:00Z  
**Status:** ⚠️ HIGH GLOSSARY DENSITY & INSUFFICIENT INSTRUCTION-FOLLOWING PROPORTION IDENTIFIED

---

## 1. Domain Distribution of Training Split (316 Records, 12,277 Tokens)

| Domain | Records | Tokens | % of Training Tokens | Nature of Content |
|---|---|---|---|---|
| `vocabulary` | 87 | 2,157 | 17.6% | Word definitions, bilingual glossaries |
| `thirukkural` | 30 | 2,264 | 18.4% | Classical 2-line Tamil couplets + commentaries |
| `literature` | 30 | 1,249 | 10.2% | Literary excerpts, author bios |
| `general` | 35 | 841 | 6.9% | Miscellaneous facts, cultural notes |
| `agriculture` | 10 | 845 | 6.9% | Farming techniques, crops |
| `computer_science` | 8 | 805 | 6.6% | Tech definitions, Python descriptions |
| `reasoning` | 8 | 768 | 6.3% | Logic puzzles, deductive statements |
| `science` | 8 | 751 | 6.1% | Biology, chemistry, photosynthesis |
| `grammar` | 8 | 730 | 5.9% | Tamil grammatical rules |
| `linguistic_pretraining` | 57 | 413 | 3.4% | Character & subword sequences |
| `government` | 14 | 357 | 2.9% | Civic terms, administrative structures |
| `poem` | 2 | 321 | 2.6% | Poetry verses |
| `instruction_following` | 4 | 254 | **2.1%** | Explicit prompt-response instructions |
| `public_domain` | 9 | 198 | 1.6% | Archival public notices |
| `animal_facts` | 1 | 176 | 1.4% | Descriptive biology facts |
| `children` | 2 | 102 | 0.8% | Nursery rhymes |
| `health_general` | 1 | 31 | 0.3% | Hygiene sentence |
| `synthetic_dialogue` | 2 | 15 | **0.1%** | Conversational dialogue turns |
| **TOTAL** | **316** | **12,277** | **100.0%** | — |

---

## 2. Structural Format Breakdown

- **Glossary / Dictionary / Factoid Style:** 222 records (**70.3%** of training data). Consists of static declarative facts (e.g. `English word : Tamil word` or `Word (Meaning): definition`).
- **Classical Literature / Thirukkural:** 62 records (**19.6%**). Heavy classical poetic phrasing.
- **Instruction-Following / Question-Answering:** Only 11 records (**3.5%**).
- **Multi-turn Dialogue:** 2 records (**0.1%**).

---

## 3. The Composition Bottleneck

The 32 evaluation probes are formulated as **direct questions and prompt directives**:
- *"தமிழில் 'அகராதி' என்பதன் பொருள் என்ன?"* (Direct Question)
- *"Convert the following active sentence into passive voice:"* (Directive)
- *"If all metals conduct electricity and copper is a metal, does copper conduct electricity?"* (Hypothetical reasoning query)

However, **96.5% of the training corpus consists of flat declarative text, dictionary entries, and classical couplets**. Causal language modeling on this text teaches the model how to continue dictionary entries or couplets, but **never teaches it that a question mark `?` implies generating an answer rather than repeating characters**.

**Conclusion:** The Phase 55 corpus qualified on token scale (>10K approved tokens), but its structural composition lacks the instruction/dialogue density required to instill zero-shot question-answering capabilities.
