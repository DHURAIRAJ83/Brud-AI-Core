"""MB-12: Brud Mini Brain Autonomous AI Knowledge Pipeline Coordinator
-- pure modules only, zero I/O.

MB-12 is not a Training Engine, a Dataset Writer, or a Runtime. It
coordinates the lifecycle already tracked by MB-08, MB-09, MB-10, and
MB-11 into one unified, admin-controlled pipeline view -- orchestration,
validation, scheduling, and reporting only. Every module here is a
pure function: no database access, no HTTP calls, no file I/O, and no
path that can train, deploy, write a dataset, or modify RAG. MB-12
deliberately never calls RAG Sandbox itself (see the completion
report's Finding 1) -- it only ever reads a RAG result MB-06 or MB-11
already produced.
"""
