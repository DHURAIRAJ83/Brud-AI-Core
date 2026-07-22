# Training Crash Recovery

## Overview

`training_recovery_attempts` records every attempt to recover a pretraining job from checkpoint after a crash, lease expiry, or manual recovery request. Recovery is audited, validated, and reversible only through checkpoint transfer or manual reset.

## Recovery Types

| Type | Cause |
|------|-------|
| `stale_lease` | Worker heartbeat stopped; job is now orphaned |
| `worker_crash` | Worker died without graceful shutdown |
| `manual_resume` | Admin requested resume from paused job |
| `pause_resume` | User requested resume from paused run (promotion) |
| `checkpoint_recovery` | Admin explicitly requested recovery from checkpoint |

## Recovery Status Lifecycle

```text
validating   → checking checkpoint integrity and eligibility
recovering   → loading state and restarting training
completed    → recovery completed cleanly
completed_with_warnings  → completed but had issues (metadata log)
failed       → recovery failed due to error
cancelled    → recovery was attempted then cancelled
```

## Recovery Fields

```python
class RecoveryAttempt:
    public_id: str
    pretraining_job_id: int
    source_worker_id: str | None                    # Pre-crash owner
    recovering_worker_id: str                       # New owner
    recovery_type: str
    status: str
    source_checkpoint_public_id: str | None         # Corrupt? null
    recovered_step: int | None
    recovered_tokens: int | None
    previous_lease_generation: int
    new_lease_generation: int
    validation_summary_json: dict
    error_code: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
```

## Recovery Workflow

```text
crash/heartbeat_stop detected
      ↓
job marked recoverable (status = 'recoverable')
      ↓
latest verified checkpoint candidate selected
      ↓
recovery attempt recorded (status = 'validating')
      ↓
checkpoint and referenced artifacts verified
      ↓
recovery attempt updated (status = 'recovering')
      ↓
new lease generation assigned
      ↓
owner loads checkpoint state
      ↓
optimization continues from next uncompleted step
      ↓
recovery attempt completed (status = 'completed')
```

## Validation Rules

Before any checkpoint is used for recovery:

1. **Checkpoint status** must be `completed` or `verified`
2. **Combined checksum** must pass
3. **Model checksum** must match current architecture
4. **Optimizer checksum** must pass
5. **Scheduler checksum** must pass
6. **Trainer-state checksum** must pass
7. **Dataset checksum** must match current dataset version
8. **Tokenizer checksum** must match current tokenizer version
9. **Architecture config checksum** must match current core model version
10. **Training config checksum** must match current configuration

Any failure triggers:

* Record blocking issue
* Mark checkpoint as `corrupt` in database
* Try previous verified eligible checkpoint only via explicit fallback
* Log audit event

## Resume Guarantees

Standard Phase 9 phase 10 workers enforce:

* **Exact step continuation:** Resume starts at `completed_steps + 1`
* **No repetition:** Steps already completed are never repeated
* **Monotonic counter:** `processed_tokens` and `completed_steps` only increase
* **RNG restoration:** Random number generator state is restored
* **Optimizer state:** No parameters are overwritten
* **Scheduler state:** Learning rate schedule is restored
* **Split isolation:** Train data never enters validation

## Phase 10 Enhancement

Phase 10 adds:

1. **Heartbeat-based recovery** when lease expires
2. **Recorded recovery attempts** with validation summaries
3. **Lease generation fencing** to prevent stale writes after takeover
4. **Audit trail** for every recovery event
5. **Recovery health checks** in Admin Dashboard
6. **Recovery CLI utilities** for investigating failed attempts

## Phase 9 Compatibility

Phase 9 existing recovery is preserved:

* **Manual checkpoint reloading** via service
* **Event-based pause/resume** via job status flags
* **Pause checkpoint retention** as `checkpoint_kind = 'pause'`

Phase 10 does not remove or alter this recovery path; it adds additional automated recovery and enforcement.

## No Historical Data Leaked

Recovery audit records contain:

* Core identifiers only
* Checksum prefixes (first 12 chars)
* Summary of validation results
* Error codes for debugging

No raw checkpoint data, full token streams, or optimizer tensors are logged.