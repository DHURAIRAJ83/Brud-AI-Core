"""Phase 12 supervised instruction-tuning: dataset validation, templates,
response-only label masking, evaluation, and bounded diagnostic generation.

Every function here is pure (no database access, no filesystem access beyond
what callers pass in explicitly) and operates on plain records/dicts, mirroring
the discipline established in ``core_model/training/`` during Phase 9-11.
"""
