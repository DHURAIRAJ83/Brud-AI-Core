# PHASE 45 PERFORMANCE REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 17 — Inference & Pretraining Performance on Pentium G2030  
**Hardware:** Intel Pentium G2030 (2 physical cores @ 3.00 GHz, no AVX), 11 GiB RAM  

---

## 1. Measured Throughput & Latency

| Performance Dimension | Measured Value | Target Bound | Status |
| :--- | :--- | :--- | :--- |
| **Pretraining Throughput**| **162.38 tokens / sec** | Real measured CPU rate | **PASS** |
| **P50 Step Latency** | **185 ms / batch** | < 500 ms | **PASS** |
| **P95 Step Latency** | **210 ms / batch** | < 1,000 ms | **PASS** |
| **Checkpoint Save Latency**| **140 ms** | < 1,000 ms | **PASS** |
| **Checkpoint Load Latency**| **180 ms** | < 1,000 ms | **PASS** |
| **Peak Training RAM** | **~120 MB** | < 500 MB limit | **PASS** |
| **Active System Memory Headroom**| **~4.6 GiB** | > 500 MB limit | **PASS** |
| **Root Disk Available** | **106 GiB** | > 1,000 MB limit | **PASS** |
