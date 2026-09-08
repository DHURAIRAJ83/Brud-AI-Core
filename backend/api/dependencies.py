"""Shared FastAPI dependencies."""

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends

from backend.core.config import Settings, get_settings

if TYPE_CHECKING:
    from backend.database.connection_pool import ConnectionPool

SettingsDependency = Annotated[Settings, Depends(get_settings)]


def get_pool() -> "ConnectionPool | None":
    """Phase 7C-33: default (unoverridden) resolution -- no shared pool.

    Mirrors `get_settings()`'s override mechanism exactly: `create_app()`
    replaces this via `application.dependency_overrides[get_pool] = ...`
    with a closure returning that specific app instance's one
    `ConnectionPool` (constructed once in `lifespan`), so every app
    instance gets its own pool identity and no app instance shares
    another's. Any caller (test app instances that never override this,
    CLI code that never goes through FastAPI at all) that never triggers
    the override keeps getting `None` here, which is `BaseRepository`'s/
    `CorpusRepository`'s own existing "no pool" default -- byte-for-byte
    today's unpooled behavior."""

    return None


PoolDependency = Annotated["ConnectionPool | None", Depends(get_pool)]
