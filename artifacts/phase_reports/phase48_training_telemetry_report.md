# PHASE 48 TRAINING TELEMETRY REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 10 — Dual Telemetry Architecture  
**Telemetry Sinks:**  
- `artifacts/phase48_checkpoints/phase48_sovereign_job_01/phase48_worker_telemetry.jsonl`  
- `artifacts/phase48_checkpoints/phase48_sovereign_job_01/phase48_training_telemetry.jsonl`  

---

## 1. Multi-Tier Telemetry Separation

Telemetry is partitioned into three distinct levels:
1. **Worker-Level Telemetry:** Tracks state transitions (`QUEUED` $\rightarrow$ `INITIALIZING` $\rightarrow$ `TRAINING` $\rightarrow$ `CHECKPOINTING` $\rightarrow$ `STOPPED`), checkpoint loadings, and resource alarms.
2. **Run-Level Telemetry:** Step index, forward loss, rolling loss, learning rate, and slice throughput.
3. **Global Accumulation Telemetry:** Global cumulative token counts cross-verified with `Phase48TokenLedger`.

---

## 2. Sample Telemetry Record

```json
{
  "timestamp": 1787999215.8,
  "worker_id": "worker_C",
  "job_id": "phase48_sovereign_job_01",
  "run_id": "phase48_run_C",
  "step": 68,
  "train_loss": 3.9714,
  "val_loss": 4.1620,
  "run_tokens": 736,
  "global_tokens": 4256,
  "tokens_per_second": 118.2,
  "elapsed_seconds": 6.22,
  "state": "STOPPED"
}
```
