# PHASE 46 RESOURCE AND HOST REALITY REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 15 — Resource Safety & CPU Host Reality  
**Hardware:** Intel(R) Pentium(R) CPU G2030 @ 3.00 GHz, 2 physical cores, 2 threads  

---

## 1. Resource Consumption & Headroom Profile

| Resource Metric | Measured Value | Threshold / Bound | Guard Status |
| :--- | :--- | :--- | :--- |
| **CPU Worker Threads** | 2 threads | `num_threads = 2` | **ENFORCED** |
| **Available RAM** | ~4.6 GiB | > 500 MB limit | **HEALTHY** |
| **Peak Training RAM** | ~145 MB | < 500 MB limit | **HEALTHY** |
| **Available Disk (/)** | ~106 GiB | > 1,000 MB limit | **HEALTHY** |
| **Throughput (Tokens/s)**| **267.80 tokens/sec** | CPU execution rate | **SUSTAINED** |
| **Step Latency (P50)** | **118 ms / step** | < 500 ms | **HEALTHY** |
| **Step Latency (P95)** | **145 ms / step** | < 1,000 ms | **HEALTHY** |

---

## 2. ResourceGuard Fail-Safe Verification

If available memory drops below 500 MB or disk space drops below 1,000 MB:
- The pretraining loop terminates immediately without dropping weights.
- Current optimizer and scheduler states are saved to disk with SHA-256 manifests.
- Telemetry is flushed, preventing system out-of-memory or disk-full lockups.
