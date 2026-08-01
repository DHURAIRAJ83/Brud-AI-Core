# Phase 15A — Production Verification & Remediation: Plan

Written before any Phase 15A code, per Step 1. All baseline inspection below
was done by direct source reading (`Read`/`Bash`/`grep`) and direct
environment probing, not by spawning a research subagent, matching the
approach used for Phase 14 and Phase 15.

## 0. The two most important discoveries

**Real headless-browser automation is genuinely possible in this
environment.** Phase 14/15's "no browser automation tool was available"
referred specifically to *this agent's own* interactive browser-control
tool, not to Playwright-driven headless testing running inside the sandbox.
Direct probing found:

- `/usr/bin/chromium` (v150) already installed at the OS level.
- A naive headless launch (`chromium --headless=new --no-sandbox
  --disable-gpu`) hangs/times out — this container's `/dev/shm` is too
  small, a well-known Docker/sandbox constraint. Adding
  `--disable-dev-shm-usage` fixes it immediately (verified: renders
  `about:blank` and a `data:` URL page in well under a second).
- `@playwright/test@1.62.0` installs cleanly from the npm registry (no
  Playwright browser-binary download needed or attempted — the config
  points `executablePath` at the system Chromium instead, avoiding any
  dependency on Playwright's own CDN).
- A real smoke script (`chromium.launch({ executablePath:
  '/usr/bin/chromium', args: ['--no-sandbox', '--disable-dev-shm-usage',
  '--disable-gpu'] })`) navigated to a page and read its DOM successfully.

Consequence: Step 8-13's browser tests will be **real** Playwright browser
automation against a real running backend+frontend, not a simulated or
HTTP-only substitute. This directly closes Phase 15's first documented
limitation.

**No schema migration is required for Phase 15A.** Every new fact this
phase needs to persist already has a reuse-appropriate home in the existing
Phase 15 schema (migration 038, unchanged):

| New fact | Existing home | Why it fits |
|---|---|---|
| Canonical manifest version/checksum bound to a run | `production_regression_runs.batch_plan_json` | Already a free-form JSON blob set once at `create_run()` and never updated — embedding `{"manifest_version", "manifest_checksum", "batches": [...]}` as the `batch_plan` argument requires no column change |
| Per-batch category (incl. `browser_e2e`) | `production_regression_results.batch_name`/`command` | Both are free-text columns already; `batch_name` records `"<category>:<batch_id>"`, `command` records the real allowlisted command |
| Backup-encryption assessment, encrypted-backup creation, encrypted-restore verification | `production_readiness_events` (generic, `event_type` unconstrained TEXT) | This is the exact table Phase 15 already built for system-wide, non-per-entity checks (`api_abuse_readiness_assessed`, `secret_redaction_mechanism_verified`) — new `event_type` values (`backup_encryption_assessed`, `encrypted_backup_created`, `encrypted_restore_verified`) follow the identical pattern |
| Independent backup-artifact re-check (encryption-aware) | `production_artifact_security_checks` (`artifact_type='backup'` already exists in the CHECK list) | Extends `ProductionArtifactSecurityService.check_backup_artifact()`, does not duplicate it |
| Phase 15A readiness report | `production_readiness_reports` (new version row) | Already versioned/immutable/checksummed; the new version's `report_json` payload gains new top-level keys (`canonical_regression`, `browser_verification`, `backup_encryption`, `encrypted_restore`), no column change |
| Phase 15A acceptance | `production_acceptance_reviews` (new row against the new report) | Already binds `report_checksum`/`target_fingerprint`; Step 27's extra required fields (manifest checksum, run id, result checksums) are recorded inside `conditions_json`, which is already a free-form JSON column for exactly this kind of structured condition data |

This matches the non-negotiable rule directly: "Do not create a migration
solely to record static configuration that belongs in files or manifests."
**Schema version stays at 38.**

## 1. Existing systems inventory (reused, never duplicated)

| Concern | Existing owner | Reuse strategy |
|---|---|---|
| Regression run/batch mechanics | `ProductionRegressionService` (`create_run`, `execute_batch`, `finalize_run`) | Extended, not replaced: a new `run_manifest_batch()` method resolves a `batch_id` against the checked-in manifest and calls the existing `execute_batch()` internals with the manifest's own command — the admin never supplies a raw command |
| Regression run/result repository methods | `ProductionReadinessRepository` | Reused verbatim (`create_regression_run`, `add_regression_result`, `update_regression_run_status`, `list_regression_runs/results`) |
| Backup creation | `backend.database.migrations.create_verified_backup()` | Never modified; the new encryption service takes its `BackupResult.path` as input and produces a sibling `.db.enc` file |
| Backup/restore readiness | `ProductionBackupReadinessService`/`ProductionRestoreReadinessService` | Extended with an encryption-aware variant; the existing plaintext-restore-drill logic is unchanged |
| Artifact security | `ProductionArtifactSecurityService` | `check_backup_artifact()` extended to also report encryption status when an encrypted sibling exists |
| Deployment readiness | `ProductionDeploymentReadinessService` | Extended to additionally require the new checks (canonical regression, browser verification, backup encryption) before reporting `ready`, following the exact same "never_assessed is blocking" pattern already used for Steps 17-21 |
| Final report/acceptance | `ProductionReadinessReportService`/`ProductionAcceptanceReviewService` | Extended report payload; acceptance service unchanged in shape, new required fields carried in `conditions` |
| Admin Assistant pipeline | `AdminAssistantService`, `core_model.admin_assistant.action_registry` | New tools/actions registered the same way Phase 15's 8 actions were; `BLOCKED_ACTION_SUBSTRINGS` unchanged; no new action can approve/activate/rollback/delete-backups/change-keys |
| CSRF/session/auth | `backend/api/auth.py` (`require_admin`, `require_csrf`, double-submit-cookie CSRF) | Reused as-is by every new route; browser tests exercise it for real over HTTP, not mocked |
| Secret redaction | `backend.core.json_utils.redact_secrets`/`SECRET_KEYS` | Reused verbatim in every new audit call and in log/report redaction |
| Frontend hash routing | `App.jsx` (`window.location.hash`) | Investigated for the deep-link limitation (see §9) |

## 2. Canonical regression manifest design

`config/production_regression_manifest.json`, versioned
(`manifest_version: 1`) and self-checksummed (SHA-256 of the canonicalized
JSON with the checksum field itself excluded, recomputed and compared the
same way `production_readiness_reports.report_checksum_sha256` already
works). Batches map to **real, already-existing** commands in this
repository — nothing is invented:

- `database_migrations` → `pytest tests/database/test_phase22_migration.py -k migration` (and friends)
- `database_integrity` → a small inline script running `PRAGMA
  integrity_check`/`PRAGMA foreign_key_check` against the target DB
- `database_repositories` → `pytest tests/database/`
- `backend_services`/`backend_api` → targeted `pytest tests/backend/...`
  batches (kept small per batch, matching the "environment kills broad runs"
  constraint documented in Phase 14/15)
- `core_model` → `pytest tests/core_model/`
- `rag`, `training`, `model_registry`, `production_readiness`,
  `admin_assistant`, `security` → targeted existing test files already
  present under `tests/backend/`
- `frontend_unit` → `npm test` (vitest) in `apps/admin-dashboard`
- `frontend_build` → `npx vite build` in `apps/admin-dashboard`
- `browser_e2e` → `npx playwright test` in `apps/admin-dashboard`
- `static_analysis` → `ruff check .`
- `secret_scan` → the Phase 15 `ProductionSecretScanService` invoked as a
  script/pytest batch
- `forbidden_write_scan` → the new static-analysis guard tests from Phase
  15 (`test_production_readiness_security.py`) plus a Phase15A-specific
  guard (§8)

Enforcement: the regression service resolves `batch_id → command` **only**
from the loaded, checksum-verified manifest; there is no code path that
accepts a caller-supplied command or argument list. Manifest schema
validation happens before any batch is even listable.

## 3. Browser-test isolation strategy

A dedicated `apps/admin-dashboard/e2e/` suite, `playwright.config.js`
pinned to a single Chromium project using the system browser
(`executablePath` resolved from `PLAYWRIGHT_CHROMIUM_PATH` env var,
defaulting to `/usr/bin/chromium`, with `--no-sandbox
--disable-dev-shm-usage` — required in this container). Global setup:

1. Spawns the backend against a **temporary, isolated SQLite database**
   (a fresh `tmp` path, never `data/database/brud_ai.db`), same pattern
   `tests/backend/*_api.py` already use via `Settings(database_path=...)`.
2. Runs `initialize_database()` against it, then seeds a dedicated
   `e2e-admin` account and the fixture chain (accepted RAG report, accepted
   checkpoint, etc.) through the same real repository/service APIs the
   Python test suite already uses — never raw SQL inserts, except where the
   existing Python test fixtures themselves already use a raw insert for a
   thing with no service API (mirrored exactly, not invented fresh).
3. Starts the backend (`uvicorn`) and frontend (`vite preview` against a
   production build, closer to real deployment than `vite dev`) on fixed,
   free local ports.
4. Playwright tests run against these ports only.
5. Global teardown stops both servers and deletes the temp database
   directory.

The real development database and real active model/RAG assignments are
never opened by any browser test.

## 4. Backup encryption: what exists, what's added

**What exists today**: nothing. `create_verified_backup()` produces a
plain, unencrypted SQLite file copy. No `cryptography`/`pynacl`/similar
library is currently a project dependency. Honest baseline assessment
(Step 14) will report `not_encrypted` for the current state before any new
code runs — this is verified by direct inspection, not assumed.

**What's added**: `pyca/cryptography` (industry-standard, added as a new
`pyproject.toml` dependency — confirmed installable in this environment,
already has `cffi` present as a transitive dependency of something else).
AES-256-GCM (`cryptography.hazmat.primitives.ciphers.aead.AESGCM`) for
authenticated, single-shot encryption of the (small, single-digit-MB in
this project's development state) SQLite backup file — streaming/chunked
AEAD is unnecessary at this file size and would add complexity without a
real safety benefit; the implementation still reads/writes through bounded
chunks to avoid an unnecessary full-file duplicate in memory beyond what
`Path.read_bytes()` already implies for files of this size, and is
revisited if backup sizes grow materially.

**Key management**: the existing `pydantic_settings` `BRUD_*` env-var
convention *is* this project's existing secret-reference mechanism (already
used for the admin cookie name, database path, etc.). A new setting,
`backup_encryption_key_env_var` (default `BRUD_BACKUP_ENCRYPTION_KEY`),
stores only the *name* of the environment variable holding the key — never
the key itself — matching Step 16's "environment variable reference"
example exactly. The key is read from `os.environ` at
encrypt/decrypt time only, held in memory only as long as the AESGCM call
needs it, and never logged, never returned by any API, never written to the
database. If the referenced env var is unset, every encryption/decryption
call fails closed (`not_configured`/`blocked`), never falling back to a
plaintext backup silently.

**Resolution (Step 14, implemented):** a new, read-only
`ProductionBackupEncryptionAssessmentService.assess()`
(`backend/services/production_backup_restore_readiness_service.py`) checks,
against the real backup directory and real `os.environ`, whether the
latest backup has an encrypted sidecar (`encrypted_backup_paths()`) and
whether the configured key-reference env var
(`Settings.backup_encryption_key_env_var`, default
`BRUD_BACKUP_ENCRYPTION_KEY`) is actually set. Recorded via
`production_readiness_events` (`event_type="backup_encryption_assessed"`),
exposed at `POST /api/admin/production-readiness/backup-readiness/
assess-encryption`, and surfaced in the "Backup & Deployment" tab. Run
against this repository's real, still-unencrypted state before any
encryption code existed: confirmed honest `not_configured` (no backup
present) and `not_encrypted` (backup present, no sidecar) results, plus a
dedicated test asserting the raw key value never appears anywhere in the
returned result or the persisted event, even when a key is present in the
environment (`test_production_backup_restore_and_deployment_readiness.py`).

**Envelope**: a small JSON sidecar (`<backup>.db.enc.meta.json`) next to the
encrypted `<backup>.db.enc` file, containing `format_version`, `algorithm`,
`key_reference` (the env var *name*), `created_at`, `source_artifact_type`,
`source_checksum` (of the original plaintext backup, already computed by
`create_verified_backup()`), `encrypted_checksum`, and the AESGCM nonce
(safe to store alongside ciphertext — it is not secret). No key material
anywhere in this file.

**Resolution (Steps 15-16, implemented):**
`ProductionBackupEncryptionService` (same module as the Step 14 assessment)
adds `encrypt_latest_backup()` and `decrypt_backup()`. The key is loaded
once per call via `_load_encryption_key()`, which fails closed
(`ValidationError`, mapped to HTTP 422 by the existing global exception
handler) if the env var is unset, not valid base64, or does not decode to
exactly 32 bytes — there is no plaintext fallback path. Exposed at
`POST /api/admin/production-readiness/backup-readiness/encrypt` and
surfaced in the "Backup & Deployment" tab next to the existing backup/
restore checks. `decrypt_backup()` verifies both the ciphertext checksum
(catches corruption before even attempting AEAD decryption) and, after a
successful decrypt, the plaintext checksum against the sidecar's
`source_checksum` — a wrong key or tampered ciphertext raises
`InvalidTag`, translated to the same fail-closed `ValidationError`, never
a silent garbage decrypt. Covered by 7 backend tests (missing backup,
missing key, wrong-length key, a real encrypt producing a real sidecar
that flips the Step 14 assessment from `not_encrypted` to `encrypted`, an
exact-bytes decrypt round-trip, wrong-key rejection, and corrupted-
ciphertext rejection) plus a full API-level encrypt→assess flow test and a
dedicated test asserting the real key value never appears in the sidecar
file or anywhere in the returned/persisted result.

## 5. Encrypted restore verification strategy

Fully isolated: copies `<backup>.db.enc` + its sidecar into a
`tempfile.TemporaryDirectory()`, decrypts there, verifies the decrypted
checksum against `source_checksum`, opens the decrypted copy with its own
`sqlite3.connect()`, runs `PRAGMA integrity_check`/`PRAGMA
foreign_key_check`/`migration_status()`, and deletes the temp directory
(including the decrypted plaintext) in a `finally` block regardless of
outcome. The live database is never touched. Wrong-key and
corrupted-ciphertext cases are tested explicitly — AESGCM's authentication
tag makes both fail closed with a decryption error, never a silent garbage
decrypt.

**Resolution (Steps 17-18, implemented):**
`ProductionBackupEncryptionService.verify_encrypted_restore()` decrypts the
latest encrypted backup via the already-tested `decrypt_backup()`, writes
the plaintext only inside a fresh `tempfile.TemporaryDirectory()`, opens
that isolated copy with its own `sqlite3` connection, and runs the same
`PRAGMA integrity_check` + `migration_status()` checks the existing
plaintext restore drill already uses — then the `with` block deletes the
temp directory unconditionally. Exposed at `POST /api/admin/
production-readiness/backup-readiness/verify-encrypted-restore`. Reports
`not_configured` (no backup, or backup not yet encrypted), `blocked`
(decrypt failed — wrong key or corrupted ciphertext, verified by a real
bit-flip test), or `passed`/`failed` for a real decrypt-and-verify. 7
backend tests cover all of these plus two isolation guarantees: the live
database file's inode is unchanged after the drill (the drill only ever
opens a temp-directory copy) and no `brud_encrypted_restore_drill_*`
temporary directory survives the call, on success or failure.

**Resolution (Steps 19-21, implemented):** three narrow, read-only
extensions, none of which required inventing a new capability:

- `ProductionArtifactSecurityService.check_backup_artifact()` gained one
  informational field, `checks["encrypted_sidecar_present"]`, computed via
  the shared `encrypted_backup_paths()` helper — it never affects
  `result_status` on its own; encryption readiness stays the dedicated
  Step 14 assessment's job, not this independent artifact-security pass's.
- `ProductionSecretScanService.scan_backup_sidecar_files()` (new method,
  same class, same `_SECRET_VALUE_PATTERNS` already used for the frontend-
  bundle scan) scans every `*.enc.meta.json` sidecar on disk for a
  secret-shaped value, as a defense-in-depth check on top of the
  by-construction guarantee that the sidecar never holds key material —
  exposed at `POST /api/admin/production-readiness/secret-scan/
  backup-sidecar-files` and wired into the "API Abuse & Secrets" tab.
- "Backup age" needed no new code: `ProductionBackupReadinessService.
  check_backup_readiness()` already existed (Phase 15) and operates on
  the plaintext `.db` file, which `encrypt_latest_backup()` never
  moves or replaces (it only ever writes a sibling `.enc` file). A new
  regression test confirms the age/staleness result is byte-for-byte
  identical before and after encrypting the same backup.

10 new backend tests cover all three, plus the existing
`test_deployment_readiness_ready_when_all_checks_pass` continues to pass
unchanged, confirming the extension didn't regress the existing
all-checks-pass path.

## 6. Deployment-readiness extension

`ProductionDeploymentReadinessService.assess()` gains three more
"never-assessed blocks readiness" checks (canonical regression, browser
verification, backup encryption), following the exact pattern already used
for backup/restore/artifact-security/api-abuse/secret-scan in Phase 15 —
absence of evidence is never treated as a pass.

**Resolution (Steps 22-23, implemented):**
`ProductionDeploymentReadinessService.assess()` gains three more
never-assessed-blocks-readiness checks, following the identical pattern
already used for backup/restore/artifact-security/api-abuse/secret-scan:

- `canonical_regression`: reads the latest `canonical_regression_finalized`
  readiness event (recorded by `finalize_manifest_run()`, §2); accepts
  `passed` or `passed_with_environment_limitations`, blocks on anything
  else or on no event at all.
- `browser_verification`: a new repository method,
  `get_latest_regression_result_by_batch_prefix("browser_e2e:")`, finds
  the most recent `browser_e2e` category batch result across all
  regression runs and requires `status == "passed"` — kept as its own
  check (not folded into `canonical_regression`) so a genuine browser-test
  failure can never be silently absorbed into an "environment
  limitations" classification.
- `backup_encryption`: reads the latest `backup_encryption_assessed` event
  (§4/Step 14) and requires `encrypted` (or the reserved
  `encrypted_with_conditions` value for future conditional-pass states);
  `not_encrypted`/`not_configured` block readiness.

12 new/updated backend tests cover: the fully-satisfied "ready" path (now
requiring real evidence for all three), that the three checks alone are
independently load-bearing (blocking with every *other* check passing),
and that an honest `not_encrypted` assessment still blocks. The
pre-existing `test_compile_report_ready_for_production_when_everything_
passes` test (readiness-report compilation, which calls this service
internally) was updated the same way and continues to pass.

**Real bug found and fixed via this revalidation pass:** clicking "System
health snapshot" in the real running Admin dashboard always failed with
405 Method Not Allowed. Root cause: `GET /system-health` was the only GET
route in this entire router requiring `CsrfDependency` (every sibling GET
route relies solely on the router-wide `require_admin` dependency — CSRF
is reserved for mutating requests) — combined with the frontend's
`productionSystemHealth()` sending a POST (to attach the CSRF header,
since `request()` only attaches it for non-GET methods) to a route that
only accepts GET. Fixed on both sides: the route now depends on
`AdminDependency` (auth only, matching every sibling GET route) instead of
`CsrfDependency`, and the frontend now sends a plain GET. No API-level
(HTTP) test had ever existed for this endpoint — only a direct service-
level test — which is exactly why the bug went undetected until real
browser automation exercised the actual button; a new API test
(`test_system_health_endpoint_is_a_real_get_and_needs_no_csrf_header`)
and a new Playwright test (`02-production-readiness-ui.spec.js`, "Backup &
Deployment tab reports real, non-fabricated deployment readiness and
health") both cover it going forward.

## 7. Final report and acceptance

`ProductionReadinessReportService.compile_report()` gains new payload
sections (§0 table); recommendation derivation is extended (not replaced)
so `ready_for_text_nlp_production` additionally requires the canonical
regression run to be `completed` (not just *a* regression run — the
manifest-bound one), browser verification to have passed, and backup
encryption to be at least `encrypted_with_conditions`.
`ProductionAcceptanceReviewService` is unchanged in mechanism; Phase 15A
simply compiles a fresh report and requires a fresh acceptance review
against it, exactly as the "stale report is rejected" behavior already
guarantees structurally.

## 8. Forbidden-write / arbitrary-command static guards

New, narrow static-analysis tests (extending
`test_production_readiness_security.py`'s pattern, not duplicating it):
the manifest-loading code path must never call `subprocess.run` with a
command that did not originate from the loaded-and-checksummed manifest
object; verified by scanning `production_regression_service.py` for any
`subprocess.run(` call site and asserting its command argument traces back
to a manifest-derived variable, plus a runtime test that a request carrying
an unregistered `batch_id` or a manifest-checksum mismatch is rejected
before any subprocess is spawned.

## 9. Hash deep-link investigation

No prior Phase 14/15 documentation in this repository actually records a
specific "hash deep-link limitation" (checked both final docs — neither
mentions one). Direct code reading of `App.jsx` shows top-level page
selection *is* hash-encoded and survives a hard refresh correctly (the
hash is a plain URL fragment, never sent to or required from the server, so
SPA-fallback routing is not even a concern here). The one real,
verifiable gap: **per-page sub-tab state (e.g. which
`ProductionReadinessPage` tab is active) is not hash-encoded** — a hard
refresh while on, say, the "Model Release" tab returns to that page's
default "Overview" tab. This will be verified with a real Playwright test
first (§0 principle: verify technically, don't assume); if confirmed, it
is fixed narrowly (encode `tab` into the hash query alongside the page
name, e.g. `#Production Readiness?tab=Model+Release`) without touching the
top-level routing mechanism, with a regression test. If investigation finds
no reproducible issue at all, this section is corrected to say so honestly
before the final doc is written.

**Resolution (Step 13, implemented):** the gap was confirmed reproducible
with a real Playwright test before any fix was written. Fixed narrowly:
`ProductionReadinessPage.jsx` now encodes the active sub-tab into the hash
as `?tab=<name>` (via `tabFromHash()` on mount and a `history.replaceState`
effect on change); `App.jsx`'s initial-page parsing was updated to split
the hash on `?` so the query suffix doesn't leak into the top-level page
name. Top-level routing, `selectPage()`, and the sidebar click flow are
unchanged. Covered by 4 vitest unit tests
(`ProductionReadinessPage.test.jsx`, "sub-tab hash deep-linking") and 3
real browser tests (`e2e/tests/03-hash-deep-link.spec.js`) verifying: a
hard reload preserves both page and tab, a fresh page load of a bookmarked
deep-link URL lands on the right tab, and an unrecognized tab value falls
back to Overview honestly instead of crashing. The separate, narrower,
deliberately out-of-scope limitation (same-document hash-only `goto()`
without a reload does not update React state, since there is no
`hashchange` listener) remains and is documented in
`e2e/tests/02-production-readiness-ui.spec.js` and
`03-hash-deep-link.spec.js` as the reason those tests use a sidebar click
or a fresh `page` for real navigation instead.

## 9.5. Responsive layout and accessibility basics (Step 12, implemented)

`apps/admin-dashboard/e2e/tests/07-responsive-accessibility.spec.js` (9
tests, all passing) verifies real behavior against the already-existing
mobile CSS (`index.css`'s `@media (max-width: 800px)` rule, unchanged) and
existing markup (`Sidebar.jsx`, `Topbar.jsx`, `DashboardLayout.jsx`,
unchanged) — nothing was added to production code for this step, only
tests, since direct inspection found the mobile layout, off-canvas drawer,
overlay-to-close interaction, and landmark roles already correctly
implemented:

- At a 390×844 mobile viewport: the sidebar is off-canvas by default,
  opens via the "Open menu" button, closes both by choosing a page (which
  also navigates) and by tapping the backdrop overlay outside the drawer's
  250px width, and no page produces horizontal overflow (checked on
  Overview and on Production Readiness across its widest tabs).
- Landmark roles: exactly one `banner`, one `main`, and a named `Admin
  modules` navigation are present; exactly one `h1` exists at all times
  and always reflects the active top-level page.
- Every sidebar nav button (including grouped "Data" children) has a
  non-empty accessible name.
- Login fields are reachable via their `<label>`, not only placeholder
  text.
- The mobile-only "Open menu" button is correctly absent from the
  accessibility tree at desktop width (`display: none`, not a violation —
  a hidden, non-functional control should not be announced) and exposes a
  real `aria-label` once visible at mobile width.

## 9.6. Final canonical regression execution and finalization policy (Steps 24-25, implemented)

The full, real canonical regression manifest was executed end-to-end
against the real local development database
(`data/database/brud_ai.db`, schema version 38, the actual environment
this repository runs in) via `ProductionRegressionService.create_manifest_
run()` → `execute_registered_batch()` for all 48 batches → `finalize_
manifest_run()` -- no batch skipped, no command substituted, every
subprocess a real `pytest`/`vitest`/`vite build`/`playwright test`/`ruff`
invocation resolved only from the checksum-verified manifest.

**First real run (before this section's fixes): `fine_status=failed`.**
Two genuine, previously-undetected issues were found and fixed as a
direct result of actually running the full manifest for real, rather than
assuming it would pass:

1. **A real product bug**, `core_model_01` (`test_admin_assistant_
   registries.py::test_every_real_nav_key_is_registered`): the "Production
   Readiness" sidebar nav key (added back in Phase 15) was never
   registered in `core_model/admin_assistant/dashboard_registry.py`'s
   `DASHBOARD_PAGES` tuple, meaning the Admin Assistant's dashboard-page
   registry -- and therefore anything built on it -- had no entry for this
   page at all. Fixed by adding a real `PageEntry` (`page_id=
   "production_readiness"`, `mode="governance"`) built from the page's
   actual `TABS` constant and its real `NOTICE`/rollback-plan/backup-
   encryption behavior (English + Tamil), not invented content. Verified:
   `tests/core_model/` (623 tests) and the specific 8-file batch both pass.
2. **A manifest timing defect**, not a code defect: `backend_api_01/02/03`
   hit `environment_incomplete` (subprocess timeout) at their configured
   240s budget. Measured in isolation: 371s / 562s / 484s respectively --
   genuinely that slow (real DB/API round trips across 56-74 tests each),
   not a fluke. Manifest corrected: those three batches' `timeout_seconds`
   raised to 700 (comfortable margin above the worst measured time),
   `manifest_version` bumped to 2, `manifest_checksum_sha256` recomputed
   via the same `compute_manifest_checksum()` the service itself uses (so
   the checked-in file and the service's own verification never diverge).
   The two tests that hardcoded `manifest_version == 1` were updated to
   `== 2`.

**Second, final run (after both fixes): `fine_status=passed`.**
Run `f59ac9f2-b845-4c71-acf9-c57b898ebcbc`: all 48/48 batches `passed`
(zero `failed`, zero `environment_incomplete`), covering all 18 required
categories with `missing_required_batch_ids=[]`. Real per-batch pass
counts included, among others: 621 database/repository/migration tests,
~700 backend_services/backend_api tests, 630 core_model tests, 45 rag
tests, 65 training tests, 17 model_registry tests, 110 production_
readiness tests, 194 admin_assistant tests, 168 security tests, 16
frontend unit test files, a real `vite build`, and all 42 real Playwright
browser tests. This is the honest, reproducible, evidence-backed
`fine_status` the finalization policy (§2, `finalize_manifest_run()`)
was designed to produce -- computed from real required-category coverage,
never assumed.

## 9.7. Final readiness report and Admin acceptance (Steps 26-27, implemented)

`_derive_recommendation()` was rewritten to read directly off `Production
DeploymentReadinessService.assess()`'s own `checks` dict (specifically
`checks["canonical_regression"]`, which is sourced from the manifest-
bound `canonical_regression_finalized` event) rather than a separately
re-fetched "latest regression run of any kind" -- removing any ambiguity
about which regression run the recommendation is really backed by, per
the plan's own stated intent. `deployment_status == "ready"` +
`canonical_regression == "passed"` (no environment limitations) yields
`ready_for_text_nlp_production`; `deployment_status == "ready"` with
`canonical_regression == "passed_with_environment_limitations"` yields
the honest, conditional `ready_with_conditions` instead (covered by a new
test). No change to `ProductionAcceptanceReviewService` -- its existing
latest-report-only binding and real active-model/RAG fingerprinting
already satisfy Step 27 as-is.

**Executed for real, against the real local database** (never simulated):
every prerequisite check that had never yet been triggered against the
real environment was run for real -- `backup_readiness` (passed),
`restore_readiness` (an isolated drill against the real latest backup,
passed, `integrity_check=ok`), `artifact_security` (passed),
`api_abuse_readiness` (passed), `secret_scan` (passed), and backup
encryption: a real 32-byte AES-256-GCM key was generated for this session
only (held solely in an ephemeral `BRUD_BACKUP_ENCRYPTION_KEY` shell
export, never written to any file or committed), the real latest backup
(`brud_ai_before_v21_...db`) was encrypted for real (producing a real
`.enc` + `.enc.meta.json` sidecar, both already covered by
`.gitignore:16`), the encryption assessment then reported `encrypted`,
and the isolated encrypted-restore drill passed for real
(`integrity_check=ok`). A manual, targeted inspection of the persisted
`report_json`/`conditions_json`/`production_readiness_events.metadata_
json`/the sidecar file confirmed the real key value appears nowhere --
only the `BRUD_BACKUP_ENCRYPTION_KEY` env var *name*.

With every prerequisite genuinely satisfied, `ProductionReadinessReport
Service.compile_report()` was run for real: report `e41e2364-6da7-46a8-
ab60-c751fa278561` (version 1), `deployment_readiness.result_status=
"ready"` with all 9 checks (`api_abuse_readiness`, `artifact_security`,
`backup_encryption`, `backup_readiness`, `browser_verification`,
`canonical_regression`, `database_integrity`, `restore_readiness`,
`secret_scan`) `passed`/`encrypted`, and
**`recommendation = "ready_for_text_nlp_production"`**. A real final
Admin acceptance review was then recorded:
`ProductionAcceptanceReviewService.submit_review(report_id, "accepted",
<real reason citing run f59ac9f2-...>, admin_id=<real "admin" account>)`
-- review `943b2d01-c04e-4f57-8478-75e9267f1960`, bound to the report's
real checksum and a real active-model/RAG-state fingerprint, per the
existing (unchanged) immutable-binding mechanism.

## 9.8. Admin Assistant integration and deterministic help (Steps 28-29, implemented)

Five new, narrow, read-mostly actions registered the same way Phase 15's
8 actions already were (`core_model/admin_assistant/action_registry.py`
+ matching entries in `ACTION_EXECUTORS`/`STALE_CHECK_FINGERPRINTS`/
`PREVIEW_GENERATORS` in `backend/services/admin_assistant_service.py`):
`run_production_backup_readiness_check`, `run_production_restore_
readiness_check`, `assess_production_backup_encryption` (all `risk_level=
"low"`), and `encrypt_production_backup` (`risk_level="moderate"` --
it's the one genuinely mutating action, though additive/reversible: it
only ever writes a new sibling `.enc`/`.enc.meta.json` file, never
touches the original backup), and `verify_production_encrypted_restore`
(`low`, a fully isolated drill). `BLOCKED_ACTION_SUBSTRINGS` is
unchanged; none of the 5 new action_types contain
`approve`/`activate`/`canary`/`rollback`/`acceptance_review`/
`build_candidate`/`validate_candidate` -- verified by extending the
existing `_PHASE15_ACTION_TYPES` guard tuple and its
`test_no_phase15_admin_assistant_action_can_approve_or_activate_
production` test in `test_production_readiness_admin_assistant.py`,
plus a new end-to-end test running all 5 through the real
propose→review→execute pipeline (including a real encrypt that flips a
following `assess_production_backup_encryption` call from
`not_encrypted` to `encrypted`).

**Deterministic help:** the `DASHBOARD_PAGES` fix from §9.6 (adding the
previously-missing "Production Readiness" entry) is also the deterministic-
help fix for this step -- `core_model/admin_assistant/intent.py`'s
`_matching_page_id()` matches user messages against exactly this
registry, so "Production Readiness" mentions were unrecognized by the
assistant's help/navigation intent classification until that entry
existed. Covered by a new regression test,
`test_help_matches_production_readiness_page`
(`tests/core_model/test_admin_assistant_intent.py`). A dedicated
`production_readiness_help.py` deterministic-Q&A module (mirroring
`rag_sandbox_help.py`/`dataset_verification_help.py`/`sample_import_
help.py`) was considered and deliberately not built: Phase 15 itself
never built one for this page, building a large new one now would be a
net-new feature area beyond "narrowly extending" existing systems for
backup-encryption/regression specifically, and the two mechanisms above
(the now-correct dashboard registry entry, plus each new action's real
bilingual `summary`/`confirmation_text`) already give the assistant real,
deterministic, non-fabricated things to say about every Phase 15A
capability.

## 9.9. Frontend updates and overview integration (Steps 30-31, implemented)

Frontend updates for every new Phase 15A backend capability were already
wired into the Production Readiness page's own tabs as each capability
was built (§9.1-§9.4): backup-encryption assessment/encrypt/verify-
restore buttons in "Backup & Deployment", the backup-sidecar secret scan
in "API Abuse & Secrets", the rollback-plan-steps fix, and the sub-tab
hash deep-link fix -- all covered by both vitest and real Playwright
tests already described above.

**"Data Overview" integration was deliberately not touched.**
`DataOverviewPage.jsx` states its own scope explicitly in its rendered
subtitle -- "A read-only snapshot of every data-related area" -- and
Production Readiness governs RAG/model *release*, not a data-pipeline
stage; every one of its existing quick-links (Datasets, Documents, Corpus
Builder, RAG Sandbox, Pretraining Readiness, etc.) is a real data-track
page. Adding a Production Readiness link there would contradict the
page's own stated scope, not fulfill it.

The real, in-scope overview integration gap: `ProductionReadinessRepository.
overview_counts()` (which backs the Production Readiness page's own
"Overview" tab -- the actual system-wide summary view for this whole
feature area) had no signal at all for backup encryption. Added
`backups_not_encrypted` -- 0 if never assessed (that absence is already
surfaced, blocking, by deployment readiness, so this counter would only
be redundant noise) or if the latest assessment says `encrypted`; 1 only
if an assessment has genuinely run and currently reports otherwise.
Surfaced as a new `StatusCard` next to the existing "Backups out of date"
card. 3 new backend tests (never-assessed → 0, assessed-and-not-encrypted
→ 1, assessed-and-encrypted → 0) plus an extended frontend test.

## 9.10. Resource/concurrency controls and security tests (Steps 32-33, implemented)

**Concurrency control**: `production_backup_restore_readiness_service.py`
gained `_backup_encryption_lock()`, one process-local `threading.Lock` per
backup directory -- the identical pattern already used for canonical
regression batch execution (`production_regression_service._run_lock`).
`encrypt_latest_backup()` holds it for its full read-encrypt-write
sequence (non-blocking acquire; a concurrent call gets a real
`ValidationError`, never silently interleaves writes to the shared
`.enc`/`.enc.meta.json` pair). `verify_encrypted_restore()` also acquires
it around its decrypt-read, so it can never read a `.enc` file
mid-write by a concurrent encrypt. A real test using a genuine
background thread (not a mocked lock) confirms the second call is
rejected while the first is still running.

**Security tests**: three new guards in `test_production_readiness_
security.py`, extending its existing static-analysis-guard pattern
(reusing the file's own `_PRODUCTION_SERVICE_FILES`/`_SERVICE_DIR`
globals, so the file's pre-existing `test_no_production_service_
directly_mutates_activation_state` and `test_no_production_service_
imports_a_new_network_library` already covered the new backup-encryption
service automatically, with no changes needed):

- `test_backup_encryption_key_value_is_only_read_by_one_function`: an
  `ast`-based scan (not a fragile string-split) confirming `os.environ`
  is referenced only inside `_load_encryption_key()` (reads the key
  *value*, fully validated, fail-closed) and `ProductionBackupEncryption
  AssessmentService.assess()` (reads only a `bool` presence flag) --
  nowhere else in the file.
- `test_new_backup_encryption_mutating_routes_require_csrf`: confirms
  all 4 new routes (`secret-scan/backup-sidecar-files`, `backup-
  readiness/assess-encryption`, `backup-readiness/encrypt`, `backup-
  readiness/verify-encrypted-restore`) are real `POST` routes and require
  `CsrfDependency` -- the direct counterpart to the real `/system-health`
  bug found and fixed in §9.4 (a GET route that wrongly required CSRF);
  this guards the opposite, equally real failure mode (a POST route that
  wrongly *doesn't*).

## 10. Pass/fail criteria for this plan

Phase 15A code may begin once this document is committed to disk. Each of
the 18 tracked tasks closes only when its own real tests pass — the
established, proven-effective pattern from the entire Phase 14/15 arc of
this session (write real code → run real targeted tests → fix real bugs
found → move on), never a broad, single mega-test-run given this
environment's documented intolerance for those.
