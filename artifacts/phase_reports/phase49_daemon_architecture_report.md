# Phase 49 Continuous Training Daemon Architecture Report

## 1. Executive Summary
Phase 49 establishes a standing, restart-safe, multi-day background continuous training daemon (`Phase49TrainingDaemon`) governing autonomous training slice execution across bounded execution windows without violating hardware, database, or Public Chat constraints.

## 2. Daemon Architecture Specifications
* **Class**: `core_model.training.phase49_training_daemon.Phase49TrainingDaemon`
* **Finite State Machine**: 14 strictly guarded states:
  * `STARTING`, `RECOVERING`, `IDLE`, `DISPATCHING`, `TRAINING`, `CHECKPOINTING`, `LEDGER_COMMIT`, `ARCHIVING`, `RESOURCE_WAIT`, `QUEUE_RECOVERY`, `CHECKPOINT_RECOVERY`, `FAILED`, `SAFE_STOP`.
* **Hardware Clamp**:
  * `max_training_workers`: 1 (Hard physical singleton)
  * `torch_threads`: 2 (Matches Intel Pentium G2030 physical 2-core topology)
* **Exclusive Single-Instance Lease**:
  * File: `artifacts/training_lease.lock`
  * Tracks: `daemon_id`, `pid`, `acquired_at`, `expires_at`, `heartbeat_interval`
  * Mutual exclusion: Rejects competing daemons; auto-cleans stale dead PIDs.
* **Heartbeat & Telemetry**:
  * Heartbeat snapshot: `artifacts/phase49_daemon_heartbeat.json` (contains PID, uptime, state, current_job_id, current_checkpoint, cumulative_tokens, RAM headroom, disk headroom)
  * Telemetry log: `artifacts/phase49_daemon_telemetry.jsonl` (dual-stream telemetry with millisecond timestamps).
* **Crash Window Protection**:
  * Mandatory Correction 3: Binds commit to idempotency key `f"{run_id}:{child_checkpoint_id}:{parent_checkpoint_id}"`. If a process crashes after checkpointing but before ledger commit, retrying with the same idempotency key succeeds once and rejects duplicate commit without inflating token totals.

## 3. Mandatory Correction Compliance
1. **Daemon != Unlimited Training**: Daemon lifetime is long-running; each training slice is bounded to `max_slice_duration` (e.g. 5.0s) and step ceiling (50 steps).
2. **Transactional Ledger Commit**: Sequence: `checkpoint saved` -> `verified integrity` -> `ledger block prepared` -> `ledger commit` -> `archived`.
3. **Crash Window Idempotency**: Idempotency key tracking prevents double token counting on crash restarts.
4. **Dependency-Aware Retention**: Protects `ACTIVE LINEAGE`, `CURRENT RESUME`, `GOLD`, and `REPRODUCTION REQUIRED` checkpoints.
5. **Statistical Claim Separation**: Descriptive measurements vs statistically defensible evidence reported separately.
6. **Cryptographic Dataset-Checkpoint Binding**: Verifies `dataset_manifest_hash` match before allowing checkpoint resume.
