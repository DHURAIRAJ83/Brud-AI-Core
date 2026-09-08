# Stage C Pre-Flight Audit — 09: E4/E5 Evaluation Strategy

**Audit Date:** 2026-09-01  
**Audit Context:** Phase 60 WS07 Stage C Pre-Flight  
**Governance Mode:** STRICT READ-ONLY, ZERO MUTATION (`training_execution_authorized = FALSE`)

---

## 1. Scientific Principles & Dual-Evaluation Mandate

To ensure complete scientific integrity, Stage C evaluation enforces strict separation between raw model weight quality and decoding assistance:

$$\text{LOSS REDUCTION} \neq \text{FUNCTIONAL CAPABILITY}$$
$$\text{DECODING CONTROLS} \neq \text{WEIGHT INTELLIGENCE}$$

Every checkpoint evaluated during Stage C (E4 and E5) MUST be probed under **two independent evaluation modes**:

1. **Mode A — Raw Weights (Unassisted Evaluation):**
   - Greedy decoding (`temperature = 0.0`)
   - Repetition penalty $\theta = 1.0$ (disabled)
   - No-repeat n-gram = 0 (disabled)
   - Measures raw language model probability distribution and unassisted repetition propensity.

2. **Mode B — Controlled Inference (Production Decoding):**
   - Temperature sampling (`temperature = 0.7`, `top_k = 20`)
   - Repetition penalty $\theta = 1.25$
   - No-repeat 3-gram filter (`no_repeat_ngram_size = 3`)
   - Measures functional usability when deployed behind production decoding controls.

---

## 2. Comprehensive 24 Capability Probe (CAP-01 to CAP-24) Suite

The evaluation suite tests all 24 standardized capability probes:

| Category | Probe Range | Description | Success Target (Raw) | Success Target (Controlled) |
|---|---|---|---|---|
| **Tamil Language** | CAP-01 to CAP-06 | Grammaticality, inflection, script purity, virama integrity | > 30% | > 60% |
| **English Language** | CAP-07 to CAP-10 | Vocabulary, syntax, instruction following | > 40% | > 70% |
| **Tanglish Language** | CAP-11 to CAP-14 | Script transliteration, phonetic consistency | > 35% | > 65% |
| **Bilingual Translation** | CAP-15 to CAP-18 | Tamil $\leftrightarrow$ English, Tamil $\leftrightarrow$ Tanglish pairs | > 25% | > 50% |
| **RAG & Context** | CAP-19 to CAP-21 | Fact retrieval, context grounding ($T=512$) | > 30% | > 55% |
| **Tools & Memory** | CAP-22 to CAP-24 | Tool dispatch formatting, consent-gated memory recall | > 50% | > 85% |

---

## 3. Metrics Matrix

For every evaluation run, the evaluator outputs:
- **Validation Loss:** Cross-entropy loss on validation split.
- **CAP Pass Rate (Raw):** Percentage of 24 CAP probes passed without decoding assistance.
- **CAP Pass Rate (Controlled):** Percentage passed with $\theta=1.25$ + 3-gram.
- **3-Gram Repetition Ratio:** Percentage of generated sequences containing repeating 3-grams (Target: $< 0.05$).
- **EOS Emission Rate:** Percentage of generations that naturally emit token `3` before max tokens (Target: $> 0.90$).
- **Multi-Turn Recall Rate:** Accuracy on retrieving facts from turn 1 when prompted at turn 6 ($T=512$).
