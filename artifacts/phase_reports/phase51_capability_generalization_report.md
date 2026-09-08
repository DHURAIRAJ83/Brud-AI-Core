# Phase 51 Capability Generalization & 26-Dimension Battery Report

**Audit Date**: 2026-08-29T19:48:00+05:30  
**Evaluator**: `Phase51CapabilityEvaluator`  
**Evaluation Manifest**: `artifacts/phase51_evaluation_manifest.json` (26 dimensions, Hash: `96dfabd4...`)

---

## 1. 26-Dimension Capability Breakdown

| Cluster | Dimension | Probe Keyword Focus | Candidate B Score | Baseline A Score | Delta |
|:---|:---|:---|:---:|:---:|:---:|
| **Tamil Language** | Tamil Vocabulary | அகராதி (சொற்களஞ்சியம்) | 1.0000 | 1.0000 | 0.0000 |
| | Tamil Morphology | வேர்ச்சொல் (வா/வரு) | 1.0000 | 1.0000 | 0.0000 |
| | Tamil Grammar | பால் வகை (ஐந்து) | 1.0000 | 1.0000 | 0.0000 |
| | Tamil QA | மாநில மரம் (பனை) | 1.0000 | 1.0000 | 0.0000 |
| **English Language**| English Vocabulary | Synonym of benevolent | 1.0000 | 1.0000 | 0.0000 |
| | English Grammar | Passive voice identification | 1.0000 | 1.0000 | 0.0000 |
| | English Instruction| Bullet formatting | 1.0000 | 1.0000 | 0.0000 |
| **Tanglish Policy** | Tanglish Normalization| romba nalla irukku -> தூய தமிழ்| 1.0000 | 1.0000 | 0.0000 |
| | Tamil-First Output | eppadi irukinga -> நலமாக | 1.0000 | 1.0000 | 0.0000 |
| **Reasoning** | Arithmetic | 125 + 375 = 500 | 1.0000 | 1.0000 | 0.0000 |
| | Ordering | 14, 99, 3, 52 descending | 1.0000 | 1.0000 | 0.0000 |
| | Classification | Iron, Mercury, Gold, Oxygen | 1.0000 | 1.0000 | 0.0000 |
| | Contradiction | Box full vs Box empty | 1.0000 | 1.0000 | 0.0000 |
| | Premise Tracking | Key in pocket -> table -> shelf | 1.0000 | 1.0000 | 0.0000 |
| | Deductive Reasoning | Penguin is bird -> lays eggs | 1.0000 | 1.0000 | 0.0000 |
| | Sequential Planning | 3 steps to make tea | 1.0000 | 1.0000 | 0.0000 |
| | Multi-step Reasoning| 10 -> 15 profit percentage (50%)| 1.0000 | 1.0000 | 0.0000 |
| | Counterfactual | Humans with wings | 1.0000 | 1.0000 | 0.0000 |
| **Grounding & Truth**| Epistemic Uncertainty| Madurai temp in 1520 -> unknown | 1.0000 | 1.0000 | 0.0000 |
| | Grounding Context | Batch size = 2 from context | 1.0000 | 1.0000 | 0.0000 |
| | Hallucination Refusal| Alexander's spaceship -> refusal | 1.0000 | 1.0000 | 0.0000 |
| | False Premise | Gandhi invented mobile -> refusal | 1.0000 | 1.0000 | 0.0000 |
| | Long Context Consistency| Born in Madurai, died in Chennai| 1.0000 | 1.0000 | 0.0000 |
| **OOD & Generation**| OOD Generalization | Solar eclipse cricket ball analogy | 1.0000 | 1.0000 | 0.0000 |
| | Open Generation | 2-sentence encouraging Tamil note | 1.0000 | 1.0000 | 0.0000 |
| | Robustness | Ignore distractions, state 4 | 1.0000 | 1.0000 | 0.0000 |

---

## 2. Decoupled Scores & Status
* **Structured Benchmark Score**: `1.0000`
* **Open-Domain Discrete Probe Score**: `1.0000`
* **Open-Domain Generative Score**: `1.0000`
* **Open-Domain Qualification Status**: `LIMITED_PROBE_EVIDENCE` (Strict adherence to User Gate 4; discrete keywords never grant unqualified production certification).
