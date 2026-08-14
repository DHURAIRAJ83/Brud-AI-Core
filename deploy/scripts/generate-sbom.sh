#!/usr/bin/env bash
set -euo pipefail

# Generates a CycloneDX SBOM for the backend (Python) and both frontend
# apps (npm). Output is written to deploy/sbom/ and is a generated
# artifact -- like deploy/benchmarks/reports/, it is not committed.
#
# Backend: requires `pip install -e .[audit]` first (installs
# pip-audit, which also generates CycloneDX output -- no separate SBOM
# tool needed for Python).
# Frontend: uses `npx @cyclonedx/cyclonedx-npm`, fetched on demand, not
# added as a devDependency of either app.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

OUT_DIR="deploy/sbom"
mkdir -p "$OUT_DIR"

echo "=== backend (pip-audit -r requirements.txt --format cyclonedx-json) ==="
if ! source venv/bin/activate 2>/dev/null || ! command -v pip-audit >/dev/null 2>&1; then
  echo "pip-audit not installed -- run: pip install -e .[audit]" >&2
  exit 1
fi
# Audits requirements.txt's declared dependency tree, not the live dev
# venv -- the venv also has pip-audit itself and its own transitive
# deps (cyclonedx-python-lib, rich, ...) installed, which are audit
# tooling, not part of what actually ships.
#
# pip-audit exits non-zero when it finds known vulnerabilities (by
# design, for verify-dependencies.sh's use) -- that's not a generation
# failure here, so don't let `set -e` abort the rest of this script
# over it. A real failure (e.g. can't resolve requirements.txt at all)
# won't produce an output file, which the check below catches.
pip-audit -r requirements.txt --format cyclonedx-json --output "$OUT_DIR/backend.cdx.json" || true
if [ ! -s "$OUT_DIR/backend.cdx.json" ]; then
  echo "pip-audit did not produce $OUT_DIR/backend.cdx.json -- see output above" >&2
  exit 1
fi
echo "wrote $OUT_DIR/backend.cdx.json"

for app in admin-dashboard chatbot; do
  echo "=== $app (npx @cyclonedx/cyclonedx-npm) ==="
  (cd "apps/$app" && npx --yes @cyclonedx/cyclonedx-npm \
    --output-format json \
    --output-file "$ROOT/$OUT_DIR/$app.cdx.json")
  echo "wrote $OUT_DIR/$app.cdx.json"
done

echo
echo "SBOM generation complete: $OUT_DIR/{backend,admin-dashboard,chatbot}.cdx.json"
