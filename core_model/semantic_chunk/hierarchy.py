"""Chunk hierarchy helpers (Phase 5, Step 9). Pure functions only."""

from __future__ import annotations

from collections.abc import Callable


def would_create_cycle(
    chunk_id: int, new_parent_id: int | None, parent_of: Callable[[int], int | None]
) -> bool:
    """`parent_of(id)` looks up the current `parent_chunk_id` of a chunk.
    Walks upward from `new_parent_id`; if `chunk_id` is ever reached, the
    assignment would create a cycle."""
    if new_parent_id is None:
        return False
    if new_parent_id == chunk_id:
        return True
    seen: set[int] = set()
    current: int | None = new_parent_id
    while current is not None:
        if current == chunk_id:
            return True
        if current in seen:
            # Existing data already has a cycle somewhere else -- do not
            # loop forever, and do not pretend this assignment is safe.
            return True
        seen.add(current)
        current = parent_of(current)
    return False
