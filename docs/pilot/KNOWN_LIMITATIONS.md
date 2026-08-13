# Brud AI — Known Limitations (Internal Pilot)

Everything below is a **disclosed, intentional, or already-audited** limitation — not a surprise bug. If pilot behavior doesn't match this list, that's a real regression worth reporting; if it does, it's expected.

## Not supported at all

- **Real model training.** Every training-adjacent phase (dataset packaging, training execution) stops at "package built" or an explicit `BackendUnavailableError`. `TorchTrainingAdapter` imports `torch` but its train method is a disclosed stub — no code path in this repository trains a real model. See `docs/audit/MB46_PRODUCTION_READINESS_AUDIT.md` §1 (MB-22, the one RED subsystem in the entire audited inventory).
- **Process or container isolation for plugin execution.** Plugins run in-process via `importlib.exec_module()`, guarded only by declared-scope filesystem/network allow-lists — a plugin that ignores its own declared contract and calls `open`/`requests` directly is not stopped by anything below the governance-gate layer. Accepted risk, re-verified unchanged as of MB-46 §8.
- **Containerization.** No Dockerfile exists anywhere in the repository. This is a bare-process deployment.

## Dormant until configured (not a bug)

- **External AI Gateway (MB-21)** — real, code-complete comparison-dispatch system, dormant until an admin configures and enables a real external provider key under Provider Settings.
- **The local model runtime itself** — honestly reports "unavailable" everywhere (widget banner, Pilot Operations, diagnostics) until a `.gguf` file is placed inside the allowed model directory, or an external provider is configured as a fallback. See the runbook §2.
- **Prompt Optimization's "Generate" and "Compare" actions** — real, tested backend, but both require an actually-loaded model to produce output; they were not live-triggered against a real model during MB-47's own verification pass (only the deterministic, non-LLM "Detect language" action was). Expect them to report an honest unavailable state until step 2 above is done.

## Real, disclosed workflow constraints (not bugs)

- **Gateway → Dataset/RAG: RAG ingestion is atomic with export, not addable afterward.** The export route's content-hash duplicate detection means re-running export on an already-exported session with the "ingest to RAG" box newly checked will silently skip RAG ingestion for every already-exported record (they're detected as duplicates and the RAG-source-creation code path is skipped for duplicates). Check the RAG boxes on the *first* export of a session, not a later one. Disclosed directly in the page's own UI copy.
- **Retrieval profiles require the full real pipeline** — there is no one-click "just index this text" shortcut (see runbook §3). This is by design: every step is independently auditable and admin-gated.

## Scope boundaries for this pilot

- **The public chatbot app (`apps/chatbot`) is out of scope.** This pilot's surface is the admin dashboard only; `/api/admin/assistant/*` (the separate Phase-8 governed-assistant system) is untouched and unaffected by anything in the MB-45/47/48 line of work.
- **Concurrency**: SQLite WAL mode gives good concurrent reads but serializes writers through a single lock (5s busy timeout) — appropriate for a small internal pilot's admin-operator scale, not multi-tenant SaaS load.
- **Not every real backend capability has a dashboard surface yet.** MB-47 closed the two largest gaps (External Gateway Dataset/RAG Bridge, Prompt & Context Optimization); a small number of narrower dead UI bindings may still exist for other subsystems — check `docs/audit/MB46_PRODUCTION_READINESS_AUDIT.md` §2 for the current, evidence-based list before assuming a missing button is a bug rather than a known gap.
- **Full-ruleset `ruff` findings (~3,171, mostly line-length style)** are pre-existing and repository-wide, unrelated to pilot functionality — not addressed by this or the preceding stabilization phase. The dead-code-relevant subset (`--select F401,F841`) is the one actually tracked and cleaned (see `docs/audit/MB47_STABILIZATION_UI_EXPOSURE_REPORT.md` §4).

## What is real and pilot-ready

Everything not listed above — the full RAG pipeline, grounded chat (plain and grounded, with live citation switching verified by a real browser test), retrieval profile management, the External Gateway Dataset/RAG Bridge, Prompt & Context Optimization's language detection, plugin governance, CSRF protection, audit logging, and approval gates before retrieval activation — is real, tested, and independently re-verified as of `docs/audit/MB46_PRODUCTION_READINESS_AUDIT.md` and `docs/audit/MB48_INTERNAL_PILOT_HARDENING_REPORT.md`.
