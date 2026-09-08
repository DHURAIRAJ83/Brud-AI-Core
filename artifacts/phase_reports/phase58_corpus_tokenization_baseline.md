# Phase 58 Corpus Tokenization Baseline Report

**Workstream:** 3 — Authoritative Corpus Tokenization Audit  
**Timestamp:** 2026-08-30T17:30:00Z  
**Status:** ✅ BASELINE ESTABLISHED — 29.17% PRE-REPAIR UNK RATE

---

## 1. Corpus Scope & Character Statistics

The authoritative Phase 55 dataset (`artifacts/phase55_dataset_records_v001.jsonl`) contains:
- **Total Records:** 396
- **Total Raw Characters:** 61,221
- **Unique Characters:** **132**

### Detailed Breakdown of the 132 Unique Characters:
- **Tamil Characters (49):** `அ, ஆ, இ, ஈ, உ, ஊ, எ, ஏ, ஐ, ஒ, ஓ, ஔ, ஃ, க, ங, ச, ஞ, ட, ண, த, ந, ப, ம, ய, ர, ல, வ, ழ, ள, ற, ன, ா, ி, ீ, ு, ூ, ெ, ே, ை, ொ, ோ, ௌ, ், ஸ்ரீ, ௧, ௨, ௩, ௪, ௫`
- **English ASCII Letters (50):** 26 lowercase (`a-z`) + 24 uppercase (`A-Z`, excluding Q and Z in this corpus slice)
- **Numerical Digits (10):** `0, 1, 2, 3, 4, 5, 6, 7, 8, 9`
- **Punctuation & Whitespace (18):** Space, newline, `.` `,` `:` `;` `!` `?` `"` `'` `(` `)` `[` `]` `-` `_` `/` `\`
- **Mathematical & Symbolic Characters (5):** `=`, `+`, `>`, `|`, `^`

---

## 2. Tokenizer v1 Encoding Metrics on Phase 55 Corpus

| Metric | Measured Value |
|---|---|
| Total Generated Tokens | 50,037 tokens |
| Total `<unk>` Tokens (ID 1) | **14,594 tokens** |
| **Global Corpus UNK Rate** | **29.17%** |
| Training Split UNK Rate (316 records) | 29.17% (11,811 / 40,490) |
| Validation Split UNK Rate (40 records) | 29.15% (1,391 / 4,772) |
| Test Split UNK Rate (40 records) | 29.15% (1,392 / 4,775) |

---

## 3. Sub-Category UNK Rates Under v1

| Character Class | Estimated UNK Occurrence | Primary Defect |
|---|---|---|
| Numerical Digits | **100.0% UNK** | All 10 digits absent from v1 vocab |
| Tamil Consonants & Vowels | **~42.8% UNK** | 41 out of 49 Tamil characters absent from v1 vocab |
| English Letters | **~18.0% UNK** | 9 lowercase letters and all uppercase absent from v1 vocab |
| Punctuation & Symbols | **~35.0% UNK** | Parentheses, brackets, math operators absent from v1 vocab |

**Pre-Repair Baseline Established:** 29.17% UNK. This is the figure that Tokenizer v2 must reduce to 0.000%.
