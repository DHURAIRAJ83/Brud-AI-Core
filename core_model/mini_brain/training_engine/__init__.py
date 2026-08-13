"""MB-22: Brud Mini Brain Real Training Execution Engine -- pure
planning/validation logic.

The first Mini Brain phase allowed to orchestrate a real training
workflow, but always behind explicit, fresh, per-job admin
authorization, and always CPU-first with GPU as an optional path.
Every module here is deterministic, pure, and JSON-serializable: no
database access, no filesystem writes, no model training. This module
never auto-starts training after package approval, never auto-deploys
or auto-promotes a trained model, and never decides anything a human
admin did not explicitly authorize.
"""
