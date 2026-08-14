# Brud AI — Production Hardening Checklist

A reusable checklist, not a one-time procedure — run through this before
every production deployment and periodically afterward. For the
step-by-step *how*, see `PRODUCTION_HTTPS_RUNBOOK.md` in this same
directory. This checklist covers what Phase 6B-1 actually fixed
(deployment-layer hardening); it deliberately does not duplicate the full
Phase 6A audit report — see "Still open" at the bottom for what's
intentionally out of this phase's scope.

## Pre-deployment

- [ ] `deploy/env/{public,admin,worker}.env` exist (copied from `.example`, not committed)
- [ ] `admin.env` → `HOST=127.0.0.1`
- [ ] `worker.env` → `HOST=127.0.0.1`
- [ ] `public.env` → `HOST=0.0.0.0` (intentional — this is the only process meant to be reached directly by the reverse proxy)
- [ ] `admin.env` → `BRUD_ADMIN_COOKIE_SECURE=true`
- [ ] No real secrets accidentally left in any `.env.example` template (templates should only ever contain placeholder/non-secret values)
- [ ] `git check-ignore -v deploy/env/*.env` confirms all three real `.env` files are ignored, not tracked

## TLS / reverse proxy

- [ ] Public and admin are served on **different hostnames** (never the same domain, never a path-based split on one domain)
- [ ] TLS certificates are valid and auto-renewing (certbot timer for nginx, or confirmed automatic for Caddy)
- [ ] `curl -I https://<public-domain>/` and `https://<admin-domain>/` both complete a TLS handshake
- [ ] HTTP→HTTPS redirect confirmed on both vhosts (nginx template) or implicit via Caddy's default behavior
- [ ] Security response headers present on both vhosts: `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` — check with `curl -sI https://<domain>/` (set by the app itself since Phase 6B-3, not the proxy — see the App-layer security section below)

## Post-deployment verification

- [ ] `deploy/scripts/smoke-test.sh` passes against all three modes
- [ ] `deploy/benchmarks/restart_recovery_check.sh` passes
- [ ] From a machine **other than the VPS itself**: `curl` to `<vps-ip>:8001` and `<vps-ip>:8002` both **fail to connect** (not 401/403 — an actual connection failure, confirming the bind is genuinely local-only, not just proxy-gated)
- [ ] From the same external machine: the admin domain over HTTPS **does** return a real response (login page or 401), confirming the proxy path itself works
- [ ] Login through the real admin domain succeeds and the session cookie is confirmed `Secure` (check via browser devtools or `curl -v` cookie output) — this is the one item that can only be verified with TLS actually in front, so do it last

## Backup encryption (Phase 6B-2)

- [ ] `deploy/env/backup-encryption.env` exists, generated from `.example`, with a real key (`chmod 600`, not committed)
- [ ] `deploy/systemd/brud-backup-encryption.{service,timer}` installed via `deploy/scripts/install-systemd.sh`
- [ ] `systemctl enable --now brud-backup-encryption.timer`
- [ ] `systemctl start brud-backup-encryption.service` once manually to confirm a real run succeeds (`journalctl -u brud-backup-encryption.service`) before relying on the daily schedule
- [ ] Confirm plaintext backups are actually deleted after a verified encrypt (check `deploy/*/backups` — or wherever `BRUD_DATABASE_BACKUP_DIR` points — for `.enc`/`.enc.meta.json` pairs with no matching plaintext `brud_ai_before_v*_*.db`)

## App-layer security (Phase 6B-3)

- [ ] `curl -sI` against a direct-to-backend URL (bypassing the proxy, e.g. from the VPS itself to `127.0.0.1:8001`) still shows `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` — proves `SecurityHeadersMiddleware` protects this path too, not just the proxied one
- [ ] `admin.env`/`public.env` have `BRUD_TRUST_PROXY_HEADERS=true` and `BRUD_TRUSTED_PROXY_IPS=127.0.0.1`; `ps aux | grep uvicorn` shows `--proxy-headers --forwarded-allow-ips` in the running process args for those two services (`worker` intentionally has neither, it's never proxied)
- [ ] Send more than `BRUD_HTTP_RATE_LIMIT_MAX_REQUESTS` (default 120) requests to any non-exempt route within `BRUD_HTTP_RATE_LIMIT_WINDOW_SECONDS` (default 60s) and confirm a `429` — `/api/health`/`/api/version` are deliberately exempt so monitoring isn't affected
- [ ] nginx/Caddy templates no longer duplicate `add_header`/`header` security-header directives — confirm only one copy of each security header appears in `curl -sI` output through the proxy (a leftover custom proxy config with its own `add_header` block would double them up)

## systemd sandboxing (Phase 6C)

- [ ] After `deploy/scripts/install-systemd.sh` and a restart, `systemctl show brud-<mode> -p MemoryMax,TasksMax` reflects the unit's configured ceiling (1G/512 public, 512M/256 worker, 4G/512 admin) — confirms the units actually reloaded, not stale pre-6C copies
- [ ] `admin`/`public`/`worker` all pass `systemd-analyze verify deploy/systemd/brud-<mode>.service` with no warnings
- [ ] `public`/`worker` additionally have `PrivateDevices=true`, `MemoryDenyWriteExecute=true`, `SystemCallFilter=@system-service` (confirmed torch-free in Phase 5F-3); `admin` deliberately omits all three because it can load torch-backed local model inference on demand and this was never validated against real GPU hardware — see the comment block in `brud-admin.service` before ever adding them there
- [ ] `ReadWritePaths` on all three is exactly `data/` and `models/` under the repo root — if a future config change adds a writable directory outside those two (check `backend/core/config.py` for any new `Path = Field(default=Path(...))` that isn't under `data/`or `models/`), the unit files need a matching update or the service will fail to start (`ProtectSystem=strict` makes everything else read-only)
- [ ] If a deployment ever sets `BRUD_ALLOW_EXTERNAL_STORAGE=true` to point a data directory outside the repo, the matching systemd unit's `ReadWritePaths` must be extended to cover it, or that feature will fail under the sandbox
- [ ] After restarting a service, `journalctl -u brud-<mode> -n 50` shows a clean `Application startup complete` with no `Failed to set up mount namespacing` or `NAMESPACE`/`SECCOMP` exit codes — a mount or syscall-filter problem shows up immediately on start, not later under load

## Dependency governance (Phase 6D)

- [ ] `apps/admin-dashboard/package.json` and `apps/chatbot/package.json`'s `dependencies` blocks are all exact-pinned versions (no `latest`, `^`, `~`, `*`) — `deploy/scripts/verify-dependencies.sh`'s check 1 confirms this; `devDependencies` intentionally keep caret ranges, that's normal for dev/test tooling
- [ ] `requirements.txt` and `pyproject.toml`'s `[project.dependencies]`/`dev` extras agree exactly — a manifest drift here is how a package like `cryptography` (security-critical, used by backup encryption) can end up silently excluded from a `pip-audit -r requirements.txt` run; re-run the reconciliation check before ever hand-editing either file:
  ```bash
  python3 -c "
  import re, tomllib
  req = {re.match(r'^([A-Za-z0-9_.\-]+)', l.strip()).group(1).lower(): l.strip()
         for l in open('requirements.txt') if l.strip()}
  proj = tomllib.load(open('pyproject.toml', 'rb'))
  pdeps = {}
  for l in proj['project']['dependencies'] + proj['project']['optional-dependencies'].get('dev', []):
      pdeps[re.match(r'^([A-Za-z0-9_.\-]+)', l).group(1).lower()] = l
  print('only in requirements.txt:', sorted(set(req)-set(pdeps)))
  print('only in pyproject.toml:', sorted(set(pdeps)-set(req)))
  print('mismatches:', [(k, req[k], pdeps[k]) for k in set(req)&set(pdeps) if req[k]!=pdeps[k]])
  "
  ```
- [ ] `pip install -e .[audit]` (installs `pip-audit`) has been run in the venv before using either new script
- [ ] `deploy/scripts/verify-dependencies.sh` passes with exit 0 before a release — if it fails, read the printed findings (it never auto-fixes; `npm audit fix`/dependency upgrades are a deliberate, separately-reviewed decision, not something this script does for you)
- [ ] `deploy/scripts/generate-sbom.sh` has been re-run recently and `deploy/sbom/{backend,admin-dashboard,chatbot}.cdx.json` reflect the current manifests — these are generated artifacts (like `deploy/benchmarks/reports/`), not committed
- [ ] Known, currently-unresolved vulnerabilities (do not silently upgrade past a pinned range to fix these without separately testing — see "Still open"): frontend `nanoid` (high, transitive via vite toolchain) and `postcss` (moderate); backend `pillow`, `starlette`, `cryptography`, `pytest`, `diskcache` — run `deploy/scripts/verify-dependencies.sh` for the current, authoritative list rather than trusting this snapshot as it ages

## Ongoing / periodic

- [ ] TLS certificate expiry monitored (30-day-out alert at minimum)
- [ ] Re-run this checklist after any change to `deploy/env/*.env`, systemd units, or reverse-proxy config
- [ ] Re-run `deploy/benchmarks/smoke_soak_10m.sh` after any dependency or config change that touches startup behavior
- [ ] Periodically confirm `brud-backup-encryption.timer` is still active (`systemctl list-timers | grep brud-backup-encryption`) and its last run succeeded

## Still open (not this phase — see the Phase 6A audit report)

These were identified in the Phase 6A security review (or, for the
dependency findings, during Phase 6D's own audit tooling) but are **out
of scope for Phase 6B-1/6B-2/6B-3/6C/6D** (deployment-hardening,
backup-encryption automation, web-security-surface hardening, systemd
sandboxing, and dependency governance/pinning only -- upgrading a
pinned version to fix a CVE is a separate, deliberate decision this
phase didn't make). Do not consider a deployment fully hardened until
these are tracked as their own follow-up work:

- [ ] The global rate limiter (Phase 6B-3) is in-process/per-worker, matching this codebase's existing `public_chat_rate_limiter.py` pattern — if a future phase moves to multiple uvicorn workers or processes behind one deployment mode, each would keep its own independent counters (a shared store like Redis would be needed for a real shared limit)
- [ ] `admin`'s sandboxing is intentionally more conservative than `public`/`worker` (Phase 6C) because its torch/GPU code paths were never validated under `PrivateDevices`/`MemoryDenyWriteExecute`/`SystemCallFilter` on real GPU hardware — narrowing this gap is future work, not a current gap to "fix" casually
- [ ] `CPUQuota` is not set on any of the three units — no load-test data exists yet to size it without risking a visible slowdown under real traffic
- [ ] Known vulnerabilities found by Phase 6D's audit tooling remain unfixed on purpose (fixing means upgrading past a pinned range, needing its own testing pass): frontend `nanoid` (high) and `postcss` (moderate, both transitive via the vite toolchain, `npm audit fix` available); backend `pillow` (large number of CVEs, fix is a major version bump to 12.x), `starlette` (9 findings, fix is a FastAPI-compatible-range check first), `cryptography` (fix 50.0.0), `pytest` (fix 9.0.3), `diskcache` (no fix version published yet, transitive — trace which declared dependency pulls it in before deciding how to respond)
- [ ] `deploy/scripts/verify-dependencies.sh`'s pinning check only covers frontend `dependencies` — the backend has no equivalent "is every requirements.txt/pyproject.toml line an exact pin" check, because this codebase's existing convention is deliberately range-pinned (`>=X,<Y`) for the backend, not exact-pinned; that's a different governance model from the frontend's, not an oversight, but worth being explicit about if a future phase wants to unify them
