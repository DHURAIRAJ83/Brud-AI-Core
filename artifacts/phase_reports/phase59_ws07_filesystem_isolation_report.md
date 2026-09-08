# Phase 59 WS07 — Filesystem Isolation & Path Traversal Report

**Workstream:** 07 — Training Execution Environment, Resource Limits & Runtime Isolation Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **FILESYSTEM ISOLATION & PATH TRAVERSAL DEFENSE FULLY QUALIFIED**

---

## 1. Executive Summary

This report establishes the filesystem boundary audit, candidate workspace sandboxing, directory traversal resistance, and production write protection for Phase 59 controlled instruction tuning.

The program's strict operational invariant mandates that all candidate model checkpoints, training logs, and evaluation metrics must reside exclusively under:
$$\text{Candidate Workspace Root} = \text{artifacts/candidates/phase59/}$$

---

## 2. Permitted Filesystem Write Boundaries

| Path Location | Designated Role | Write Permission? | Enforcement Mechanism |
|---|---|---|---|
| `artifacts/candidates/phase59/` | Candidate sequences, records, checkpoints | ✅ **PERMITTED** | Primary candidate workspace |
| `artifacts/candidates/phase59/checkpoints/` | Candidate model `.pt` files | ✅ **PERMITTED** | Designated candidate checkpoint folder |
| `models/` | Production model registry & exports | ❌ **PROHIBITED** | Stop condition `STOP-12` & file guard |
| `artifacts/phase56_checkpoints/` | Historical Phase 56 baselines | ❌ **PROHIBITED** | Read-only frozen baseline guard |
| `data/database/` | Production SQLite database (`brud_ai.db`)| ❌ **PROHIBITED** | Stop condition `STOP-10` & SHA watchdog |
| `data/tokenizers/versions/tok/v2/`| Frozen Tokenizer v2 model | ❌ **PROHIBITED** | Stop condition `STOP-08` & SHA watchdog |
| `/tmp/`, `/var/`, `/home/` outside repo | Operating system paths | ❌ **PROHIBITED** | Path canonicalization validator |

---

## 3. Directory Traversal Attack Resilience

The checkpoint management path validation logic was tested against synthetic directory traversal attacks:

| Attack Vector | Input Test Path | Canonicalized Target Path | Reaction | Status |
|---|---|---|---|---|
| **Relative Parent Traversal** | `artifacts/candidates/phase59/../../models/test.pt` | `/home/dhurai/Projects/brud-ai/models/test.pt` | Escapes candidate root $\to$ **REJECTED** | ✅ **PASS** |
| **System Root Traversal** | `../../../etc/passwd` | `/etc/passwd` | Escapes candidate root $\to$ **REJECTED** | ✅ **PASS** |
| **Absolute OS Path** | `/tmp/external_checkpoint.pt` | `/tmp/external_checkpoint.pt` | Escapes candidate root $\to$ **REJECTED** | ✅ **PASS** |
| **Historical Directory Write** | `artifacts/phase56_checkpoints/c.pt` | `.../artifacts/phase56_checkpoints/c.pt` | Escapes candidate root $\to$ **REJECTED** | ✅ **PASS** |
| **Production Target Write** | `models/candidate_model.gguf` | `.../models/candidate_model.gguf` | Escapes candidate root $\to$ **REJECTED** | ✅ **PASS** |
| **Legitimate Candidate Path** | `artifacts/candidates/phase59/checkpoints/c1.pt` | `.../artifacts/candidates/phase59/...` | Inside candidate root $\to$ **AUTHORIZED** | ✅ **PASS** |

---

## 4. Path Canonicalization & Confinement Enforcement

- **Enforcement Rule:** Every output path is resolved to its real canonical path using `Path(target).resolve()` and checked against `Path(allowed_root).resolve()` via `target.relative_to(allowed_root)`.
- **Zero Ambiguity:** Traversal sequences like `..` or symlinks are flattened prior to permission validation.
- **Fail-Closed:** Any path failing the `relative_to` containment check raises an immediate `ValueError: unauthorized filesystem write path`, halting execution before any file handle is opened.

---

## 5. Filesystem Isolation Verdict

**STATUS: PASS.** Candidate write boundaries are strictly confined to `artifacts/candidates/phase59/`, directory traversal is neutralized, and production directories are 100% write-protected.
