"""MB-04C: Model Capability Optimization -- pure, deterministic modules.

Sits between the Runtime's raw response and the final response,
alongside (not inside) MB-04B's Quality Engine. This package does not
build prompts (that stays MB-04A's job) and does not run inference
itself (that stays MB-04's Runtime Manager's job) -- it only decides
HOW to call the existing Runtime (generation strategy, token budget,
retry) and evaluates what came back (length, stability). No AI model,
no embeddings, no vector search anywhere in this package.
"""
