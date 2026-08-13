# Brud AI — Admin Onboarding Checklist

A new admin's first-session checklist for an internal pilot. Each item links to the fuller explanation in `docs/pilot/INTERNAL_PILOT_RUNBOOK.md`. Check items off in order — later steps assume earlier ones are done.

## Day 1 — access and orientation

- [ ] Backend (`make backend`) and admin dashboard (`make admin`) are both running and reachable (runbook §1).
- [ ] You have a real admin account (`python -m backend.admin_cli create-admin`) and can sign in at `http://localhost:5174/#Login`.
- [ ] You've opened **Pilot Operations** in the sidebar once, just to see the page exists and loads (runbook §5). Don't worry yet if runtime health shows "unavailable" — that's covered next.
- [ ] You've skimmed `docs/pilot/KNOWN_LIMITATIONS.md` once, so nothing on that list surprises you mid-pilot.

## Day 1 — get the runtime answering

- [ ] A local `.gguf` model is placed inside the allowed model directory (default `models/`), **or** a real external provider key is configured and enabled under Provider Settings (runbook §2).
- [ ] Local Setup (or Provider Settings) shows the model/provider as configured.
- [ ] Pilot Operations' "Runtime backend" and "Runtime health" tiles show a real backend name and "available" — not "unavailable". If they still say unavailable, re-check the model path is genuinely inside the allowed directory (a path outside it is silently rejected, by design).

## Day 1 or 2 — get grounded chat answering

- [ ] At least one knowledge space exists with at least one approved source, indexed and active (runbook §3, or use the Gateway → Dataset/RAG shortcut if you already have gateway-collected content).
- [ ] At least one retrieval profile is validated, activated, and set as the grounded-chat default on the RAG page's Retrieval Profile Management table.
- [ ] Pilot Operations' "Active retrieval profile" tile shows a real profile name, not "none set".
- [ ] You've opened the floating Assistant widget, checked "Use knowledge base", asked a question your indexed content actually answers, and seen a real **Sources** list under the reply (runbook §4).
- [ ] You've verified the default-profile-switch behavior once: change the default on the RAG page, send another grounded message in the same still-open widget, and confirm the citation source changes without reloading the page.

## Before inviting pilot users

- [ ] You know where the audit trail lives (Pilot Operations' "Recent audit events", or `GET /api/admin/audit/recent` directly) and have looked at a few real entries.
- [ ] You've read the support/escalation procedure (runbook §6) and know what to check first when a user reports a problem.
- [ ] You understand the one real "run export, then add RAG later" gotcha on the Gateway → Dataset/RAG page (runbook §3) if you plan to use it.
- [ ] You've confirmed `/api/admin/assistant/*` (the separate Phase-8 assistant system) and the MB-45 widget health fix are both untouched — if you're picking up this repo mid-development, this is the fastest way to confirm you haven't regressed either (`docs/audit/MB45_WIDGET_BACKEND_CONSOLIDATION_2026_08_11.md`).

## Ongoing (weekly, or after any code change)

- [ ] Full verification suite still green: `npm run build`, `npx vitest run`, `npx playwright test`, `pytest tests/backend -q`, `ruff check --select F401,F841 backend/ core_model/` (all from `docs/audit/MB48_INTERNAL_PILOT_HARDENING_REPORT.md`'s own verification checklist).
- [ ] Pilot Operations still shows a sane state (runtime available, a default profile set, recent audit events look like real pilot activity, not errors).
