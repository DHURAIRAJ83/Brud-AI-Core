"""MB-04B: Response Quality Engine -- pure, deterministic modules.

Sits conceptually after MB-04A's prompt+generation step and before a
final response is returned. Does not touch MB-01/02/03/04 architecture,
MB-04A's Prompt Builder, or the Runtime state machine -- this package
only ever receives already-generated text (and the Response Plan that
produced it) and reports on / lightly cleans it. No AI, no embeddings,
no vector search anywhere in this package.
"""
