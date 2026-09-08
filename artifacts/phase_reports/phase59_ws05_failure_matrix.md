# Phase 59 WS05 — Failure & Fallback Matrix

**Workstream:** 05 — Training Objective, Loss Function & Optimization Safety Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **OPTIMIZATION SAFETY FAILURE & FALLBACK MATRIX SPECIFIED (35 SCENARIOS)**

---

## 1. Executive Summary

This matrix establishes fail-closed triggers, defensive containment protocols, automated fallbacks, and safe terminal states for thirty-five (35) operational failure modes spanning loss computation, gradient anomalies, optimizer instabilities, checkpoint corruptions, and CPU resource limits.

---

## 2. Operational Failure & Fallback Scenarios

| ID | Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Terminal State |
|---|---|---|---|---|---|
| `FAIL-WS05-001` | Logits-labels shape mismatch | `logits.shape[:2] != labels.shape` | Shape assertion before slicing | Reject batch; halt forward step | **Matched batch shapes** |
| `FAIL-WS05-002` | All-masked label batch | `not torch.any(shift_labels != -100)` | Defensive guard in `causal_lm_loss` | Raise `ValueError`; do not return `NaN` | **Guarded loss execution** |
| `FAIL-WS05-003` | Off-by-one causal shift error | Shift slice index differs from `[:-1]` / `[1:]` | Unit test regression assertion | Enforce canonical `[B, T-1]` alignment | **Exact causal alignment** |
| `FAIL-WS05-004` | Non-finite training loss (NaN/Inf) | `not torch.isfinite(output.loss)` | Post-forward loss assertion | Abort step; dump offending batch | **Preserved model weights** |
| `FAIL-WS05-005` | Non-finite gradient norm (NaN/Inf) | `not torch.isfinite(grad_norm)` | Post-clipping assertion | Discard gradient buffer; zero grad | **Preserved optimizer state** |
| `FAIL-WS05-006` | Exploding gradient norm ($> 10.0$) | `grad_norm > 10.0` | Step gradient magnitude monitor | Clamp norm to 1.0; log warning | **Bounded gradient magnitude** |
| `FAIL-WS05-007` | Prompt label gradient leakage | Gradient non-zero at prompt positions | Unit test assertion on prompt grad | Enforce `ignore_index=-100` on prompt | **Zero prompt gradient** |
| `FAIL-WS05-008` | Padding label gradient leakage | Gradient non-zero at pad positions | Unit test assertion on pad grad | Enforce `ignore_index=-100` on pad | **Zero padding gradient** |
| `FAIL-WS05-009` | Unintended frozen parameter | `p.requires_grad == False` on model param | Parameter loop trainability check | Set `p.requires_grad = True` | **100% trainable weights** |
| `FAIL-WS05-010` | Parameter omitted from AdamW | Set difference between model and opt | Optimizer parameter group check | Add missing parameter to group | **All weights in optimizer** |
| `FAIL-WS05-011` | Weight decay applied to bias/norm | 1D parameter found in decay group | Dimension assertion in optimizer | Relocate to no-decay group | **Unbiased normalization** |
| `FAIL-WS05-012` | Unsupported scheduler requested | Scheduler name not in registry | Factory validation exception | Raise `ValueError`; fallback to constant | **Valid scheduler policy** |
| `FAIL-WS05-013` | Learning rate division by zero | `total_steps <= warmup_steps` | Parameter validation check | Enforce `total_steps > warmup_steps` | **Stable schedule curve** |
| `FAIL-WS05-014` | Accumulation scaling omission | Loss not divided by accumulation steps | Accumulation scaling unit test | Scale loss by `1 / N_accum` before backprop | **Exact average gradient** |
| `FAIL-WS05-015` | Cross-sequence attention leak | Attention mask not causal/independent | Mask tensor shape inspection | Enforce block-diagonal / isolated mask | **Isolated sequence context** |
| `FAIL-WS05-016` | Missing supervised EOS token | Target doesn't end with token ID 3 | End-of-target sequence validator | Enforce `truncate_response_tail` policy | **100% EOS termination** |
| `FAIL-WS05-017` | Zero-target sequence executed | Sequence target length == 0 | Target length validator assertion | Quarantine example; reject batch | **All sequences supervised** |
| `FAIL-WS05-018` | Model-tokenizer vocab mismatch | `lm_head.out_features != vocab_size` | Dimension equality assertion | Re-initialize head with tokenizer vocab | **Synchronized vocabularies** |
| `FAIL-WS05-019` | Context length truncation overflow | Input tensor length $> 128$ | Tensor shape validator | Truncate sequence to 128 boundary | **Bounded context window** |
| `FAIL-WS05-020` | Process memory exceeds 2.0 GB | `process_memory_bytes() > 2 GB` | Step memory monitor callback | Abort training; log memory dump | **Safe host memory state** |
| `FAIL-WS05-021` | Host available RAM $< 500$ MB | `available_memory_bytes() < 500 MB` | Pre-step resource assertion | Pause training until RAM recovers | **Host system protected** |
| `FAIL-WS05-022` | Checkpoint write to production path | File path targets `models/` | Path validator in checkpoint callback | Divert write to candidate directory | **Isolated candidate storage** |
| `FAIL-WS05-023` | Checkpoint serialization corruption | File size 0 or invalid pickle/pt | Checksum and load test on save | Retry save; retain previous checkpoint | **Valid checkpoint file** |
| `FAIL-WS05-024` | Overwriting Phase 56 checkpoint | Target path in `phase56_checkpoints/` | Write permission validator | Block filesystem write immediately | **Frozen historical baselines** |
| `FAIL-WS05-025` | Resume state desynchronization | Resumed step differs from target | Step counter assertion on reload | Synchronize step counter with checkpoint | **Exact resume fidelity** |
| `FAIL-WS05-026` | RNG state desynchronization | RNG tensor size mismatch on reload | Generator tensor validation | Re-seed with `sampling_seed` | **Reproducible generation** |
| `FAIL-WS05-027` | Validation loss divergence ($> 1.5\times$) | Validation loss $> 1.5\times$ initial | Metric tracking callback | Halt training; revert to best checkpoint | **Protected generalization** |
| `FAIL-WS05-028` | Validation gradient leakage | Gradients populated during eval | `torch.no_grad()` assertion | Enforce `no_grad()` during eval | **Zero validation gradients** |
| `FAIL-WS05-029` | Benchmark probe fed to training | Probe ID detected in training stream | Substring matching on batch | Reject batch; purge probe immediately | **Zero benchmark leakage** |
| `FAIL-WS05-030` | Tokenizer hash mutation | SHA-256 differs from `65342625...` | Pre-step SHA assertion | Halt training; restore frozen model | **Frozen tokenizer intact** |
| `FAIL-WS05-031` | Phase 55 corpus hash mutation | SHA-256 differs from `3e1481c3...` | Pre-step SHA assertion | Halt training; restore frozen corpus | **Frozen corpus intact** |
| `FAIL-WS05-032` | Production DB hash mutation | SHA-256 differs from `34376318...` | Pre-step SHA assertion | Halt training; revert DB from git | **Production DB intact** |
| `FAIL-WS05-033` | Candidate model public routing | `is_public_chat_eligible` is True | Routing registry inspection | Force flag to `False`; traffic = 0.0% | **Public exposure blocked** |
| `FAIL-WS05-034` | Premature large-scale training | Total steps exceeds micro-limit ($> 100$) | Step limit assertion in config | Cap steps to 100 for validation phase | **Bounded controlled study** |
| `FAIL-WS05-035` | Unsafe execution primitive in code | Static scan detects `eval`, `exec` | AST security scanner | Remove unsafe primitive immediately | **Clean secure codebase** |

---

## 3. Failure Policy Declaration

In the event that any failure scenario triggers:
1. Pipeline halts immediately (fail closed).
2. Offending tensors, batches, and stack traces are logged.
3. No silent data rewriting or automated recovery is permitted without explicit audit trail.
