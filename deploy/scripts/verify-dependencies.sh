#!/usr/bin/env bash
set -uo pipefail

# Repeatable supply-chain verification, meant to be run before a
# release and periodically otherwise (see
# deploy/runbooks/PRODUCTION_HARDENING_CHECKLIST.md's dependency
# governance section). Runs every check and prints a full summary
# rather than stopping at the first failure, then exits non-zero if
# anything failed.
#
# npm audit and pip-audit both need network access to query their
# advisory databases -- this script is not meant to run in an
# air-gapped environment.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

FAILED=0

echo "=== 1. Frontend production dependencies are exactly pinned ==="
# Scoped to "dependencies" only (production, shipped code) -- not
# "devDependencies", where this repo's existing caret-range convention
# for dev/test tooling (playwright, vitest, testing-library, ...) is
# normal practice and out of scope for this check.
for app in admin-dashboard chatbot; do
  unpinned=$(node -e "
    const deps = require('./apps/$app/package.json').dependencies || {};
    const bad = Object.entries(deps).filter(([, v]) => !/^\d+\.\d+\.\d+/.test(v));
    bad.forEach(([name, v]) => console.log(name + '@' + v));
  ")
  if [ -n "$unpinned" ]; then
    echo "FAIL ($app): unpinned production dependencies found:"
    echo "$unpinned" | sed 's/^/  /'
    FAILED=1
  else
    echo "OK ($app): all production dependencies exactly pinned"
  fi
done
echo

echo "=== 2. npm audit (production dependencies) ==="
for app in admin-dashboard chatbot; do
  echo "--- $app ---"
  if (cd "apps/$app" && npm audit --omit=dev); then
    echo "OK ($app): no known vulnerabilities in production dependencies"
  else
    echo "FAIL ($app): npm audit found known vulnerabilities (see above) -- do not silently 'npm audit fix' without reviewing what it upgrades"
    FAILED=1
  fi
done
echo

echo "=== 3. pip-audit (backend, requirements.txt) ==="
if ! source venv/bin/activate 2>/dev/null || ! command -v pip-audit >/dev/null 2>&1; then
  echo "SKIP: pip-audit not installed -- run: pip install -e .[audit]"
else
  if pip-audit -r requirements.txt; then
    echo "OK: no known vulnerabilities in backend dependencies"
  else
    echo "FAIL: pip-audit found known vulnerabilities (see above) -- review each fix_versions entry before upgrading, some may cross a pinned range boundary in pyproject.toml/requirements.txt"
    FAILED=1
  fi
fi
echo

if [ "$FAILED" -eq 0 ]; then
  echo "=== All dependency verification checks passed ==="
else
  echo "=== One or more dependency verification checks FAILED -- see above ===" >&2
fi
exit "$FAILED"
