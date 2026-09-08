# Phase 59 WS07 — Failure & Fallback Matrix

**Workstream:** 07 — Training Execution Environment, Resource Limits & Runtime Isolation Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **RUNTIME ISOLATION FAILURE & FALLBACK MATRIX SPECIFIED (35 SCENARIOS)**

---

## 1. Executive Summary

This matrix establishes fail-closed triggers, defensive containment protocols, automated fallbacks, and safe terminal states for thirty-five (35) operational failure modes spanning hardware limits, process memory, swap, disk space, network leakage, and filesystem boundaries.

---

## 2. Operational Failure & Fallback Scenarios

| ID | Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Terminal State |
|---|---|---|---|---|---|
| `FAIL-WS07-001` | Non-CPU device requested | `config.device != "cpu"` | Pre-flight device validation | Override device to `"cpu"` | **CPU execution only** |
| `FAIL-WS07-002` | CUDA tensor detected | `any(p.is_cuda for p in model.parameters())` | Device assertion in model init | Force tensor migration to CPU | **100% CPU resident** |
| `FAIL-WS07-003` | Available RAM $< 1.0$ GB | `MemAvailable < 1 GB` | Pre-flight memory check | Abort training before init | **Host protected from OOM** |
| `FAIL-WS07-004` | Process RSS $> 2.0$ GB | `VmRSS > 2,048 MB` in step callback | Step memory limit monitor | Terminate process immediately | **Host protected from OOM** |
| `FAIL-WS07-005` | Monotonic memory leak | RSS grows $> 20$ MB across 10 steps | Multi-step memory delta tracker | Abort run; dump tensor graph | **Zero memory runaway** |
| `FAIL-WS07-006` | Page swap triggered ($> 100$ MB) | `SwapUsed` delta $> 100$ MB | Step swap watchdog | Pause training; reclaim buffers | **Zero swap dependence** |
| `FAIL-WS07-007` | Workspace disk free $< 10.0$ GB| `shutil.disk_usage().free < 10 GB` | Pre-flight storage check | Abort training before init | **Zero disk exhaustion** |
| `FAIL-WS07-008` | Checkpoint write failure (disk full)| File write I/O exception | Atomic rename safeguard | Discard partial `.tmp`; retain prior | **Uncorrupted prior checkpoint**|
| `FAIL-WS07-009` | Checkpoint written to `/tmp` | Path prefix check | Path canonicalization validator | Redirect to candidate directory | **Confined candidate storage**|
| `FAIL-WS07-010` | Checkpoint written to `models/`| Target path targets `models/` | Write permission guard | Block write; raise `PermissionError`| **Production model protected**|
| `FAIL-WS07-011` | Overwriting Phase 56 checkpoint| Target in `phase56_checkpoints/` | Write permission guard | Block write; raise `PermissionError`| **Historical baseline protected**|
| `FAIL-WS07-012` | Directory traversal via `../` | `..` detected in target path | Canonicalization check | Sanitize and reject path | **Confined candidate root** |
| `FAIL-WS07-013` | Absolute external path escape | Path outside repository root | Path containment check | Reject path; fail closed | **Confined workspace** |
| `FAIL-WS07-014` | Outbound HTTP request attempted | Network socket monitor | Offline firewall / sandboxing | Terminate socket request | **Air-gapped offline state** |
| `FAIL-WS07-015` | External model provider called | Provider API module invocation | Static AST and runtime guard | Intercept call; abort pipeline | **Local sovereign execution** |
| `FAIL-WS07-016` | Environment variable redirection | `CUDA_VISIBLE_DEVICES` or proxy set | Hardcoded config precedence | Enforce explicit config parameters | **Immutable config state** |
| `FAIL-WS07-017` | Subprocess shell execution | `subprocess` with `shell=True` | Static code scan assertion | Block subprocess execution | **Single-process execution** |
| `FAIL-WS07-018` | DataLoader worker crash | Worker process exit code $\ne 0$ | Worker count assertion | Enforce `dataloader_workers=0` | **In-memory single process** |
| `FAIL-WS07-019` | CPU thread oversubscription | Configured threads $> 2 \times$ cores | Thread count assertion | Clamp `set_num_threads` to cores | **Balanced CPU utilization** |
| `FAIL-WS07-020` | Illegal instruction (SIGILL) | AVX instruction on Pentium G2030 | Use `foreach=False` in AdamW | Fallback to standard SSE4.2 loop | **Stable instruction execution**|
| `FAIL-WS07-021` | Infinite training loop | Step counter exceeds `total_steps` | Loop bound assertion | Unconditional loop break | **Strict step limit** |
| `FAIL-WS07-022` | Step duration timeout ($> 10$ s) | Step duration timer | Step timeout watchdog | Abort step; log latency anomaly | **Bounded step latency** |
| `FAIL-WS07-023` | NaN training loss detected | `torch.isnan(loss) == True` | Post-forward loss assertion | Abort step; raise `ValueError` | **Zero corrupted weights** |
| `FAIL-WS07-024` | Inf training loss detected | `torch.isinf(loss) == True` | Post-forward loss assertion | Abort step; raise `ValueError` | **Zero corrupted weights** |
| `FAIL-WS07-025` | Exploding gradient norm ($> 10.0$)| `grad_norm > 10.0` | Norm clipping threshold check | Clamp norm to 1.0; log warning | **Bounded weight updates** |
| `FAIL-WS07-026` | Validation loss divergence ($> 1.5\times$)| Validation loss $> 1.5\times$ initial | Validation monitor callback | Halt training loop; retain best | **Protected generalization** |
| `FAIL-WS07-027` | Checkpoint serialization crash | PyTorch serialization exception | Two-stage `.tmp` atomic save | Abandon `.tmp`; preserve prior | **Valid prior checkpoint** |
| `FAIL-WS07-028` | Process interrupted (SIGINT/TERM)| OS signal handler | Signal interception callback | Clean exit; delete incomplete `.tmp` | **Clean filesystem state** |
| `FAIL-WS07-029` | Resume state desynchronization | Checkpoint step differs from expected | Checkpoint header validator | Sync step counter with checkpoint | **Exact resume continuity** |
| `FAIL-WS07-030` | Checkpoint pruning baselines | Retention purges frozen corpus | File path exemption check | Protect non-candidate files | **Frozen baselines intact** |
| `FAIL-WS07-031` | Training log contains API secret| Regex scanner on log strings | Secret pattern filter | Mask secret; abort logging | **Zero credential exposure** |
| `FAIL-WS07-032` | Production DB mutation detected | SHA-256 $\ne$ `34376318...` | Database hash watchdog | Halt process; revert DB from git | **Production DB intact** |
| `FAIL-WS07-033` | Candidate public chat registration| Candidate flag set to active | Routing registry watchdog | Force flag to `False`; traffic = 0% | **Zero public exposure** |
| `FAIL-WS07-034` | Missing training dataset file | File not found at configured path | Pre-flight dataset loader | Raise `FileNotFoundError`; abort | **Safe halted state** |
| `FAIL-WS07-035` | Tokenizer v2 hash mutation | SHA-256 $\ne$ `65342625...` | Pre-flight hash assertion | Halt pipeline; restore frozen model | **Frozen tokenizer intact** |

---

## 3. Failure Policy Declaration

Any occurrence of `FAIL-WS07-010` (production model write), `FAIL-WS07-014` (network access), `FAIL-WS07-032` (database mutation), or `FAIL-WS07-033` (public chat exposure) is strictly **TRAINING-BLOCKING** and triggers immediate emergency pipeline shutdown.
