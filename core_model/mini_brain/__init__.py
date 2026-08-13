"""Brud Mini Brain -- pure domain logic (MB-01: framework only, no model).

This package holds zero I/O: no database access, no HTTP, no file
reads. `backend/services/mini_brain_service.py` and
`backend/services/mini_brain_runtime.py` are the impure layer that
call into these functions, exactly the same split every other feature
in this codebase already uses (see `core_model/admin_assistant/` for
the closest analogous pair).
"""
