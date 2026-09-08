# Phase 58 Capability Coverage Repair Plan

**Workstream:** 14 — Capability Coverage Repair Plan  
**Timestamp:** 2026-08-30T17:55:00Z  
**Status:** ✅ GENERAL-PURPOSE CAPABILITY REPAIR MATRIX DEFINED (ZERO CONTAMINATION)

---

## 1. Governance Rule Against Contamination

Per Rule 1 and Rule 8, **no evaluation probe questions or answers may ever be copied directly into the training dataset**.

Instead, this plan specifies the **general-purpose linguistic and logical competencies** that must be augmented in future data curation so that the model learns generalizable skills rather than memorized test answers.

---

## 2. General Capability Augmentation Strategy

| Capability Cluster | Diagnostic Deficit Identified in Phase 57 | Permitted General-Purpose Training Data Augmentation |
|---|---|---|
| **Tamil Grammar & Syntax** | Model never saw singular/plural rule pairs | Curate standard school grammar patterns (`மரம் -> மரங்கள்`, `பழம் -> பழங்கள்`, `பூ -> பூக்கள்`) |
| **Bilingual QA / Definitions** | Glossaries formatted as static dictionaries | Format glossaries into question-answer dialogues (`X என்பதன் பொருள் என்ன? -> Y`) |
| **Arithmetic & Numerical Grounding** | Numbers were `<unk>` in tokenizer v1 | General elementary word problems exercising basic arithmetic (`5 + 9 = 14`, `100 - 20 = 80`) |
| **Logic & Deductive Syllogisms** | Only 8 flat logic records existed | Curate general categorical syllogisms (`All A are B; C is A; Therefore C is B`) |
| **Tanglish Normalization** | Tanglish records lacked standard Tamil targets | Curate parallel Tanglish-Tamil conversational pairs (`eppadi irukinga -> எப்படி இருக்கிறீர்கள்`) |
| **Adversarial & Refusal Guardrails** | Model had no concept of safety refusals | Curate standard refusal demonstrations for impossible or harmful requests |
| **Factual Knowledge Retrieval** | Classical Tamil couplets lacked biographical context | Curate general encyclopedic introductory sentences on prominent literary works |

---

## 3. Measurable Validation Targets

When implemented in future training, capability success will be evaluated using:
1. Target keyword presence in model generations.
2. 0% UNK emission.
3. Stable response coherence under greedy argmax decoding.
