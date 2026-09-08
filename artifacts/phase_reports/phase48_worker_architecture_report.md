# PHASE 48 WORKER ARCHITECTURE REPORT

**Date:** 2026-08-29  
**Status:** VERIFIED  
**Workstream:** Workstream 2 — Background Worker Engine  
**Module:** `core_model/training/phase48_training_worker.py`  

---

## 1. 10-State Finite-State Machine

In accordance with **Mandatory Correction 2**, the worker is not an unconstrained, runaway background daemon. Instead, it follows a deterministic finite-state machine with bounded execution slices:

```text
QUEUED ──> INITIALIZING ──> TRAINING ──> CHECKPOINTING ──> STOPPED / COMPLETED
               │                │               │
               ▼                ▼               ▼
           RECOVERING        PAUSED       RESOURCE_WAIT
```

| State | Allowed Next States | Description |
| :--- | :--- | :--- |
| `QUEUED` | `INITIALIZING`, `CHECKPOINTING`, `STOPPED`, `FAILED` | Job registered and waiting for worker allocation |
| `INITIALIZING` | `TRAINING`, `CHECKPOINTING`, `RECOVERING`, `FAILED`, `STOPPED` | Loading model architecture, RNG, and weights |
| `TRAINING` | `CHECKPOINTING`, `PAUSED`, `RESOURCE_WAIT`, `COMPLETED`, `STOPPED`, `FAILED`| Real forward, loss, backward, optimizer step |
| `CHECKPOINTING` | `TRAINING`, `QUEUED`, `INITIALIZING`, `COMPLETED`, `STOPPED`, `FAILED`, `PAUSED` | Atomic checkpoint flush and manifest creation |
| `PAUSED` | `INITIALIZING`, `TRAINING`, `STOPPED`, `FAILED` | Explicit administrator pause or graceful pause |
| `RESOURCE_WAIT` | `TRAINING`, `STOPPED`, `FAILED` | Host resource limits breached; polling for headroom |
| `RECOVERING` | `INITIALIZING`, `TRAINING`, `FAILED`, `STOPPED` | Restoring from last verified checkpoint after crash |
| `COMPLETED` | *(Terminal State)* | Target steps or target tokens fulfilled |
| `FAILED` | `RECOVERING`, `STOPPED` | Unrecoverable error encountered; fail closed |
| `STOPPED` | `INITIALIZING`, `QUEUED` | Gracefully stopped at time bound or user request |

---

## 2. Invalid Transition Defense

Every call to `transition_to(target_state)` verifies the transition against `VALID_TRANSITIONS`. Any illegal transition raises `WorkerTransitionError` and immediately halts execution, guaranteeing fail-closed safety.
