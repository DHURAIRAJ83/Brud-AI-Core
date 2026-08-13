"""MB-29: Local Model Auto-Setup & Provider Configuration Center --
policy/planning/catalog helpers for MB-27 (Provider Settings) and
MB-28 (LLM Runtime).

This phase's own pure-package rule is narrower than MB-26/27/28's:
"no fastapi, sqlite3, subprocess shell execution, or network access"
-- it does not forbid read-only filesystem/OS introspection, unlike
the stricter zero-I/O convention those phases used. Two modules use
that room deliberately and only for that purpose:
`hardware_probe.py` (real `psutil`-or-stdlib hardware introspection)
and `model_scanner.py` (real, confined, read-only directory listing
for `.gguf` files -- size/mtime stat calls only, never file content).
Both are disclosed here rather than silently exempted. Every other
module in this package is strictly pure: given data in, data out, no
I/O at all.

Real model loading, real provider secret storage/decryption, and all
database access continue to live entirely in MB-27/MB-28's existing
services -- this phase reuses them rather than duplicating any of it.
"""
