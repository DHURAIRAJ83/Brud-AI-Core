# PHASE 15 — PRODUCTION READINESS & DEPLOYMENT ROADMAP
## Brud AI Mini Brain / Admin Assistant Runtime

**Date**: September 4, 2026  
**Status**: ACTIVE VALIDATION & HARDENING  
**Scope**: P15.1 → P15.10 Locked Execution Order  
**Baseline Verified**: Phase 14 Certified (29/29 P14 tests, 96/96 historical tests passing)  

---

### 1. Phase 15 Overview & Execution Plan

Phase 15 validates and hardens the Brud AI Mini Brain / Admin Assistant Runtime at the **real production deployment level**, answering:
> *"Can the current Brud AI Mini Brain runtime safely survive real deployment, real traffic, real provider outages, process restarts, resource pressure, backup/restore operations, and security attacks?"*

The locked execution order is strictly enforced:
- **P15.1**: Production Deployment Discovery & Audit (Current Stage)
- **P15.2**: Security Hardening Audit (Vulnerability classification, credential checks, injection analysis)
- **P15.3**: Production Load & Concurrency Testing (Multi-session, concurrent streaming, SQLite write contention)
- **P15.4**: Resource Pressure & Memory Safety (Memory leak checks, RSS bounding, file descriptor audits)
- **P15.5**: Process Restart & Crash Recovery (Unclean process termination, WAL recovery, `PRAGMA integrity_check`)
- **P15.6**: Backup & Restore Validation (Snapshot generation, byte-exact restore execution, integrity verification)
- **P15.7**: Disaster Recovery Validation (Catastrophic failure simulation, RTO/RPO measurement, recovery steps)
- **P15.8**: Reverse Proxy & Network Resilience (SSE buffering, timeout tolerance, proxy header propagation)
- **P15.9**: Dependency & Configuration Security (Dependency vulnerability scan, production config lock)
- **P15.10**: Final Production Smoke & Certification (End-to-end smoke test, full regression, final verdict)

---

### 2. Architectural Guardrail Invariants (G1–G14 Lock)

All 14 invariants remain strictly locked and non-negotiable throughout Phase 15:
1. **G1**: `authority_mode = ADVISORY_ONLY` — zero autonomous execution from chat.
2. **G2**: Maker != Checker — proposals require separate human approval.
3. **G3**: Tool Invocation Boundary — direct tool execution from chat is strictly blocked.
4. **G4**: Training Gate Fail-Closed — `SignedTrainingAuthorizationToken = ABSENT`.
5. **G5**: Single Persistence Turn — tokens buffered in memory; exactly 1 record per turn in SQLite.
6. **G6**: Zero Secret Leakage — API keys, Fernet secrets, and credentials scrubbed from egress.
7. **G7**: Zero Fake Intelligence — `random.choice() == 0` in production resolution paths.
8. **G8**: Truthful Citations — citations empty `[]` when ungrounded; exact chunks when grounded.
9. **G9**: Bounded Context Window — 100+ turn sessions maintain bounded memory and prompt budgets.
10. **G10**: Configured != Available — active socket/HTTP ping required for provider availability.
11. **G11**: Deterministic Failover — automated fallback chain on transient provider errors.
12. **G12**: SSE Disconnect Abort — client disconnect detected, streaming aborted, event recorded.
13. **G13**: Unicode NFC Integrity — Tamil script and Tanglish phrases normalized to NFC.
14. **G14**: Audit Ledger Append-Only — all runtime events stored immutably in `mini_brain_llm_runtime_events`.
