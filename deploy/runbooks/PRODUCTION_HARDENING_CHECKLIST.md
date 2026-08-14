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

## Ongoing / periodic

- [ ] TLS certificate expiry monitored (30-day-out alert at minimum)
- [ ] Re-run this checklist after any change to `deploy/env/*.env`, systemd units, or reverse-proxy config
- [ ] Re-run `deploy/benchmarks/smoke_soak_10m.sh` after any dependency or config change that touches startup behavior
- [ ] Periodically confirm `brud-backup-encryption.timer` is still active (`systemctl list-timers | grep brud-backup-encryption`) and its last run succeeded

## Still open (not this phase — see the Phase 6A audit report)

These were identified in the Phase 6A security review but are **out of
scope for Phase 6B-1/6B-2/6B-3** (deployment-hardening, backup-encryption
automation, and web-security-surface hardening only, no unrelated backend
logic changes). Do not consider a deployment fully hardened until these
are tracked as their own follow-up work:

- [ ] Frontend core dependencies (`react`, `react-dom`, `vite`, `@vitejs/plugin-react`) are pinned to `"latest"` in both `apps/admin-dashboard/package.json` and `apps/chatbot/package.json`
- [ ] No systemd sandboxing directives (`NoNewPrivileges`, `ProtectSystem`, etc.) on any of the units
- [ ] The global rate limiter (Phase 6B-3) is in-process/per-worker, matching this codebase's existing `public_chat_rate_limiter.py` pattern — if a future phase moves to multiple uvicorn workers or processes behind one deployment mode, each would keep its own independent counters (a shared store like Redis would be needed for a real shared limit)
