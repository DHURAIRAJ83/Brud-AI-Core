# Phase 59 WS04 — Task Coverage & Difficulty Report

**Workstream:** 04 — Instruction-Following, Task Coverage & Capability Alignment Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **TASK COVERAGE FULLY AUDITED — QUALIFIED FOR CONTROLLED TRAINING**

---

## 1. Executive Summary

This report establishes the empirical audit of instruction task types, difficulty tiers, and prompt-following coverage for the Phase 59 candidate instruction dataset (`artifacts/candidates/phase59/phase59_instruction_records_v001.jsonl`). The primary objective of Phase 59 is proving that Brud-Small v2 achieves measurable instruction-following improvement. A rigorous task audit must distinguish between superficial keyword presence and genuine task supervision.

Recalculated directly from candidate artifacts, the dataset provides five (5) task types distributed across five (5) distinct difficulty tiers.

---

## 2. Quantitative Task Type Metrics

| Task Type | Record Count | Percentage | Raw Token Count | Supervised Tokens ($T=128$) | Avg Inst Chars | Avg Resp Tokens | Min Resp | Max Resp | Truncated Sequences |
|---|---|---|---|---|---|---|---|---|---|
| `definition_qa` | **203** | **51.3%** | 17,941 | 11,336 | 37.4 | 71.0 | 15 | 224 | 49 |
| `factual_explanation` | **148** | **37.4%** | 9,271 | 4,507 | 52.2 | 37.1 | 7 | 339 | 15 |
| `literature_explanation` | **35** | **8.8%** | 4,677 | 2,639 | 99.3 | 94.8 | 37 | 117 | 30 |
| `dialogue` | **7** | **1.8%** | 153 | 82 | 22.7 | 11.7 | 9 | 16 | 0 |
| `directive` | **3** | **0.8%** | 451 | 155 | 45.0 | 128.7 | 15 | 337 | 1 |
| **Total** | **396** | **100.0%** | **32,493** | **18,719** | **48.8** | **59.8** | **7** | **339** | **95** |

### Task Type Findings:
1. **Definition QA Dominance:** 51.3% of records focus on technical and sovereign definitions (e.g. `"பிளாக்செயின் (Blockchain) என்றால் என்ன?"`). This provides strong anchor supervision for terminology grounding.
2. **Factual Explanations:** 37.4% of records train factual answering across governance, agriculture, and general facts.
3. **Literature Commentaries:** 8.8% of records train structured literary interpretation of Thirukkural couplets.
4. **Dialogue & Directives:** Bounded representation (2.6% combined). These teach conversational greetings and multi-sentence passage extraction, but represent micro-curricula rather than conversational scale.

---

## 3. Five-Tier Difficulty Classification

Examples were classified into five (5) deterministic difficulty bands based on structural complexity, token length, multi-step logic, and reasoning constraints:

| Difficulty Tier | Description & Operational Criteria | Count | Percentage | Representative Source IDs | Dominant Languages |
|---|---|---|---|---|---|
| **Level 1** | **Lexical / Direct Lookup** (Concise definitions & single-turn greetings $< 25$ tokens) | **140** | **35.4%** | `rec_0014e36ae8c8`, `rec_062a0981c4f5`, `rec_071258c4ced1` | `mixed` (88), `en` (28), `ta` (22), `tgl` (2) |
| **Level 2** | **Simple Factual Explanation** (Single-sentence exposition, 25–60 tokens) | **130** | **32.8%** | `rec_008066d469df`, `rec_01dfe87bd0d2`, `rec_02ee5292594b` | `mixed` (82), `ta` (24), `en` (22), `tgl` (2) |
| **Level 3** | **Multi-Step Explanation** (Multi-sentence, annotated, or complex literature, 60–120 tokens) | **108** | **27.3%** | `rec_0074590514a2`, `rec_018a71cb8805`, `rec_01f0c06ad1d2` | `mixed` (98), `ta` (7), `en` (2), `tgl` (1) |
| **Level 4** | **Reasoning / Inference** (Formal reasoning domain, multi-step physics/CS rules) | **13** | **3.3%** | `rec_054cb4904308`, `rec_115aec6d5694`, `rec_1a0ec2f089a1` | `mixed` (10), `ta` (3) |
| **Level 5** | **Multi-Constraint Instruction** (Directives, summaries, translation instructions) | **5** | **1.3%** | `rec_60f43376a736`, `rec_8732b0c31fc7`, `rec_9336c54a18ba` | `en` (3), `ta` (2) |

---

## 4. Instruction-Following Coverage: "What" vs "How"

A critical distinction in instruction tuning is whether a dataset teaches:
- *"What to answer"* (domain knowledge memorization) vs
- *"How to follow an instruction"* (generalized behavioral compliance with query constraints).

### Audit Findings:
1. **Strong "What to Answer" Foundation:** 88.6% of records (`definition_qa` + `factual_explanation`) teach the model factual truth and domain definitions.
2. **Emergent "How to Follow" Supervision:**
   - Single-turn role boundary conditioning: `<assistant>` token triggers response mode.
   - Question-form variance: 252 unique prompt triggers condition distinct answers.
   - Format directives: Specific records require summaries, translations, greetings, and step-by-step problem definitions.
3. **Identified Gap:** The dataset has limited negative constraint instructions (e.g. *"Answer in exactly 3 words"*, *"Do not use the letter e"*). The future model will follow topical instructions well, but may not obey fine-grained negative constraints.

---

## 5. Task Coverage Verdict

**STATUS: PASS.** Task types and difficulty tiers are empirically quantified, well-stratified across Levels 1–3 (95.5%), and provide appropriate supervision for controlled Phase 59 learning.
