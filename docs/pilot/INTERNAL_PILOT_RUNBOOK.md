# Brud AI — Internal Pilot Runbook

**Audience:** the admin(s) operating Brud AI for an internal pilot with daily users.
**Scope:** how to start it, configure a local model, create a retrieval profile, verify grounded chat works, check on it day to day, and what to do when something goes wrong.

---

## 1. Starting the backend and frontend

From the repository root, with the venv already set up (`. venv/bin/activate` if you haven't):

```bash
make backend   # FastAPI backend  -> http://127.0.0.1:8000  (docs at /docs)
make admin     # Admin dashboard  -> http://localhost:5174
make chatbot   # Public chatbot   -> http://localhost:5173 (not part of the pilot surface)
make dev       # all three at once, with child-process cleanup on exit
```

For a pilot, run `make backend` and `make admin` (skip `make chatbot` unless the pilot also needs the public-facing chat surface). Both processes log to stdout; keep them in a terminal multiplexer or under a process supervisor (systemd, `tmux`, `screen`) so they survive a terminal close. There is no Dockerfile in this repository yet — this is a bare-process deployment, matching the project's own documented "local desktop / local server" readiness tier.

**Creating the first admin account** (interactive, password never accepted as a CLI argument):

```bash
python -m backend.admin_cli create-admin
python -m backend.admin_cli list-admins
```

Sign in at `http://localhost:5174/#Login`.

---

## 2. Configuring a local model

Brud AI runs a local GGUF model via `llama-cpp-python`. Without one configured, the runtime honestly reports **unavailable** everywhere (widget health banner, Pilot Operations page, diagnostics) rather than failing silently — this is expected, not a bug, until a model is configured.

1. Place a `.gguf` model file inside the configured model directory. By default this is `models/` under the repo root (`BRUD_ALLOWED_MODEL_DIR` in `.env`, default `models`) — **the backend refuses any model path outside this directory**, so don't try to point it at a file elsewhere on disk.
2. In the admin dashboard, open **Brud Mini Brain → Local Setup**. This tab shows real hardware probing (RAM/disk headroom), a real scan of `.gguf` files already inside the allowed directory, and a save form for `model_path`, `context_length`, `max_tokens`, `temperature`, and `threads`.
3. Save the configuration. The **Pilot Operations** page's "Runtime" section and the Admin Assistant widget's health banner will both immediately reflect the new `backend_type: "local"` / `loaded: true` state — both read from the same real runtime-resolution function (`MiniBrainLlmRuntimeService._resolve_backend()`; see `docs/audit/MB45_WIDGET_BACKEND_CONSOLIDATION_2026_08_11.md`), so they cannot disagree.
4. If no local model is configured, and an external provider key is configured and enabled under **Brud Mini Brain → Provider Settings**, the runtime falls back to that provider automatically — no separate switch to flip.

---

## 3. Creating a retrieval profile (for grounded chat)

Grounded chat needs a real, **active** retrieval profile backed by a real, indexed knowledge space. This is a real multi-step pipeline — there is no one-click shortcut, by design (each step is independently auditable):

1. **Knowledge & RAG → Knowledge Spaces**: create a space.
2. **Sources**: add a source (paste text, or another supported source type) inside that space, then approve it.
3. **Source Versions → Chunking**: create a version, then a chunk set from it, then validate the chunk set.
4. **Embedding Models → Embedding Runs**: register an embedding model (or reuse an existing one), create an embedding run against the chunk set, and execute it.
5. **Vector Indexes**: create a vector index from the embedding run, then build → validate → activate it.
6. **Keyword Indexes**: create a keyword index from the same chunk set, then build → validate → activate it.
7. **Retrieval Profiles**: create a profile in the space, then validate → activate it. Only an **active** profile can be used for retrieval or set as the grounded-chat default.
8. On the same **Retrieval Profiles** tab, use the **Retrieval Profile Management** table to **Set as default** — this is what the Admin Assistant widget's grounded-chat toggle actually uses (see §4).

**Shortcut for a pilot with an existing gateway-collected dataset:** if you already have an accepted **External AI Gateway** session, use the new **Gateway → Dataset/RAG** page instead — one form does source export + RAG ingestion + vector index build in a single real call. See its own in-page note about the one real constraint: check the "Also ingest into RAG" box *before* running the export — re-running export afterward to add RAG belatedly re-detects the same content as duplicates and silently skips RAG ingestion for it.

---

## 4. Testing grounded chat

1. Open the floating **Assistant** widget (bottom-right corner, any page).
2. Check **Use knowledge base**.
3. Ask a question whose answer is covered by your indexed content.
4. A response with a **Sources** list under it (source name, rank, score) confirms grounded mode retrieved real chunks. No sources listed means either no active default profile exists, or nothing in the indexed content scored above the profile's `minimum_score` threshold for that question.
5. To confirm the default-profile switch takes effect **immediately, without reloading the page**: change which profile is the default on the RAG page's Retrieval Profile Management table, then send another grounded message in the same still-open widget — the citation source should reflect the new default on the very next reply. This exact behavior is covered by a real, automated browser test: `apps/admin-dashboard/e2e/tests/10-grounded-chat.spec.js` (run via `npm run test:e2e` inside `apps/admin-dashboard`).

---

## 5. Day-to-day operational check

Open **Pilot Operations** in the sidebar (top level, next to System). One page, reused endpoints only, shows:

- Runtime backend, loaded model, runtime health (available/unavailable)
- Active grounded-chat default retrieval profile
- Knowledge space count, active retrieval profile count
- Last 20 audit events
- Database schema version

This is the first page to check when a pilot user reports "the assistant isn't responding" or "grounded answers stopped citing sources."

---

## 6. Support / escalation procedure

1. **Check Pilot Operations first** (§5) — most "it's broken" reports are explained by `runtime health: unavailable` (no model/provider configured — see §2) or `active retrieval profile: none set` (see §3 step 8).
2. **Check the backend log** (stdout of `make backend`) for the failing request's stack trace. Every admin mutation is CSRF-protected and audit-logged (`audit_logs` table, surfaced on Pilot Operations) — a rejected or failed action always leaves a trace.
3. **Reproduce via the API docs** at `http://127.0.0.1:8000/docs` if the dashboard's error message is unclear — every route is real FastAPI/OpenAPI, so the exact request/response shape is always inspectable there.
4. **If a specific known limitation is the cause**, check `docs/pilot/KNOWN_LIMITATIONS.md` before assuming it's a new bug.
5. **Escalate with**: the Pilot Operations screenshot, the relevant backend log lines, and the admin username/timestamp of the failing action (from the audit event). File it the same way other engineering issues in this repository are tracked; this pilot introduces no separate ticketing system.
6. **Never** work around a failure by disabling CSRF, editing the database directly, or bypassing the admin-mutation button-disable-while-pending behavior (see `docs/audit/MB48_INTERNAL_PILOT_HARDENING_REPORT.md` §5) — these exist specifically to keep the audit trail and data honest during a pilot with real daily users.

---

## Reference: ports and processes

| Process | Port | Command |
|---|---|---|
| Backend (FastAPI) | 8000 | `make backend` |
| Admin dashboard | 5174 | `make admin` |
| Public chatbot | 5173 | `make chatbot` (not part of pilot scope) |
