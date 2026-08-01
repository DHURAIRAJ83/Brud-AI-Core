"""Pure policy modules for the floating Admin Assistant (Phase 8).

Nothing here talks to the database or calls a service -- these modules
are the single source of truth for "what pages exist", "what an
assistant mode means", and "what actions can be proposed", so the LLM
narrates from data the server already validated instead of inventing
page names or action ids of its own.
"""
