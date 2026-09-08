# Phase 59 WS03 — Failure & Fallback Matrix

**Workstream:** 03 — Data Quality, Balance & Generalization Audit  
**Phase:** 59 — Controlled Capability & Instruction Learning Validation  
**Date:** 2026-08-31  
**Status:** ✅ **DATA QUALITY FAILURE & FALLBACK MATRIX SPECIFIED (32 SCENARIOS)**

---

## 1. Executive Summary

This matrix establishes fail-closed detection triggers, defensive containment interventions, automated fallbacks, and safe terminal states for thirty-two (32) critical operational failure modes spanning data quality, distribution imbalances, severe truncation, memorization risks, benchmark contamination, and isolation violations.

---

## 2. Operational Failure & Fallback Scenarios

| ID | Failure Mode | Detection Mechanism | Defensive Protocol | Fallback Action | Safe Terminal State |
|---|---|---|---|---|---|
| `FAIL-WS03-001` | Missing canonical instruction artifact | `INST_PATH.exists() == False` | File path assertion prior to audit | Halt pipeline; notify operator to rerun WS02 | **Candidate artifact verified** |
| `FAIL-WS03-002` | Canonical instruction SHA mismatch | Checksum differs from WS02 manifest | SHA-256 integrity assertion | Re-verify WS02 generation; block audit | **Cryptographically verified dataset** |
| `FAIL-WS03-003` | Incomplete record schema | Missing any of 12 required fields | Schema validator on every JSONL record | Quarantine incomplete record; fail audit | **100% compliant schema** |
| `FAIL-WS03-004` | Null field values in record | Any field value is `None` | Null assertion scan across records | Reject candidate dataset | **Zero null fields** |
| `FAIL-WS03-005` | Empty instruction prompt | `len(instruction.strip()) == 0` | Text length assertion $> 0$ | Reject record; flag transformation bug | **Zero empty instructions** |
| `FAIL-WS03-006` | Empty assistant response | `len(response.strip()) == 0` | Text length assertion $> 0$ | Reject record; flag transformation bug | **Zero empty responses** |
| `FAIL-WS03-007` | Duplicate record IDs | ID collision in `inst_records` | Set length assertion == list length | Halt audit; assign unique deterministic IDs | **Unique record IDs** |
| `FAIL-WS03-008` | Duplicate source hashes | Hash collision in `inst_records` | Set length assertion on `source_hash` | Investigate upstream source deduplication | **Unique source hashes** |
| `FAIL-WS03-009` | Exact prompt-response duplication | Level 4 duplicate detected | Pair tuple hash table comparison | Purge duplicate pair; re-run audit | **Zero duplicate pairs** |
| `FAIL-WS03-010` | Exact response duplication | Level 3 duplicate detected | Response string hash table comparison | Inspect domain generation logic | **Distinct response targets** |
| `FAIL-WS03-011` | Normalized text pair duplicate | Level 5 duplicate detected | Normalized text hash comparison | Remove redundant pair; preserve first instance | **Zero normalized duplicates** |
| `FAIL-WS03-012` | Single-task category collapse | 1 task represents $> 90\%$ of data | Task distribution entropy $< 0.5$ bits | Reject dataset balance; re-curate tasks | **Balanced multi-task spread** |
| `FAIL-WS03-013` | Domain starvation ($< 5$ domains) | Number of domains $< 5$ | Domain count assertion | Halt qualification; restore multi-domain corpus | **$\ge 15$ sovereign domains** |
| `FAIL-WS03-014` | Language balance distortion | Language counts differ from Phase 55 | Language count comparison vs source | Re-sync transformation with source corpus | **Source-aligned language balance** |
| `FAIL-WS03-015` | Tanglish record corruption | `tgl` record contains empty text | Verification of 5 Tanglish records | Restore pristine Tanglish records | **Pristine Tanglish examples** |
| `FAIL-WS03-016` | UNK token emission in text | `sp2.EncodeAsIds(text).count(1) > 0` | Tokenizer vector scan for ID 1 | Reject example; verify byte fallback | **0.0000% UNK rate** |
| `FAIL-WS03-017` | Sequence with zero supervised targets | `target_token_count == 0` | Assertion `target_token_count > 0` | Enforce `truncate_response_tail` policy | **Every sequence has targets** |
| `FAIL-WS03-018` | Sequence with $\le 1$ target token | `target_token_count <= 1` | Assertion `target_token_count >= 2` | Reject example as trivial target | **Substantial target length** |
| `FAIL-WS03-019` | Total response token retention $< 70\%$ | Retained tokens / Orig tokens $< 0.70$ | Global token retention assertion | Increase context window or shorten prompt | **$\ge 70\%$ token retention** |
| `FAIL-WS03-020` | Severely truncated sequences $> 10\%$ | $> 50\%$ removed in $> 40$ sequences | Outlier truncation count assertion | Flag long-form records for chunking | **$\le 5\%$ severely truncated** |
| `FAIL-WS03-021` | Supervision density $< 0.05$ | Target ratio $< 5\%$ of sequence | Supervision density check | Flag example as under-supervised | **Adequate supervision density** |
| `FAIL-WS03-022` | Cross-split ID overlap | Train ID found in val or test | Set intersection assertion == 0 | Purge overlapping record from train | **Strict split isolation** |
| `FAIL-WS03-023` | Cross-split response text overlap | Response string found across splits | Set intersection assertion == 0 | Re-partition splits to isolate text | **Zero text overlap across splits** |
| `FAIL-WS03-024` | Exact benchmark prompt contamination | Instruction matches Phase 53 probe | Substring search against 32 probes | Quarantine contaminated training record | **Zero benchmark contamination** |
| `FAIL-WS03-025` | Exact benchmark answer contamination | Response matches Phase 53 probe answer | Substring search against 32 probes | Quarantine contaminated training record | **Zero benchmark contamination** |
| `FAIL-WS03-026` | Target keyword verbatim contamination | Response equals benchmark target keyword | Exact match against probe keywords | Quarantine contaminated training record | **Zero keyword contamination** |
| `FAIL-WS03-027` | High memorization risk rating | Risk matrix scores HIGH or CRITICAL | Multi-factor risk calculation | Block training authorization; reduce epochs | **LOW memorization risk** |
| `FAIL-WS03-028` | Unsafe execution primitive detected | AST detects `eval`, `exec`, `os.system` | Static code analysis scan | Remove unsafe primitive immediately | **Clean secure codebase** |
| `FAIL-WS03-029` | Production database mutation | DB SHA-256 differs from frozen hash | Database SHA assertion | Revert `brud_ai.db` from git; block pipeline | **Production DB unmodified** |
| `FAIL-WS03-030` | Candidate model public routing | `is_public_chat_eligible` set to `True` | Routing configuration audit | Force flag to `False`; traffic = 0.0% | **Public chat exposure = 0.0%** |
| `FAIL-WS03-031` | Premature training execution | Training script launched during WS03 | Process monitor lock | Kill unauthorized process; flag violation | **Training execution blocked** |
| `FAIL-WS03-032` | Candidate artifact placed in production | File written outside `artifacts/candidates/` | Filesystem path validator | Move artifact to isolated directory | **Candidate storage isolated** |

---

## 3. Failure Policy Declaration

In the event that any failure scenario triggers:
1. Pipeline halts immediately (fail closed).
2. Failure ID, affected records, and stack trace are logged to the workstream audit log.
3. No silent data rewriting or automated record deletion is permitted.
4. Corrective remediation must be documented and re-audited prior to proceeding.
