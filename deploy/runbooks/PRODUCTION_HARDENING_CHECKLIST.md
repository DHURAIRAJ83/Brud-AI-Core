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
- [ ] Security response headers present on both vhosts: `Strict-Transport-Security`, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` — check with `curl -sI https://<domain>/`

## Post-deployment verification

- [ ] `deploy/scripts/smoke-test.sh` passes against all three modes
- [ ] `deploy/benchmarks/restart_recovery_check.sh` passes
- [ ] From a machine **other than the VPS itself**: `curl` to `<vps-ip>:8001` and `<vps-ip>:8002` both **fail to connect** (not 401/403 — an actual connection failure, confirming the bind is genuinely local-only, not just proxy-gated)
- [ ] From the same external machine: the admin domain over HTTPS **does** return a real response (login page or 401), confirming the proxy path itself works
- [ ] Login through the real admin domain succeeds and the session cookie is confirmed `Secure` (check via browser devtools or `curl -v` cookie output) — this is the one item that can only be verified with TLS actually in front, so do it last

## Ongoing / periodic

- [ ] TLS certificate expiry monitored (30-day-out alert at minimum)
- [ ] Re-run this checklist after any change to `deploy/env/*.env`, systemd units, or reverse-proxy config
- [ ] Re-run `deploy/benchmarks/smoke_soak_10m.sh` after any dependency or config change that touches startup behavior

## Still open (not this phase — see the Phase 6A audit report)

These were identified in the Phase 6A security review but are **out of
scope for Phase 6B-1** (deployment-hardening only, no backend logic
changes). Do not consider a deployment fully hardened until these are
tracked as their own follow-up work:

- [ ] Automatic backups are unencrypted by default — `encrypt_latest_backup` must currently be triggered manually after each backup
- [ ] No security-headers middleware exists at the application layer (this checklist's TLS section covers proxy-level headers only, which protects the proxied hostnames but not any direct-to-backend access path)
- [ ] No rate-limiting middleware exists anywhere in the application
- [ ] Frontend core dependencies (`react`, `react-dom`, `vite`, `@vitejs/plugin-react`) are pinned to `"latest"` in both `apps/admin-dashboard/package.json` and `apps/chatbot/package.json`
- [ ] `BRUD_TRUST_PROXY_HEADERS` exists in the env templates but is not yet consumed by `backend/main.py` — don't rely on the app correctly identifying real client IPs behind the proxy until this is wired up
- [ ] No systemd sandboxing directives (`NoNewPrivileges`, `ProtectSystem`, etc.) on any of the three units
