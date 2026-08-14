# Brud AI — Release Candidate Manifest

## Build identity

- Branch: `phase-5-performance-polish`
- Commit SHA (full): `6cd80d015831c0bf5ba372c436fa54829b6baddf`
- Commit SHA (short): `6cd80d0`
- Build date (UTC): 2026-08-14
- Python: 3.13.5
- Node: v24.18.0
- npm: 11.16.0

## Deployment mode summary

Three independent single-process uvicorn deployment modes, each with its own systemd unit, env template, and sandboxing profile (Phase 6C):

| Mode | Bind | Internet-reachable | Sandboxing | Notes |
|---|---|---|---|---|
| `public` | `0.0.0.0` | Yes, behind a TLS reverse proxy only | Full (`PrivateDevices`, `MemoryDenyWriteExecute`, `SystemCallFilter=@system-service`) | Confirmed torch-free (Phase 5F-3) |
| `admin` | `127.0.0.1` | No — proxy-only, separate hostname | Conservative (omits the three above — may load torch/GPU inference on demand, never validated on real GPU hardware) | `BRUD_ADMIN_COOKIE_SECURE=true` |
| `worker` | `127.0.0.1` | No — never proxied | Full, same as `public` | Confirmed torch-free (Phase 5F-3) |

## Security features enabled (verified present in source, this commit)

- `SecurityHeadersMiddleware` — `backend/main.py:69`, `backend/core/security_headers_middleware.py:28`
- `GlobalRateLimitMiddleware` — `backend/main.py:68`, `backend/core/rate_limit_middleware.py:33`
- `BRUD_ADMIN_COOKIE_SECURE=true` — `deploy/env/admin.env.example:6`
- `ProtectSystem=strict` — all three systemd units (`deploy/systemd/brud-{public,admin,worker}.service`)
- Automated backup encryption — `deploy/systemd/brud-backup-encryption.timer`, referenced in both runbooks

Full grep evidence: `deploy/release-candidate/reports/security-inventory.txt`

## Benchmark report references

| Phase | Report | Location |
|---|---|---|
| 5G-A (cold start / import / latency benchmarks) | `phase5g-a-benchmark-report.md` | `deploy/benchmarks/reports/phase5g-a-benchmark-report.md` (tracked) |
| 7A (1-hour soak, PASS) | `smoke_soak_10m.json` | `deploy/benchmarks/reports/smoke_soak_10m.json` (untracked, generated — **note:** this file's name is a holdover from the original 10-minute smoke-test script; it currently holds the Phase 7A 1-hour run's output, `duration_s: 3600`) |
| 7B-1 (50-user load test) | `load_test_report.json` | **Not present under `deploy/`** — this run only ever wrote to the session's ephemeral scratchpad directory, not archived to the repo. The numbers are recorded in that phase's conversation report only. |
| 7B-1R (concurrency remediation investigation) | — | **No JSON artifact was ever produced.** Findings were computed and reported inline in conversation only. |
| 7C-1 (pilot concurrency remediation) | `before.json` / `after.json` | **Not present under `deploy/`** — scratchpad only. **Additionally: the underlying code change (async→def on 3 routes) was never committed** — it existed only as an uncommitted working-tree diff and has been stashed (`git stash`, message: "Phase 7C-1 pilot: async->def conversion (inconclusive, not adopted)") ahead of this RC snapshot so this manifest reflects what is actually shipped at `6cd80d0`, not an unresolved experiment. |

This is a real gap, not an oversight being glossed over: three of the five Phase 7 evidence sets have no durable, repo-resident artifact. See `RELEASE_CHECKLIST.md`'s "benchmark reports archived" item, left unchecked for this reason.

## Known open items (from `PRODUCTION_HARDENING_CHECKLIST.md`'s "Still open" section)

- Global rate limiter is in-process/per-worker — multi-worker deployment would silently multiply the effective limit (no shared store).
- `admin`'s systemd sandboxing is intentionally less restrictive than `public`/`worker` (untested against real GPU/torch code paths).
- `CPUQuota` is not set on any systemd unit — no load-test data exists to size it safely.
- Known, unfixed dependency vulnerabilities (deliberately not upgraded this phase): frontend `nanoid` (high), `postcss` (moderate); backend `pillow`, `starlette`, `cryptography`, `pytest`, `diskcache`.
- Backend dependency pinning uses range pins (`>=X,<Y`), not exact pins — a different governance model from the frontend's exact-pin convention, by design, not an oversight.
- Phase 7B-1 found response latency degrades sharply under 50-way concurrency on a DB-touching route (~30ms sequential → ~1.3s p50 at 50 concurrent) due to synchronous SQLite I/O inside `async def` routes with zero threadpool offload anywhere in `backend/`. Phase 7C-1's pilot fix for 3 routes produced an **inconclusive** result on this hardware (mixed before/after numbers, high run-to-run variance) and was not adopted. **This remains unresolved.**

No unresolved item listed above is being claimed as fixed by this release candidate.
