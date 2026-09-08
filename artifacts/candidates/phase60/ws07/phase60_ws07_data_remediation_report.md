# Phase 60 WS07 — Data Remediation & Multi-Turn Dataset Architecture

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS07 — Capability Remediation & Architecture/Inference Scaling  
**Stage:** Stage A — Remediation Design, Baseline Diagnosis & Experiment Formulation  
**Date:** 2026-08-31  
**Status:** ✅ **STAGE A QUALIFIED — READY FOR HUMAN AUTHORIZATION CHECKPOINT**  
**Stage B Training Authorization:** 🔒 **STRICTLY BLOCKED (PENDING HUMAN APPROVAL)**  

---

## 1. Targeted Data Expansion Plan
New records will be isolated under `artifacts/candidates/phase60/ws07/data/phase60_ws07_dataset_v001.jsonl`:
- **Multi-Turn Dialogue Records:** 300 curated multi-turn exchanges with explicit entity retention.
- **Structured Tool-Dispatch Records:** 150 records prompting calculator tool calls (`{"tool": "calculator", "args": [a, b]}`).
- **Clear Refusal Records:** 150 refusal templates for out-of-domain and toxic prompts.
- **EOS-Reinforced Records:** 100% verified terminal EOS tokens.
