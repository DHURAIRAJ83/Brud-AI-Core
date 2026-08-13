"""MB-07: Brud Mini Brain Release Pipeline -- pure decision modules only.

Every module here is a deterministic function of its inputs: no file
I/O, no database access, no network access, no randomness. The actual
checkpoint loading, GGUF file writing, quantization byte-packing, model
loading, and timing measurements happen in
`backend.services.mini_brain_release_pipeline_service`, which calls
these modules to turn raw facts into pass/fail decisions and reports.

MB-07 never trains a model, never edits a dataset, and never modifies
a checkpoint -- it converts an already-approved, already-promoted
checkpoint (from MB-06) into a production-ready GGUF artifact, then
gates every irreversible step (version creation, activation) behind an
explicit admin decision.
"""
