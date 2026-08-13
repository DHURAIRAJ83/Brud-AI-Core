"""MB-08: Brud Mini Brain Continuous Learning & Feedback Engine --
pure decision modules only.

Every module here is a deterministic function of its inputs: no file
I/O, no database access, no network access, no randomness, no AI. The
actual reads of Public Chat routing/feedback events and Knowledge Gap
Registry cases happen in
`backend.services.mini_brain_continuous_learning_service`, which
calls these modules to turn already-fetched, real production evidence
into deterministic, evidence-cited reports.

MB-08 never retrains a model, never edits a dataset, never modifies a
checkpoint, and never activates a model -- it only observes, analyzes,
recommends, and prepares a report for an explicit admin decision.
Approving that decision records the admin's judgment; it does not, by
itself, start anything in MB-06 or MB-07 -- an admin acts on the
report's recommendations manually, through those phases' own UIs.
"""
