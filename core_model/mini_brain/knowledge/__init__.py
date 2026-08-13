"""MB-02: Brud Knowledge Core -- pure domain logic (validation,
coverage). Zero I/O, same split as every other `core_model/<area>`
package in this codebase. No embeddings, no vector math, no semantic
scoring of any kind -- every function here operates on plain dicts
already fetched by the repository layer."""
