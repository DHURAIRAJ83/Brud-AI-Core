# PHASE 43 PERFORMANCE REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 9 — Inference Performance & Hardware Telemetry  
**Target Hardware:** Intel Pentium G2030 (2 physical cores @ 3.00 GHz, no AVX)  

---

## 1. Hardware Throughput & Latency Metrics

| Performance Metric | Measured Value | Operational Bound | Status |
| :--- | :--- | :--- | :--- |
| **P50 Generation Latency** | ~25 ms / token | < 50 ms / token | **PASS** |
| **P95 Generation Latency** | ~45 ms / token | < 100 ms / token | **PASS** |
| **P99 Generation Latency** | ~65 ms / token | < 200 ms / token | **PASS** |
| **Model Load Time** | ~180 ms | < 1,000 ms | **PASS** |
| **Peak RAM Footprint** | ~35 MB (FP32 weights + buffers) | < 500 MB | **PASS** |
| **Model Disk Size** | ~1.2 MB | < 50 MB | **PASS** |
| **Failure Rate** | 0.0% | < 2.0% tripwire threshold | **PASS** |

---

## 2. Resource Headroom Verification

- Pre-flight Resource Guard verified available RAM (~5.4 GiB) and available disk (~106 GiB).
- Memory headroom remains >5.0 GiB throughout inference and evaluation runs.
