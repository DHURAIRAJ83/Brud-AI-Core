"""Phase 2.8E: a process-local, in-memory registry mapping a real
(execution_mode='gpu') MB-22 job's public_id to its live
`TorchTrainingAdapter`, plus a per-job lock serializing every
adapter-touching operation for that job.

This registry is NEVER the source of truth -- it is a pure runtime
cache. It exists only to make same-process, cross-service-instance
continuation cheap: when the same OS process already holds a job's
live adapter in memory (from an earlier stage in the same request, or
an earlier request served by this same worker), reusing it is free and
skips re-verifying/re-loading a checkpoint on every single stage call.
The authoritative state remains exactly what it already was before
this phase: the database, the governed dataset/tokenizer/Core-Model
artifacts, and the latest verified checkpoint on disk.

Process death, a different worker process, or an explicit eviction all
correctly and safely fall back to checkpoint-based reconstruction (see
`MiniBrainTrainingEngineService._ensure_adapter_for_job()`) -- never to
a stale, wrong, or cross-job entry. No secret or arbitrary
caller-supplied path is ever stored here; only the already-constructed,
already-identity-verified adapter object itself.

Lifecycle: REGISTER (via `get_or_create()`) -> USE (repeated `get()` /
`get_or_create()` calls from later requests in this same process) ->
PAUSE/CHECKPOINT (no registry change -- the adapter stays registered)
-> EVICT (`evict()`, called by the service on cancel/finalize/failure/
archive) -> RECOVER (a later `get_or_create()` on the same job id, now
finding nothing, reconstructs fresh from the checkpoint)."""

from __future__ import annotations

import threading
from typing import Any, Callable


class JobAdapterRegistry:
    def __init__(self) -> None:
        self._registry_lock = threading.Lock()
        self._entries: dict[str, Any] = {}
        self._job_locks: dict[str, threading.Lock] = {}

    def lock_for(self, job_public_id: str) -> threading.Lock:
        """Returns the single, stable per-job lock every adapter-touching
        stage call for this job must hold for its full duration --
        callers use this to serialize concurrent requests against the
        same job (Part 12), not to protect the registry dict itself
        (that has its own internal lock)."""
        with self._registry_lock:
            lock = self._job_locks.get(job_public_id)
            if lock is None:
                lock = threading.Lock()
                self._job_locks[job_public_id] = lock
            return lock

    def get(self, job_public_id: str) -> Any | None:
        with self._registry_lock:
            return self._entries.get(job_public_id)

    def get_or_create(self, job_public_id: str, factory: Callable[[], Any]) -> Any:
        """Callers MUST already hold `lock_for(job_public_id)` for the
        duration of this call -- that lock is what actually serializes
        two concurrent reconstruction attempts for the SAME job; this
        method's own internal lock only protects the registry dict
        itself, and is deliberately never held while `factory()` runs
        (checkpoint loading can take real, non-trivial time), so two
        DIFFERENT jobs' reconstructions never block each other."""
        with self._registry_lock:
            existing = self._entries.get(job_public_id)
            if existing is not None:
                return existing
        adapter = factory()
        with self._registry_lock:
            # Defensive only: a caller that reconstructed without holding
            # lock_for() first could race here. Never silently replace an
            # entry that already won -- the first adapter registered for a
            # job is the one every subsequent caller must keep using.
            existing = self._entries.get(job_public_id)
            if existing is not None:
                return existing
            self._entries[job_public_id] = adapter
            return adapter

    def evict(self, job_public_id: str) -> None:
        with self._registry_lock:
            self._entries.pop(job_public_id, None)
            self._job_locks.pop(job_public_id, None)

    def contains(self, job_public_id: str) -> bool:
        with self._registry_lock:
            return job_public_id in self._entries

    def size(self) -> int:
        with self._registry_lock:
            return len(self._entries)


# Process-local singleton -- one per OS process, exactly matching the
# scope this phase's design requires (Section 5 of the report: a
# registry entry must never be treated as authoritative across a
# process boundary).
REGISTRY = JobAdapterRegistry()
