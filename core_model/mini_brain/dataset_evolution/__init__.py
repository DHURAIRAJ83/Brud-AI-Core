"""MB-11: Brud Mini Brain Autonomous Dataset Evolution & Knowledge
Factory -- pure modules only, zero I/O.

MB-11 is not a Training Engine, a Dataset Editor, or a Runtime. It
continuously analyzes what MB-05, MB-05.1, MB-08, MB-09, and MB-10
have already computed and plans how Brud AI's dataset should evolve --
recommendation and planning only. Every module here is a pure
function: no database access, no HTTP calls, no file I/O, and no path
that can create, update, delete, train, deploy, or modify RAG. Every
plan produced is explicitly non-binding until an admin approves it
through `MiniBrainDatasetEvolutionService`, and even an approved plan
is never executed automatically -- expansion, merges, splits, and
synthetic dataset creation all happen manually, elsewhere, afterward.
"""
