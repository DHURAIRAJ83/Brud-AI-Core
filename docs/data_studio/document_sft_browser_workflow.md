# Document SFT — Browser Workflow Evidence (Production Integration pass)

## What was and was not run this pass

No new Playwright scenarios were executed in this pass. This is a disclosed,
resource-driven scope decision, not an oversight:

- At the point this decision was made, `free -h` showed as little as ~420MB free RAM
  (1.7GB "available") with ~1.1GB already in swap, on a shared machine already
  running an active desktop Chromium session (15+ renderer processes) and the
  Claude Desktop Electron app outside this agent's control. Launching a third
  concurrent heavy process group (backend `uvicorn` + `vite` dev server + a new
  headless Playwright Chromium instance) risked destabilizing the host.
- The exact end-to-end path the task requires for browser verification --
  upload → extract → review → cleanup → Tamil quality → chunk → generate SFT →
  review candidates → export → **validate export → preview handoff → ingest →
  propose dataset version → preview split → confirm build → training_jobs
  unchanged** -- is instead exercised as a real, passing integration test at the
  HTTP layer: `tests/backend/test_document_sft_production_integration_api.py`,
  against the live FastAPI application (`api_app` fixture) and a real SQLite
  database via `httpx.AsyncClient`, not mocks. It includes the idempotent-retry
  (no duplicate dataset record on a second ingest call), the checksum-conflict
  path (a tampered stored checksum returns 409 and does not proceed), and a direct
  `SELECT COUNT(*) FROM training_jobs` assertion that the count is unchanged after
  a full build.
- The prior pass's committed Playwright suite (3 tests, single worker, covering
  upload through page review) remains valid for the surfaces it covers and was not
  re-run or modified this pass.

## What this means for the verdict

Per the task's own instruction ("If the complete post-fix manifest cannot finish
because of the environment, the final verdict must use `_WITH_LIMITATIONS`"), the
absence of a new browser run for this pass's additions is one of the reasons the
final verdict is `_COMPLETE_WITH_LIMITATIONS` rather than `_COMPLETE`. The backend
API integration test evidence above is real and passing, but it is not a substitute
for the browser-rendered UI (the new Dashboard tabs and Wizard steps) actually being
clicked through in a live browser.
