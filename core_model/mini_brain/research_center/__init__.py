"""MB-10: Brud Mini Brain AI Research & Knowledge Acquisition Center
-- pure decision modules only.

MB-10 turns MB-09's planning output into a managed research process:
build a request, select providers from a real (never hardcoded)
registry, run either a Local Draft or a Multi-Provider Consensus pass,
validate evidence and citations, resolve conflicts and duplicates,
score research quality across seven dimensions, and assemble a draft
dataset that is always `verified: false` until an admin says
otherwise.

Every module here is a deterministic function of its inputs: no file
I/O, no database access, no network access, no randomness, and no
call to any external AI provider -- confirmed by audit before writing
this phase (see MB-09's own audit; nothing changed since). MB-10 never
starts training, never deploys or activates a model, never modifies a
dataset, never approves a dataset, and never modifies MB-06/MB-07/
MB-08/MB-09. Every dataset draft must go through RAG Sandbox before
MB-06 Learning Supervisor is even considered -- there is no path from
a draft directly to the Training Engine anywhere in this package or
`backend.services.mini_brain_research_center_service`.
"""
