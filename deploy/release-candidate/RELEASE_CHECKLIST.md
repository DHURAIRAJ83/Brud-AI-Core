# Brud AI — Release Checklist

Build: `phase-5-performance-polish` @ `6cd80d0`

All boxes intentionally left unchecked — this checklist records what a real deployment must still complete before going live; none of these have been executed against a real production environment as part of producing this release candidate package.

- [ ] TLS configured (real certificates installed, `nginx.conf`/`Caddyfile` deployed from the `.example` templates)
- [ ] Admin confirmed not publicly reachable (external connection test to `:8001`, not just config review)
- [ ] Backup encryption timer enabled (`systemctl enable --now brud-backup-encryption.timer`) and a real key generated into `deploy/env/backup-encryption.env`
- [ ] Restore drill completed (a real `verify_encrypted_restore()` run against production data, not just the isolated test fixtures used during development)
- [ ] SBOM generated against the actual release commit (`deploy/scripts/generate-sbom.sh`) and reviewed
- [ ] Dependency audit reviewed (`deploy/scripts/verify-dependencies.sh`) and open CVEs triaged for this release
- [ ] Benchmark reports archived (see `RC_MANIFEST.md` — currently incomplete: 7B-1/7B-1R/7C-1 have no repo-resident artifact)
- [ ] Monitoring configured (uptime/health checks, log aggregation, alerting on the systemd units)
- [ ] Rollback procedure tested (not just documented — an actual rollback rehearsal)
- [ ] Release tag created (this package only prepares a *local* tag — see `RC_MANIFEST.md`)
- [ ] Release notes prepared
