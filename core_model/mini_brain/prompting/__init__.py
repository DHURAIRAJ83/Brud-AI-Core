"""MB-04A: Prompt & Context Optimization -- pure, deterministic modules.

Improves what the CPU model (integrated in MB-04.1) actually receives
as its prompt, without touching MB-01/02/03, the MB-04 Runtime
Manager's architecture, or the model itself. No AI, no embeddings, no
vector search anywhere in this package -- language detection,
Tanglish normalization, knowledge compression, and template selection
are all literal, rule-based text processing.
"""
