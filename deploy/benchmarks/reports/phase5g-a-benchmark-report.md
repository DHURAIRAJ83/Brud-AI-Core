# Phase 5G-A — Production Benchmark Report (Uvicorn-only)

Branch: `phase-5-performance-polish` · HEAD: `a6f0d58` · Generated: 2026-08-14

All benchmarks run against an isolated temp SQLite database and dedicated
test ports (18097–18099) — never the real `data/` directory, never a port
a real service might be using. All test processes were confirmed cleaned
up (no orphans, temp dirs removed) after every run.

## 1. Cold-start wall-clock (`cold_start_benchmark.py`, 3 runs/mode)

| Mode | Min (s) | Avg (s) | Max (s) |
|---|---|---|---|
| dev | 11.57 | 12.53 | 14.45 |
| admin | 12.81 | 13.15 | 13.53 |
| **public** | **1.86** | **1.99** | **2.17** |
| **worker** | **0.89** | **0.94** | **0.99** |

`public`/`worker` are 6–14x faster than `dev`/`admin` — the direct payoff of Phase 5D–5F's deployment-mode filtering and torch deferral work. (Numbers ran ~2-3s higher across the board than earlier session baselines because the 10-minute soak test was running concurrently in the background during this measurement — noted for reproducibility, not a regression.)

## 2. Import-time breakdown (`startup_import_benchmark.py`)

| Mode | torch present | torch cumulative |
|---|---|---|
| dev | Yes | 2194 ms |
| admin | Yes | 2061 ms |
| **public** | **No** | — |
| **worker** | **No** | — |

`dev`/`admin`'s torch trigger is now fully attributed to one specific, previously-unaddressed chain (confirmed automatically by this script, matching Phase 5F-3's manual finding):
```
backend.services.base_model_resource_service
  -> core_model.pretraining_readiness.resource_profiles
  -> core_model.evaluation.architecture_checks
  -> torch
```
Reached via the always-eager `pretraining_readiness.py` admin route. Out of scope for Phase 5F-2 (which only targeted 6 named services) — flagged here as the next concrete lazy-import candidate if `dev`/`admin` startup time becomes a priority.

## 3. RSS memory snapshot (`rss_snapshot.sh`)

| Mode | RSS (MB) |
|---|---|
| dev | 389.2 |
| admin | 389.2 |
| **public** | **101.2** |
| **worker** | **47.9** |

Matches Phase 5F's investigation numbers closely (public was 101.2 MB there too) — confirms the torch-deferral work is stable and reproducible via automated tooling, not a one-off measurement.

## 4. Single-user latency (`latency_benchmark.py`, public mode, 50 sequential requests to `/api/health`)

| Metric | Value |
|---|---|
| min | 26.9 ms |
| avg | 38.5 ms |
| p50 | 35.4 ms |
| p95 | 66.7 ms |
| max | 72.2 ms |

Sequential only — concurrent/load testing is explicitly Phase 5G-B's scope. Latency here includes real network round-trip through a live uvicorn process, not just import cost.

## 5. Restart-recovery check (`restart_recovery_check.sh`, public mode)

| Check | Result |
|---|---|
| Initial startup healthy | ✅ |
| Port freed after simulated crash (SIGKILL) | ✅ |
| Recovery healthy after restart | ✅ |
| **Overall** | **PASS** |

Confirms the process can be killed and restarted cleanly. This validates the *mechanism* systemd's `Restart=always` (already configured in Phase 5E's unit files) relies on — it does not test systemd's own restart behavior over time, which requires actually installing the units (`install-systemd.sh`, not run in this phase).

## 6. 10-minute smoke soak (`smoke_soak_10m.sh`, public mode, 30s interval)

| Metric | Value |
|---|---|
| Duration | 600s (10 min) |
| Health checks | 20/20 healthy (**100% uptime**) |
| RSS first | 119,240 KB |
| RSS last | 119,256 KB |
| RSS max | 119,256 KB |
| RSS growth | **0.0%** (16 KB absolute, over 10 minutes) |
| **Overall** | **PASS** |

No leak signal at all over 10 minutes — RSS was essentially flat. This is a smoke-test proxy only; the full 1h/6h/24h soak tests (Phase 5G-B, not run here) have far more room to surface a slow leak that 10 minutes cannot.

## Summary

| Deliverable | Status |
|---|---|
| cold_start_benchmark.py | ✅ Built, executed |
| startup_import_benchmark.py | ✅ Built, executed |
| latency_benchmark.py | ✅ Built, executed |
| restart_recovery_check.sh | ✅ Built, executed — PASS |
| smoke_soak_10m.sh | ✅ Built, executed (real 600s run) — PASS |
| rss_snapshot.sh | ✅ Built, executed |
| This report | ✅ |

**Not run in this phase** (Phase 5G-B, documented/scripted only, per the approved gate decision): `soak_1h.sh`, `soak_6h.sh`, `soak_24h.sh`, `load_50.sh`, `load_200.sh`, `load_500.sh`, long-term RSS graphs.

## Notable finding for a future phase

`dev`/`admin` mode startup still costs ~2.1s in torch load via `base_model_resource_service.py` — a genuine, previously-unaddressed chain, not part of Phase 5F-2's six-file scope. If `dev`/`admin` cold-start time becomes a priority, this is the next concrete, well-evidenced lazy-import candidate (same pattern as the six files already fixed: verify every usage site, move to function scope, confirm `torch` absent from `sys.modules`).
