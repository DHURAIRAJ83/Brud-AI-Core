# Master Brud AI System Audit — 05: Dataset & Data Engine Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal Data Architect & Scientific Auditor  
**Confidence Rating:** HIGH CONFIDENCE (Verified by direct JSONL inspect, line counts, and SHA-256 hashes)  

---

## 1. Master Dataset Inventory

| Dataset Identifier | Version | Records | Languages | Sources | Provenance Class | SHA-256 Hash | Synthetic Ratio | Contamination Status |
|---|---|---|---|---|---|---|---|---|
| **Phase 53 Benchmark** | v1.0 | 500 | ta, en | Air-gapped Eval Set | Human Authored | `554bf72317d9...` | 0.0% | Strictly Air-gapped (Zero leak) |
| **Phase 55 Corpus** | v1.0 | 10,000 | ta | Clean Tamil Corpus | Curated Human Web | `3e1481c3279c...` | 0.0% | Certified Clean |
| **Phase 60 WS03 Dataset** | v001 | 2,000 | ta (97.7%), en (2.3%) | Cleaned Phase 55 + SFT | Curated Human + Templates | `f682ddf82e75...` | 15.0% | 0.0% overlap with Phase 53 |
| **Phase 60 WS03 Quarantine**| v001 | 12 | corrupted / noisy | Discarded records | Corrupted | `7f4153b82103...` | N/A | Excluded from training |
| **WS07 E3 Sealed Dataset** | v001 | 88 | ta, en, tgl, mixed | Admin Assistant Engine | Human-Reviewed AI Proposals | `cb1387ebc92c...` | 100% Governed Synthetic | Air-gapped, NFC Validated |
| **E3-A Train Set** | exp-a | 725 | ta (100%) | WS03 Tamil slice | Curated Human | Dynamic Split | 0.0% | 0.0% leak |
| **E3-B Train Set** | exp-b | 1,436 | ta (50.5%), en (49.5%) | WS03 + English SFT | Curated + Template | Dynamic Split | 12.5% | 0.0% leak |
| **E3-C Train Set** | exp-c | 1,647 | ta, en, tgl | WS03 + En + Tanglish | Curated + Transliterated | Dynamic Split | 23.7% | 0.0% leak |
| **E3-D Train Set** | exp-d | 2,072 | ta, en, tgl, mixed | WS03 + En + Tgl + Mixed | Curated + Bilingual | Dynamic Split | 39.3% | 0.0% leak |
| **E3-E Train Set** | exp-e | 2,088 | ta, en, tgl, mixed | WS03 + E3 Multi-Turn QA | Balanced Multilingual | Dynamic Split | 40.0% (Cap: 8:1) | 0.0% leak |

---

## 2. Admin Assistant Dataset Expansion Capability & Safety

### A. Can the Admin Assistant Safely Expand Data?
**YES, under strict architectural constraints:**
1. **Synthetic Ratio Bound:**
   - Enforced by `MAX_SYNTHETIC_RATIO = 8.0` (synthetic records cannot exceed 8x the approved human anchor records).
   - In E3-E, synthetic and expanded pairs contributed 363 records to an anchor base of 1,725 human records (~21% of the total dataset), well below the safety ceiling.
2. **Quality Gates Enforced in Code (`dataset_expansion_validator.py`):**
   - Unicode NFC normalization enforced.
   - Zero-width character stripping (`\u200B`, `\u200C`, `\u200D`).
   - Tamil virama validity (no orphaned pulli `\u0BCD`).
   - Script ratio checks (Tamil $\ge 15\%$, Latin $\ge 15\%$ for mixed).
   - Contamination check: Air-gap match against Phase 53 held-out benchmark.
3. **Admin Review Queue:**
   - Proposals are generated with status `PENDING`.
   - Never injected into training until explicitly transitioned to `APPROVED` by an authenticated human admin.

### B. What the Data Engine CANNOT Do Today:
- **It cannot automatically scrape and clean the live web.** There is no automated crawler or web scraper pipeline in `core_model/admin_assistant/`.
- **It cannot generate open-domain general knowledge translations.** Translations are currently limited to the 10 core bilingual anchor concepts defined in `TAMIL_ENGLISH_LEXICON`.
