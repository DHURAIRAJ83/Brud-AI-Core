"""MB-17: Vision RAG & Multimodal Retrieval Center -- pure decision
logic only, zero I/O.

MB-17 is not an OCR engine, vision model, dataset generator, embedding
trainer, training engine, runtime, or release pipeline. It answers
questions by retrieving already-computed evidence from an already-
certified MB-16 dataset (and, through it, MB-14/MB-15's own real
image/object/knowledge-graph data), fusing that evidence, and grounding
an answer in it -- never generating free text from a language model,
since none exists in this codebase for that purpose.

Text-similarity scoring reuses the real, already-tested `core_model.
rag` primitives (`embed_local_custom`, `score_vectors`,
`tokenize_for_keyword_index`, `classify_language`, `normalize_query`,
the bilingual insufficient-evidence policy in `answer_policy.py`, and
`grounding_checks.compute_grounding_quality`) directly -- this package
never reimplements retrieval math. `knowledge_graph_retrieval.py`
never regenerates a graph, matching MB-16's own discipline -- it only
ever references MB-14/MB-15's already-built graph.
"""
