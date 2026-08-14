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

## Ongoing / periodic

- [ ] TLS certificate expiry monitored (30-day-out alert at minimum)
- [ ] Re-run this checklist after any change to `deploy/env/*.env`, systemd units, or reverse-proxy config
- [ ] Re-run `deploy/benchmarks/smoke_soak_10m.sh` after any dependency or config change that touches startup behavior
- [ ] Periodically confirm `brud-backup-encryption.timer` is still active (`systemctl list-timers | grep brud-backup-encryption`) and its last run succeeded

## Still open (not this phase — see the Phase 6A audit report)

These were identified in the Phase 6A security review but are **out of
scope for Phase 6B-1/6B-2/6B-3/6C** (deployment-hardening,
backup-encryption automation, web-security-surface hardening, and
systemd sandboxing only, no unrelated backend logic changes). Do not
consider a deployment fully hardened until these are tracked as their
own follow-up work:

- [ ] Frontend core dependencies (`react`, `react-dom`, `vite`, `@vitejs/plugin-react`) are pinned to `"latest"` in both `apps/admin-dashboard/package.json` and `apps/chatbot/package.json`
- [ ] The global rate limiter (Phase 6B-3) is in-process/per-worker, matching this codebase's existing `public_chat_rate_limiter.py` pattern — if a future phase moves to multiple uvicorn workers or processes behind one deployment mode, each would keep its own independent counters (a shared store like Redis would be needed for a real shared limit)
- [ ] `admin`'s sandboxing is intentionally more conservative than `public`/`worker` (Phase 6C) because its torch/GPU code paths were never validated under `PrivateDevices`/`MemoryDenyWriteExecute`/`SystemCallFilter` on real GPU hardware — narrowing this gap is future work, not a current gap to "fix" casually
- [ ] `CPUQuota` is not set on any of the three units — no load-test data exists yet to size it without risking a visible slowdown under real traffic
