# Phase 58 Benchmark Representability Report

**Workstream:** 4 — Benchmark Representability Audit  
**Timestamp:** 2026-08-30T17:33:00Z  
**Status:** ⚠️ AUDIT COMPLETE — 50% BENCHMARK STRUCTURAL FAILURE UNDER v1

---

## 1. Benchmark Representability Under Tokenizer v1

All 32 frozen evaluation probes (`artifacts/phase53_evaluation_manifest.json`) were audited against Tokenizer v1:

| Representability Status | Probe Count | Percentage | Description |
|---|---|---|---|
| **FULLY_REPRESENTABLE** | **0** | **0.0%** | Probes where prompt, answer, and all keywords have 0 UNKs |
| **PARTIALLY_REPRESENTABLE** | **16** | **50.0%** | Probes where at least 1 keyword has 0 UNKs, but prompt or answer contains UNKs |
| **NON_REPRESENTABLE** | **16** | **50.0%** | Probes where **ALL** keywords contain UNK, making scoring physically impossible |

---

## 2. UNK Breakdown in Benchmark Prompts & Answers (v1)

- **Probe Prompts (Input):** 418 UNK tokens out of 1,867 total tokens (**22.39% UNK**)
- **Expected Answers (Target):** 314 UNK tokens out of 1,395 total tokens (**22.51% UNK**)

---

## 3. Inventory of the 16 Non-Representable Probes

| Probe ID | Cluster | Target Keywords | Why Unrepresentable Under v1 |
|---|---|---|---|
| `ta_vocab_01` | `tamil_language` | `['பொருள்', 'நூல்', 'அகரமுதலி', 'அகராதி']` | `அ`, `ர`, `ப`, `ந`, `ூ` absent from v1 |
| `ta_grammar_02` | `tamil_language` | `['மரங்கள்']` | `ர`, `ங` absent from v1 |
| `ta_literature_03` | `tamil_language` | `['திருவள்ளுவர்', 'வள்ளுவர்']` | `ர`, `ள`, `ு` absent from v1 |
| `ta_proverb_04` | `tamil_language` | `['சேமிப்பு', 'பெரிய', 'பலன்', 'சிறு']` | `ச`, `ே`, `ப`, `ர`, `ற` absent from v1 |
| `ta_syntax_05` | `tamil_language` | `['புத்தகம்']` | `ப`, `ு` absent from v1 |
| `en_instruction_04` | `english_language` | `['solar', 'wind', 'hydro']` | `w`, `r` absent from v1 |
| `tgl_policy_01` | `tanglish_policy` | `['எப்படி', 'இருக்கிறீர்கள்']` | `எ`, `ப`, `ர` absent from v1 |
| `reasoning_arithmetic_01` | `reasoning` | `['14']` | Digits absent from v1 |
| `reasoning_analogy_04` | `reasoning` | `['school', 'classroom', 'college']` | `c` absent from v1 |
| `reasoning_epistemic_05` | `reasoning` | `['cannot', 'unknown', 'uncertain', 'impossible', 'future']` | `c`, `u`, `p` absent from v1 |
| `ground_context_01` | `grounding` | `['4,500', '4500', 'meters']` | Digits absent from v1 |
| `ground_distractor_03` | `grounding` | `['8841']` | Digits absent from v1 |
| `ground_multi_attribute_04` | `grounding` | `['mars', '2012', '899']` | Digits and `r` absent from v1 |
| `gen_explanation_02` | `generative` | `['scattering', 'wavelengths', 'blue', 'atmosphere']` | `c`, `w`, `b`, `u` absent from v1 |
| `gen_repetition_check_03` | `generative` | `['problem', 'code', 'communication']` | `p`, `c`, `u` absent from v1 |
| `gen_creative_tamil_04` | `generative` | `['நட்பு', 'நிழல்', 'உடன்']` | `ந`, `ட`, `ப`, `உ` absent from v1 |

**Target for Tokenizer v2:** All 32 probes must shift to **FULLY_REPRESENTABLE (0 UNK on keywords, 0 UNK on prompts)**.
