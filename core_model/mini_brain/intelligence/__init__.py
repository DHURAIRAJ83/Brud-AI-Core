"""MB-03: Brud Intelligence Engine -- pure domain logic.

Every function in this package is deterministic: keyword/pattern
matching, fixed rule tables, and plain arithmetic. No model call, no
embedding, no vector math, no probability distribution anywhere.
`backend/services/mini_brain_intelligence_service.py` is the only
impure layer, and its only I/O is a read-only call into MB-02's
Knowledge Core plus a log write to MB-01's existing event log -- it
never mutates Knowledge Core, Admin Assistant, or any other module.
"""
