# Phase 61 Report — 03: Multilingual Foundation Corpus Architecture

## Category Breakdown & Ratios (Target 50M Tokens)

| Category | Sub-Domains | Target Token Ratio | Token Volume | Purpose |
|---|---|---|---|---|
| **Tamil Prose & Lit** | Reference, News, Wiki, Literature, Edu | 35.0% | 17.5M Tokens | Foundation Tamil Syntax & Semantics |
| **English Technical/Edu** | Science, Math, Code, Reference | 30.0% | 15.0M Tokens | Analytical Reasoning & World Knowledge |
| **Tanglish (Latin Script)**| Colloquial, Phonetic, Social | 15.0% | 7.5M Tokens | Tanglish Phonetic Representation |
| **Mixed Code-Switching** | Tamil-English, Tamil-Tanglish | 10.0% | 5.0M Tokens | Natural Code-Switching Representation |
| **Structured Knowledge** | Definitions, Facts, QA Pairs | 10.0% | 5.0M Tokens | Factual Structure & Refusal Grounding |

### Strict Boundary Enforcement
1. **Foundation Pretraining Corpus:** Unlabeled & semi-structured text for self-supervised token prediction.
2. **Instruction / SFT Corpus:** Explicit `<user>` / `<assistant>` prompt-response pairs (Sealed E3-E split).
3. **RAG Corpus:** Searchable reference documents indexed for runtime retrieval (BM25 / Dense Vector).
4. **Evaluation Corpus:** Unseen benchmark probes (CAP-01 through CAP-24).
