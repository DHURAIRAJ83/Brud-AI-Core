# Brud AI — Production Acceptance Summary

Build: `phase-5-performance-polish` @ `6cd80d0` · 2026-08-14

## Acceptance table

| Area | Status | Evidence |
|---|---|---|
| Security hardening (headers, rate limiting, TLS templates, proxy trust) | IMPLEMENTED & VERIFIED | Phase 6B-1/6B-3; `security-inventory.txt` |
| Backup encryption | IMPLEMENTED & AUTOMATED | Phase 6B-2; `brud-backup-encryption.timer` present |
| systemd sandboxing | IMPLEMENTED (asymmetric by design) | Phase 6C; `admin` deliberately more conservative than `public`/`worker` — see RC_MANIFEST |
| SBOM | GENERATED | Phase 6D; `sbom-inventory.txt` (3 CycloneDX files) |
| Dependency governance | PINNED, AUDITED, KNOWN GAPS OPEN | Phase 6D; frontend exact-pinned (no `"latest"` remaining), backend range-pinned + manifest-reconciled; several known CVEs deliberately not upgraded this phase |
| 1-hour soak | **PASS** | Phase 7A; 100% uptime, 0.3% RSS growth, `smoke_soak_10m.json` |
| 50-user load test | **CONDITIONAL PASS** | Phase 7B-1; 100% success rate, zero errors, but p50 latency degrades ~45x under 50-way concurrency (30ms → ~1.3s) — stable and correct, not fast, under load |
| Concurrency remediation | **INVESTIGATION COMPLETE / OPTIMIZATION OPEN** | Phase 7B-1R + 7C-1; root cause identified precisely (sync SQLite I/O in `async def` routes, zero threadpool offload anywhere in `backend/`), a 3-route pilot fix was built and measured but gave an inconclusive result on this hardware and was **not adopted** (stashed, not committed) |
| Overall verdict | **RC-READY (pilot/small-scale deployment)** | See rationale below |

## Verdict rationale

No critical, unaddressed security gap was found in this deployment's actual attack surface: TLS termination, admin network isolation, security headers, rate limiting, process sandboxing, and automated encrypted backups are all implemented and empirically verified working (not just present in config). The open items are bounded and understood, not unknowns:

- Dependency CVEs are documented with fix versions identified, deliberately deferred (not silently ignored) pending their own upgrade-and-test pass.
- The concurrency ceiling is a **correctness-preserving capacity limit**, not a security or stability defect — Phase 7B-1 showed 100% success and no crashes even at 50 concurrent users, just degraded latency. This makes the system safe to run at modest/pilot scale while remaining honestly not yet validated for high-concurrency production traffic.
- `admin` mode's narrower sandboxing is a deliberate, documented, risk-aware choice (unvalidated GPU code paths), not an oversight.

This verdict is scoped to **pilot / small-scale deployment**. It is not a claim of production-scale readiness under sustained high concurrency — that remains gated on resolving the concurrency bottleneck (Phase 7C-1's "Still open" item), which was investigated but not fixed in this build.

## Evidence gap disclosed

Three of the five Phase 7 benchmark runs (7B-1, 7B-1R, 7C-1) produced no durable, repo-archived artifact — their evidence exists only in this session's conversation record and ephemeral scratchpad files. See `RC_MANIFEST.md`'s benchmark table for the precise breakdown. This is reflected in `RELEASE_CHECKLIST.md`'s "benchmark reports archived" item being left unchecked.
