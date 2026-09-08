# Phase 59 WS02 — Failure & Fallback Matrix

**Workstream:** 02 — Dataset Transformation Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **DEFENSIVE PROTOCOLS & FALLBACK MATRIX SPECIFIED (30 SCENARIOS)**

---

## 1. Executive Summary

This matrix establishes fail-closed detection mechanisms, defensive interventions, automated fallbacks, and safe terminal states for thirty (30) critical operational failure modes spanning dataset transformation, loss masking, tokenizer integration, split integrity, memorization, security, and governance boundaries.

---

## 2. Failure & Fallback Scenarios

| ID | Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Final State |
|---|---|---|---|---|---|
| `FAIL-WS02-001` | Corrupted Phase 55 corpus file | SHA-256 mismatch against WS01 freeze (`3e1481c3...`) | Pre-transformation SHA assertion | Halt pipeline; restore from immutable git store | **Verified Phase 55 corpus** |
| `FAIL-WS02-002` | Malformed JSONL record syntax | `json.loads()` raises `JSONDecodeError` | Line-by-line try/except parser | Isolate malformed line to quarantine; halt transform | **Clean JSONL records only** |
| `FAIL-WS02-003` | Missing provenance metadata | `source_id` or `source_record_hash` is null | Assertion on schema fields | Reject record from candidate dataset | **100% lineage preserved** |
| `FAIL-WS02-004` | Empty instruction string | `len(instruction.strip()) == 0` | String length check prior to tokenization | Fail closed; flag record for review | **Zero empty instructions** |
| `FAIL-WS02-005` | Empty assistant response string | `len(response.strip()) == 0` | String length check prior to tokenization | Fail closed; flag record for review | **Zero empty responses** |
| `FAIL-WS02-006` | UNK token emission in instruction | `sp2.EncodeAsIds(instruction).count(1) > 0` | Token vector inspection for ID 1 | Reject example; inspect vocabulary coverage | **Zero UNK instruction rate** |
| `FAIL-WS02-007` | UNK token emission in response | `sp2.EncodeAsIds(response).count(1) > 0` | Token vector inspection for ID 1 | Reject example; check byte fallback status | **Zero UNK response rate** |
| `FAIL-WS02-008` | Special token ID collision in raw text | Literal string `<assistant>` in user text | Regex search for reserved tags in body | Escape or reject raw tag to prevent prompt injection | **Sanitized user prompt** |
| `FAIL-WS02-009` | Missing `<assistant>` boundary token | `input_ids[p_len - 1] != 6` | Assertion on prompt boundary position | Reject example; re-render with template | **Guaranteed assistant boundary** |
| `FAIL-WS02-010` | Prompt token exposed as loss target | `labels[t] != -100` for $t < p_{\text{len}}$ | Vector mask assertion on label slice | Overwrite slice with `-100`; log critical warning | **100% prompt loss masked** |
| `FAIL-WS02-011` | Zero supervised response tokens | `all(l == -100 for l in labels)` | Assertion `target_token_count > 0` | Reject example; cannot train unconditioned step | **Every example has targets** |
| `FAIL-WS02-012` | Padding token exposed as loss target | `labels[t] != -100` for $t \ge p_{\text{len}} + r_{\text{len}}$ | Vector mask assertion on padding slice | Overwrite slice with `-100`; verify pad_token_id | **100% padding loss masked** |
| `FAIL-WS02-013` | Causal shift off-by-one error | Loss computed without label offset | Unit test evaluating loss gradient wrt prompt | Enforce `shift_logits` vs `shift_labels` | **Conditioned causal loss** |
| `FAIL-WS02-014` | Total prompt loss wipeout from truncation | `prompt_token_count == 0` under prompt truncation | Check prompt count $> 0$ | Enforce `truncate_response_tail` policy | **Prompt context preserved** |
| `FAIL-WS02-015` | Terminal EOS token omitted | `input_ids[active_end - 1] != 3` | End-of-active token assertion | Append EOS ID 3 before sequence padding | **Explicit EOS termination** |
| `FAIL-WS02-016` | Sequence length exceeds 128 | `len(input_ids) > 128` | Tensor dimension check | Truncate or pad to exactly 128 tokens | **Exact 128 token sequence** |
| `FAIL-WS02-017` | Cross-split ID overlap | Intersection of train and val/test IDs $> 0$ | Hash set intersection assertion | Purge overlapping records; halt candidate build | **Strict partition isolation** |
| `FAIL-WS02-018` | Benchmark prompt contamination | Instruction matches Phase 53 probe prompt | Substring match against benchmark manifest | Immediate quarantine of leaked training example | **Zero benchmark contamination** |
| `FAIL-WS02-019` | Benchmark answer contamination | Response matches Phase 53 probe expected output | Substring match against benchmark manifest | Immediate quarantine of leaked training example | **Zero benchmark contamination** |
| `FAIL-WS02-020` | PII / Secret detection in instruction | Regex match on emails, phones, API keys | Pre-serialization regex scan | Redact or reject contaminated record | **Zero PII exposure** |
| `FAIL-WS02-021` | Non-deterministic transformation output | SHA-256 mismatch between run 1 and run 2 | Double-run hash comparison | Fix random seed; eliminate un-ordered dicts | **Bit-exact reproducibility** |
| `FAIL-WS02-022` | Tokenizer v1 model loaded accidentally | Vocabulary size == 64 | `sp.GetPieceSize() != 1024` | Fail closed; load only v2 tokenizer | **Tokenizer v2 enforced** |
| `FAIL-WS02-023` | Legacy Phase 56 checkpoint reuse attempt | Loading state dict with 64-vocab embedding | Model parameter shape assertion | Abort loading; instantiate fresh Brud-Small v2 | **Fresh model instantiation** |
| `FAIL-WS02-024` | Production DB mutation attempt | File write handle opened on `brud_ai.db` | Pre/post SHA-256 check on `brud_ai.db` | Revert DB from git; block pipeline | **Production DB immutable** |
| `FAIL-WS02-025` | Public chat routing alteration | `is_public_chat_eligible` set to `True` | Routing configuration audit | Force flag to `False`; traffic share = 0.0% | **Public exposure blocked** |
| `FAIL-WS02-026` | Training launched before WS08 completion | Training process spawned in WS02 | Process monitor; execution lock check | Kill unauthorized training subprocess | **Training halted** |
| `FAIL-WS02-027` | Disk space exhaustion during serialization | `IOError` / `ENOSPC` during JSONL write | Free disk space check $> 1\text{ GB}$ | Flush temporary buffers; alert operator | **Clean filesystem state** |
| `FAIL-WS02-028` | Memory exhaustion during batch building | Process RSS $> 2\text{ GB}$ | Memory monitoring threshold | Stream records sequentially; avoid bulk caching | **Bounded memory $< 200\text{ MB}$** |
| `FAIL-WS02-029` | NaN loss evaluation | `torch.isnan(loss).item() == True` | PyTorch finite loss assertion | Re-check label values and logits; zero-out NaNs | **Numerically stable loss** |
| `FAIL-WS02-030` | Candidate dataset stored in production path | File path outside `artifacts/candidates/` | File destination validator | Move file to isolated candidate directory | **Isolated candidate storage** |

---

## 3. Failure Policy Declaration

In the event that any failure scenario triggers:
1. Pipeline halts immediately (fail closed).
2. Failure ID and stack trace are logged to the workstream audit log.
3. No automatic data patching or silent data rewriting is permitted.
4. Corrective action must be reviewed, documented, and certified before resuming.
