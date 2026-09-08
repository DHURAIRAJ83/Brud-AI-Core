# Phase 59 WS04 — Failure & Fallback Matrix

**Workstream:** 04 — Instruction-Following, Task Coverage & Capability Alignment Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **CAPABILITY ALIGNMENT FAILURE & FALLBACK MATRIX SPECIFIED (32 SCENARIOS)**

---

## 1. Executive Summary

This matrix establishes fail-closed triggers, defensive containment interventions, automated fallbacks, and safe terminal states for thirty-two (32) critical operational failure modes spanning task coverage, capability distortion, reasoning deficits, contradiction hazards, and benchmark misalignment.

---

## 2. Operational Failure & Fallback Scenarios

| ID | Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Terminal State |
|---|---|---|---|---|---|
| `FAIL-WS04-001` | Task type cardinality collapse ($< 3$ tasks) | Unique `task_type` count $< 3$ | Cardinality assertion $\ge 3$ | Halt audit; inspect transformation mapping | **5 distinct task types** |
| `FAIL-WS04-002` | Zero examples in core task | Count == 0 in `definition_qa` or `factual_exp` | Minimum record assertion per task | Fail qualification; restore task mapping | **All core tasks populated** |
| `FAIL-WS04-003` | Task Shannon entropy collapse ($< 0.5$ bits) | Task distribution entropy $< 0.5$ | Categorical entropy threshold check | Flag extreme task skew; re-balance | **Entropy $> 1.0$ bit** |
| `FAIL-WS04-004` | Factual contradiction in training pairs | Opposing assertions on identical entity | Pairwise entity statement contradiction scan | Log finding; quarantine contradictory records | **Consistent factual grounding** |
| `FAIL-WS04-005` | Heuristic prompt pollution ($> 10\%$ of data) | CSV header-derived prompts $> 40$ records | Pattern match on `record_id` / `text` prompts | Halt pipeline if $> 10\%$; flag as warning if $\le 4\%$ | **Bounded heuristic prompts** |
| `FAIL-WS04-006` | Tanglish record corruption | Any of 5 Tanglish records has empty text | Record content assertion on `language == 'tgl'` | Restore original 5 Tanglish records | **Pristine Tanglish records** |
| `FAIL-WS04-007` | Unauthorized Tanglish synthesis | Tanglish record count $> 5$ | Assertion `len(tgl_recs) == 5` | Purge unapproved synthetic records | **Zero synthetic data** |
| `FAIL-WS04-008` | Complete Tamil script omission | Zero Tamil Unicode in `ta` records | Regex assertion `[\u0b80-\u0bff]` | Reject dataset; investigate font/encoding | **Verified Tamil Unicode** |
| `FAIL-WS04-009` | UNK token emission in capability records | `sp2.EncodeAsIds(text).count(1) > 0` | Tokenizer vector inspection for ID 1 | Reject example; verify byte fallback | **0.0000% UNK rate** |
| `FAIL-WS04-010` | Total absence of procedural reasoning | Zero records with step markers (`1.`, `2.`) | Keyword scan for procedural steps | Halt reasoning qualification | **Procedural steps represented** |
| `FAIL-WS04-011` | Over-claiming mental arithmetic capability | Arithmetic claimed without drill supervision | Cross-check claim vs drill record count | Downgrade arithmetic claim to "Tool-Assisted" | **Transparent capability claim** |
| `FAIL-WS04-012` | Single response style collapse ($> 80\%$) | 1 response archetype represents $> 80\%$ | Archetype distribution check | Flag single-style over-fitting risk | **Balanced response structures** |
| `FAIL-WS04-013` | Sequence missing EOS token ID 3 | Last active token $!= 3$ | End-of-active token assertion | Enforce `truncate_response_tail` policy | **100% EOS termination** |
| `FAIL-WS04-014` | Supervised EOS token omission in labels | `labels[last_pos] != 3` | Label slice assertion on EOS position | Overwrite EOS label with 3 | **100% supervised EOS** |
| `FAIL-WS04-015` | EOS-only response target | `target_token_count <= 1` | Assertion `target_token_count >= 2` | Reject example as degenerate | **Substantial target length** |
| `FAIL-WS04-016` | Truncation of prompt context | `prompt_token_count < orig_prompt_len` | Prompt length comparison pre/post packing | Halt pipeline; enforce prompt preservation | **100% prompt preservation** |
| `FAIL-WS04-017` | Zero-target sequence generated | `target_token_count == 0` | Assertion `target_token_count > 0` | Halt pipeline; reject unconditioned example | **All sequences have targets** |
| `FAIL-WS04-018` | Cross-split contamination of reasoning | Reasoning record duplicated across splits | Hash set intersection on reasoning IDs | Purge reasoning duplicate from train | **Strict split isolation** |
| `FAIL-WS04-019` | Benchmark probe exact leak in instructions | Instruction matches Phase 53 probe prompt | Substring scan against benchmark manifest | Immediate quarantine of leaked record | **Zero benchmark contamination** |
| `FAIL-WS04-020` | Benchmark answer exact leak in responses | Response matches Phase 53 probe answer | Substring scan against benchmark manifest | Immediate quarantine of leaked record | **Zero benchmark contamination** |
| `FAIL-WS04-021` | Over-claiming adversarial safety | Safety claimed without refusal training pairs | Cross-check safety claim vs refusal count | Enforce inference guardrail requirement | **Safe inference architecture** |
| `FAIL-WS04-022` | Unsupported capability over-generalization | High capability score assigned to sparse task | Verification against capability support table | Force limitation documentation in manifest | **Honest capability score** |
| `FAIL-WS04-023` | Difficulty band collapse ($< 3$ bands) | Difficulty levels represented $< 3$ | Difficulty tier cardinality check | Stratify prompts by complexity | **5 difficulty tiers active** |
| `FAIL-WS04-024` | Literature interpretation ambiguity | Thirukkural couplets lack meaning | Verification of explanation body | Ensure couplet explanation is populated | **Clear literature commentary** |
| `FAIL-WS04-025` | Unsafe execution primitive in audit code | Static scan detects `eval`, `exec`, `os.system`| AST security inspection | Remove unsafe primitive immediately | **Clean secure codebase** |
| `FAIL-WS04-026` | Production database mutation attempt | Database SHA differs from frozen baseline | Pre/post SHA-256 assertion | Revert DB from git; fail workstream | **Production DB intact** |
| `FAIL-WS04-027` | Public chat routing exposure | `is_public_chat_eligible` set to `True` | Routing configuration audit | Force flag to `False`; traffic = 0.0% | **Public exposure blocked** |
| `FAIL-WS04-028` | Premature training execution attempt | Training process launched during WS04 | Process monitor lock | Terminate unauthorized training subprocess | **Training halted** |
| `FAIL-WS04-029` | Candidate artifact stored in production | File written outside `artifacts/candidates/` | File path validator | Relocate artifact to candidate directory | **Candidate storage isolated** |
| `FAIL-WS04-030` | Frozen Phase 55 corpus hash mutation | Corpus SHA differs from frozen baseline | Pre/post SHA-256 assertion | Revert corpus from git; fail workstream | **Frozen corpus intact** |
| `FAIL-WS04-031` | Frozen Tokenizer v2 hash mutation | Tokenizer SHA differs from frozen baseline | Pre/post SHA-256 assertion | Revert tokenizer from git; fail workstream | **Frozen tokenizer intact** |
| `FAIL-WS04-032` | Quality gate suppression attempt | Failed gate hidden from final summary | Cross-check table vs recorded status | Enforce transparent WARN/FAIL reporting | **Transparent audit reporting** |

---

## 3. Failure Policy Declaration

In the event that any failure scenario triggers:
1. Pipeline halts immediately (fail closed).
2. Failure ID, affected records, and stack trace are logged to the workstream audit log.
3. No silent data rewriting or automated record deletion is permitted.
4. Corrective remediation must be documented and re-audited prior to proceeding.
