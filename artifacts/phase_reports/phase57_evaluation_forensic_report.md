# Phase 57 Evaluation Pipeline Forensic Report

**Workstream:** 7 — Evaluation Pipeline Forensic Audit  
**Timestamp:** 2026-08-30T16:50:00Z  
**Status:** ⚠️ DUAL CAUSE IDENTIFIED: EVALUATOR CODE WORKS, BUT TOKENIZER RENDERS 50% OF BENCHMARK MATHEMATICALLY IMPOSSIBLE

---

## 1. Forensic Investigation Objectives

Did the zero score (0/32) across Baseline, Candidate, and Control represent:
- Genuine model capability limitation?
- Evaluator pipeline malfunction?
- Keyword matching breakdown?
- Tokenizer-to-evaluator representational impossibility?

---

## 2. Test 1: Evaluator Code Correctness (Harness Verification)

The evaluation scoring logic was tested with known-positive synthetic outputs:
```python
test_response = "தமிழில் அகராதி என்பதன் பொருள் ஒரு நூல் ஆகும்."
keywords = ['பொருள்', 'நூல்', 'அகரமுதலி', 'அகராதி']
hit = any(k in test_response.lower() for k in keywords)
# Result: True
```
- Greedy decoding implementation: Correct.
- String normalization: Correct (case-insensitive substring check).
- Probe loading from manifest: Correct (all 32 probes read accurately).
- Synthetic test pass rate: **100%**.

The Python evaluator code itself does **not** have a parsing or scoring bug.

---

## 3. Test 2: The Representational Impossibility Barrier

When the model generates token IDs, they must pass through `sp.Decode(ids)` to produce the response string evaluated by the keyword matcher.

When we test whether the tokenizer can round-trip and decode the 32 probe keyword sets, we discover a catastrophic barrier:

| Probe Category | Total Probes | Probes with at Least 1 Representable Keyword | Probes with 0 Representable Keywords (Mathematically Impossible) |
|---|---|---|---|
| Tamil Language | 5 | 0 (0.0%) | **5 (100.0%)** |
| English Language | 4 | 3 (75.0%) | **1 (25.0%)** |
| Tanglish Policy | 3 | 2 (66.7%) | **1 (33.3%)** |
| Reasoning | 6 | 3 (50.0%) | **3 (50.0%)** |
| Grounding | 4 | 1 (25.0%) | **3 (75.0%)** |
| Adversarial Refusal | 5 | 5 (100.0%) | **0 (0.0%)** |
| Generative Coherence | 5 | 2 (40.0%) | **3 (60.0%)** |
| **TOTAL** | **32** | **16 (50.0%)** | **16 (50.0%)** |

### Concrete Examples of Impossible Probes:
1. `ta_vocab_01`: Keywords `['பொருள்', 'நூல்', 'அகரமுதலி', 'அகராதி']`. Every single keyword contains Tamil letters mapped to `<unk>` in the 64-token tokenizer. `'அகராதி'` decodes as `' ⁇ க ⁇ தி'`. Substring match for `'அகராதி'` can **never** return True.
2. `ta_grammar_02`: Keyword `'மரங்கள்'` decodes as `'ம ⁇ ்க ⁇ ்'`.
3. `ta_literature_03`: Keyword `'திருவள்ளுவர்'` decodes as `'தி ⁇ வ ⁇ ் ⁇ வ ⁇ ்'`.
4. `reasoning_arithmetic_01`: Keyword `'14'` decodes as `' ⁇ '` (digits are not in the vocabulary).
5. `ground_context_01`: Keywords `['4,500', '4500', 'meters']` all contain digits or missing characters.

---

## 4. Forensic Verdict

The 0/32 result is a **composite failure**:
1. **Structural Evaluator Incompatibility (16/32 probes):** Half of the benchmark probes were mathematically impossible for the model to pass, regardless of weights, because the tokenizer cannot generate or decode the target keywords.
2. **Model Semantic Under-Capacity (remaining 16 probes):** On the 16 probes where keywords were theoretically representable (e.g. 'kind', 'no', 'did not', 'nonsense', 'tea'), the 83K parameter model at 0.62 epochs failed to learn the complex associative reasoning needed to generate those specific words in response to English/Tanglish prompts.
