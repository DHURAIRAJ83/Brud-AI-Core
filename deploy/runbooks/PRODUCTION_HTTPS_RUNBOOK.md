# Brud AI — Production HTTPS Deployment Runbook

Covers taking the `public`/`admin`/`worker` systemd services (Phase 5E) live
behind TLS, using the hardened env templates (Phase 6B-1 Step 2) and the
reverse-proxy templates (Phase 6B-1 Steps 3B/3C). Written for a single-VPS
deployment; adapt paths/users as needed.

## Architecture

```
Internet ──HTTPS──▶ nginx/Caddy ──HTTP (127.0.0.1)──▶ brud-public.service  (:8000, 0.0.0.0)
                          │
      admin.<domain> ─────┴──HTTP (127.0.0.1)──▶ brud-admin.service   (:8001, 127.0.0.1)

brud-worker.service (:8002, 127.0.0.1) — never proxied; local-only, background jobs
```

Only the reverse proxy is ever directly internet-reachable. `admin` and
`worker` bind to `127.0.0.1` — they are unreachable from outside the
host even if the proxy is misconfigured or absent, which is a second,
independent layer of protection beyond TLS termination. The env
templates declared this binding since Phase 6B-1 Step 2, but
`deploy/scripts/start-{admin,worker}.sh` ignored `HOST`/`PORT` entirely
and hardcoded `0.0.0.0` until Phase 6B-3 fixed them to actually read it
— if you deployed between those two phases, re-run Step 2 below and
restart the affected services to pick up the fix.

## Prerequisites

- A VPS with this repository cloned and `venv/` set up (see main project README for env setup — out of scope here).
- Two DNS records pointed at the VPS: one for the public API domain, one for the admin domain (**must be different hostnames** — see Security checklist below for why).
- `nginx` or `caddy` installed on the host (this runbook doesn't install either — pick one and follow its own installation docs).
- Root/sudo access for `deploy/scripts/install-systemd.sh` and reverse-proxy installation.

## Step 1 — Configure environment files

```bash
cp deploy/env/public.env.example deploy/env/public.env
cp deploy/env/admin.env.example deploy/env/admin.env
cp deploy/env/worker.env.example deploy/env/worker.env
```

Edit each `.env` file (not `.example`) and set real values for anything
environment-specific (database path, origins, any provider API keys).
**Do not commit these files** — they're already covered by `.gitignore`'s
`.env` rule pattern; verify with `git check-ignore -v deploy/env/public.env`
before proceeding if unsure.

Confirm the hardened defaults are present (Phase 6B-1 Step 2):

```bash
grep -E '^HOST=|BRUD_ADMIN_COOKIE_SECURE|BRUD_TRUST_PROXY_HEADERS' deploy/env/*.env
```

Expected: `admin`/`worker` → `HOST=127.0.0.1`; `public` → `HOST=0.0.0.0`;
`BRUD_ADMIN_COOKIE_SECURE=true` in `admin` only.

## Step 2 — Install systemd units

```bash
deploy/scripts/install-systemd.sh
```

This copies `deploy/systemd/brud-*.service` into `/etc/systemd/system/` and
runs `systemctl daemon-reload`. All three units are sandboxed (Phase
6C: `ProtectSystem=strict` plus a `ReadWritePaths` carve-out for
`data/`/`models/`, `NoNewPrivileges`, capability dropping, and more --
see `PRODUCTION_HARDENING_CHECKLIST.md`'s systemd sandboxing section for
the full list and per-service differences). This doesn't change what
the app can do functionally, only what it can touch on disk and which
syscalls it can make -- if you've customized any data directory outside
`data/`/`models/` (e.g. via `BRUD_ALLOW_EXTERNAL_STORAGE=true`), extend
the matching unit's `ReadWritePaths` first or the service will fail at
startup. **Do not start the services yet** — the
reverse proxy needs to be in place first so `admin`'s cookies (which
require TLS to actually be useful with `Secure` set) aren't exercised
without it.

## Step 3 — Set up the reverse proxy

Choose one:

**nginx**: copy `deploy/reverse-proxy/nginx.conf.example` to nginx's
`sites-available/`, replace every `<PLACEHOLDER>` (domain names, cert
paths), symlink into `sites-enabled/`, then obtain certificates (e.g. via
`certbot --nginx`) for both domains before the first `nginx -t && systemctl
reload nginx`.

**Caddy**: copy `deploy/reverse-proxy/Caddyfile.example` to
`/etc/caddy/Caddyfile`, replace `<PUBLIC_DOMAIN>`/`<ADMIN_DOMAIN>`, then
`systemctl reload caddy` — Caddy provisions certificates automatically on
first request to each domain, no separate certbot step needed.

Either way, verify TLS is actually live before starting the backend
services:

```bash
curl -I https://<public-domain>/   # expect a TLS handshake to succeed even with a 502 (backend not up yet)
curl -I https://<admin-domain>/
```

## Step 4 — Start the services

```bash
sudo systemctl enable --now brud-public brud-admin brud-worker
systemctl status brud-public brud-admin brud-worker
```

## Step 5 — Verify

Smoke test through the proxy (real end-to-end path):

```bash
curl -fsS https://<public-domain>/api/health
curl -fsS https://<admin-domain>/api/health
```

Direct-to-backend smoke test (bypasses the proxy, confirms the app itself
is healthy — matches the existing tooling from Phase 5E/5G-A):

```bash
deploy/scripts/smoke-test.sh
deploy/benchmarks/restart_recovery_check.sh
```

Confirm `admin`/`worker` are **not** reachable from outside the host:

```bash
# from a different machine, both should fail to connect (not just 403/401):
curl -v http://<vps-ip>:8001/api/health
curl -v http://<vps-ip>:8002/api/health
```

## Security checklist (ties back to the Phase 6A audit findings)

- [ ] `admin`/`worker` bind to `127.0.0.1` (verified in Step 1)
- [ ] `BRUD_ADMIN_COOKIE_SECURE=true` is set (verified in Step 1) — **only effective because TLS is now in front**; setting this without real TLS just breaks cookie delivery entirely, it doesn't add protection
- [ ] Admin is served on a **separate domain/subdomain** from public, each with its own certificate — never the same hostname, so a public-facing link or redirect can never accidentally point at the admin login
- [ ] HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` are present on responses — set by the app itself (`backend/core/security_headers_middleware.py`, Phase 6B-3), not the proxy, so check with `curl -sI` against the real domain rather than reading the proxy config
- [ ] A global per-IP rate limit is active (`backend/core/rate_limit_middleware.py`, Phase 6B-3; tune via `BRUD_HTTP_RATE_LIMIT_MAX_REQUESTS`/`BRUD_HTTP_RATE_LIMIT_WINDOW_SECONDS`) — confirm it doesn't false-positive on normal dashboard usage before relying on it under load
- [ ] Consider enabling the commented-out IP-allowlist block in either template for the admin vhost, if the admin panel only needs to be reachable from known IPs/VPN
- [ ] `.env` files are not committed (`git check-ignore -v deploy/env/*.env`)
- [ ] `brud-backup-encryption.timer` is installed and enabled (`systemctl enable --now brud-backup-encryption.timer`) so plaintext backups are encrypted, verified, and the plaintext deleted automatically (Phase 6B-2) — without this, backups remain unencrypted by default as found in Phase 6A
- [ ] `deploy/env/backup-encryption.env` exists with a real generated key (`chmod 600`, not committed) — the timer's service unit will fail closed (and leave plaintext untouched) if this key is missing
- [ ] `BRUD_TRUST_PROXY_HEADERS=true` and `BRUD_TRUSTED_PROXY_IPS=127.0.0.1` are set in `admin.env`/`public.env` (Phase 6B-3) — `deploy/scripts/start-{admin,public}.sh` pass these to uvicorn as `--proxy-headers --forwarded-allow-ips`, so `X-Forwarded-For`/`-Proto` are only trusted when they come from the reverse proxy itself; verify with `ps aux | grep uvicorn` that the running process actually has `--proxy-headers` in its args, since a stale process from before this was wired up won't have it until restarted

## Rollback

- Reverse-proxy misconfiguration: `nginx -t` (or `caddy validate`) before every reload; keep the previous working config as `<name>.conf.bak` until the new one is confirmed live.
- Service misbehaving after start: `systemctl stop brud-<mode>`; the systemd units' `Restart=always` will not fight a manual stop.
- Full rollback to pre-hardening bindings: the previous `HOST=0.0.0.0` behavior for `admin`/`worker` can be restored by overriding `HOST` in the real `.env` file (not `.example`) — but this reintroduces the Phase 6A critical finding and should only be temporary, e.g. for local debugging without a proxy in front.
