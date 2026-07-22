# Training Worker Leases

## Overview

`worker_heartbeats` provides reliable tracking of active workers and their ownership of pretraining jobs. Workers report heartbeats to claim, renew, and release ownership of running jobs.

## Heartbeat Status Lifecycle

```text
starting  → worker identifies itself to the service
idle       → worker is ready but not running any job
claiming   → worker is validating lease eligibility and parameters
running    → worker is actively training on a job
pausing    → worker received pause request, safely completing current step
recovering → worker recovered a job from an abandoned checkpoint
stopping   → worker received shutdown request
stopped    → worker gracefully exited or crashed without recovering
failed     → worker process terminated unexpectedly
```

## Lease Fields

```python
class WorkerHeartbeat:
    public_id: str
    worker_id: str                          # Server-generated, safe reference
    status: str
    current_job_public_id: str | None
    hostname_hash: str                      # Safe instance reference
    process_started_at: datetime
    last_heartbeat_at: datetime
    lease_expires_at: datetime
    shutdown_requested: bool
    metadata_json: dict
    created_at: datetime
    updated_at: datetime
```

**Key guarantee:** A `worker_id` is **server-generated** and never exposed directly to workers. Workers identify only by `hostname_hash` and lease generation token.

## Lease Generation

Every running job obtains a lease with:

* **Lease generation:** Monotonically incrementing integer for fencing
* **Lease expires after:** Configurable interval (e.g., 30 seconds)
* **Heartbeat interval:** Configurable minimum (e.g., 3 seconds)

When a job is claimed:

1. Repository generates the next lease generation
2. Repository records the job owner ID and lease expiry
3. Repository returns the generation to the caller
4. Caller must return the generation on every heartbeat

## Heartbeat Protocol

**Worker → Backend (heartbeat):**
```python
{
    "status": "running",
    "current_job_public_id": "<job_id>",
    "lease_generation": 7,
    "hostname_hash": "safe_ref",
}
```

**Backend → Worker (response):**
```python
{
    "valid": true,
    "next_heartbeat_at": "2026-07-22T10:15:37Z"
}
```

If the generation is stale or the job lease has expired:

```python
{
    "valid": false,
    "error": "stale_generation" | "lease_expired" | "not_owner"
}
```

**Backend → Worker (shutdown):**
```python
{
    "action": "shutdown" | "pause",
    "grace_period_seconds": N
}
```

## Lease Validation in Phase 9

Phase 9 already includes some lease validation in `pretraining_service._claim()`:

1. Job status check (must be `queued`)
2. Status mutation to `running`
3. Worker ID assignment
4. Event logging

This is **sufficient for Phase 9** but Phase 10 extends it with:

1. Heartbeat table for monitoring
2. Lease generation fencing
3. Stale worker detection
4. Lease expiry automatic job recovery
5. Best-effort graceful shutdown

## Stale Worker Detection

The heartbeat manager periodically queries heartbeats and identifies stale entries:

```python
def cleanup_stale_heartbeats():
    now = time.time()
    stale_heartbeats = db.execute("""
        SELECT *
        FROM worker_heartbeats
        WHERE last_heartbeat_at < now - HEARTBEAT_TIMEOUT
        AND status NOT IN ('stopped', 'failed')
    """).fetchall()

    for hb in stale_heartbeats:
        if hb.current_job_public_id:
            mark_job_recoverable(hb.current_job_public_id)
        mark_heartbeat_stale(hb.public_id)
```

## Automatic Recovery

When a job is marked recoverable:

1. Detect eligible verified checkpoint
2. Create `training_recovery_attempts` record
3. Mark start time and source status
4. Wait for active lease expiry
5. Allow new worker to claim
6. Load checkpoint state
7. Resume training from next uncompleted step

## No Process detail Exposure

Workers **never** send process ID (PID) or full hostnames. They send only:

* Safe instance reference (`hostname_hash`)
* Server-generated worker ID
* Lease generation token

The backend logs PID as audit data but never exposes it to the UI or other workers.

## Phase 10 Integration

Phase 10 extends the worker to:

1. **Start** with `status = 'starting'`
2. **Update** on each heartbeat to `status = 'running'`
3. **Extend lease** on every heartbeat by regeneration
4. **Gracefully shut down** on stop signal by transition to `status = 'stopping'`
5. **Report leak** if shutdown fails by `status = 'failed'`
6. **Clean up** after graceful exit by `status = 'stopped'`

## Phase 9 Continuity

Phase 9 workers remain compatible with Phase 10 systems by:

1. Returning lease generation on claim
2. Including lease generation on status updates
3. Responding to shutdown requests
4. Logging exit status

Phase 9 code can be evolved in place without breaking existing functionality.