# Phase 60 WS01 — Post-Training Diagnostic & Capability Gap Baseline Report

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS01 — Post-Training Diagnostic & Capability Gap Baseline  
**Date:** 2026-08-31  
**Status:** ✅ **POST-TRAINING DIAGNOSTIC COMPLETE WITH LIMITATIONS (VERDICT B)**  
**Training Authorization:** **STRICTLY BLOCKED** (Diagnostic and design phase only)  
**Production Promotion:** **NOT AUTHORIZED (0.0% PUBLIC TRAFFIC)**

---

## 1. Executive Summary

Following the completion of the Phase 59 controlled instruction-tuning campaign (Verdict B), Phase 60 Workstream 01 conducted a comprehensive scientific and diagnostic audit of the trained candidate model (`artifacts/candidates/phase59/checkpoints/checkpoint_best.pt`, step 100).

The objective is to establish an unvarnished, empirical baseline of model capabilities, diagnose root causes of failure across 24 capability dimensions, analyze model capacity and training duration boundaries, and formulate the dataset expansion design required before authorizing any future training campaign.

---

## 2. Answers to Ten Primary Scientific Questions

### 1. Which capabilities actually improved after Phase 59 training?
- **Cross-Entropy Language Modeling Density:** Validation loss improved from 7.0738 to 6.4102 (-0.6636, -9.38%), and unseen held-out test loss improved from 7.0943 to 6.4253 (-0.6690, -9.43%).
- **Token Distribution Concentration:** The model shifted from generating high-entropy random uniform byte noise to concentrating probability mass on valid subwords and punctuation.

### 2. Which capabilities remain unsupported?
- All 24 semantic and instruction capabilities (factual QA, multi-step reasoning, dialogic turn-taking, structured output, arithmetic, summarization, entity extraction, safe refusal) remain unsupported for task execution. The model predominantly outputs frequent punctuation (`.`) or short syllables (`ழe`).

### 3. Which failures are caused by insufficient data coverage?
- **Zero-record capabilities (10 dimensions):** Arithmetic/Numerical (CAP-14), Structured Response (CAP-16), Safe Refusal (CAP-18), Multi-turn Context (CAP-19), Summarization (CAP-21), Translation (CAP-22), Entity Extraction (CAP-23), Tool-use Boundary (CAP-24).
- **Severe scarcity (4 dimensions):** Tanglish (CAP-10, 5 records), Dialogue (CAP-05, 7 records), Directive Following (CAP-06, 3 records), Instruction Following (CAP-04, 10 records).

### 4. Which failures are caused by model capacity/context limitations?
- At 528,128 parameters ($d=128, L=2, h=4, d_{\text{ff}}=256$), parametric memory is bounded. While sufficient for basic grammar, tone matching, and narrow classification, it cannot memorize vast open-domain encyclopedic facts without external grounding.
- Context length $T=128$ tokens restricts multi-turn context (CAP-19) and long-form document summarization (CAP-21).

### 5. Which failures are caused by tokenizer/formatting?
- Tokenizer v2 (1,024 vocab) is technically sound (0.0000% UNK, 100% roundtrip), but character/subword decomposition in Tamil requires 2–4 subword pieces per word, consuming sequence length rapidly.

### 6. Which failures are caused by insufficient training duration?
- 100 steps (gradient accumulation 2 = 200 sequences seen out of 316 examples) is less than one full epoch. Training stopped while validation loss was still declining smoothly. At this early stage, models exhibit severe punctuation/frequency bias before learning conditional generation.

### 7. Which capabilities require tool assistance rather than model-only learning?
- Arithmetic/Numerical calculation (CAP-14), multi-step logical reasoning (CAP-13), and live dynamic facts (CAP-24) require tool calling (calculator, Python runtime, search API). Small parametric models should never be expected to compute multi-digit multiplications natively.

### 8. What exact capability expansion is required before another training campaign?
- Construct dedicated instruction records for dialogue, constraint following, refusal boundaries, Tanglish conversational pairs, structured JSON responses, summarization, and entity extraction.
- Clean and replace the 16 heuristic fixture prompts (`LIM-WS04-04`).

### 9. What minimum dataset scale and composition should Phase 60 target?
- Target scale: **1,500 – 2,500 curated instruction records** ($4\times - 6\times$ expansion).
- Target distribution: 35% Tamil, 35% English, 20% Mixed Bilingual, 10% Tanglish across balanced tasks.

### 10. What evaluation criteria must be satisfied before next training authorization?
- Pre-flight quality and distribution audit, non-zero benchmark probe baseline, refusal testing protocol, and multi-checkpoint validation gating.

---

## 3. Post-Training Diagnostic Verdict

$$\mathbf{VERDICT:}\quad \mathbf{B \;—\; POST-TRAINING\; DIAGNOSTIC\; COMPLETE\; WITH\; LIMITATIONS}$$
