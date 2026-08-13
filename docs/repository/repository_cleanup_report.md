# Repository Cleanup Report

Produced by the Completion, Stabilization & Zero-New-Feature Finalization
pass (2026-08-01). This is a refinement of `repository_cleanup_audit.md`
(prior Repository Stabilization pass) with everything re-verified still
current, plus one additional check. **Recommendations only — nothing was
deleted, moved, or auto-cleaned.**

## Re-verified still accurate

- `data/brud_ai.db` — still present, still 0 bytes, still unreferenced
  (real DB is `data/database/brud_ai.db`, gitignored). Recommend removal,
  not actioned.
- `.claude/launch.json` — still present, still local-only IDE config.
  Recommend adding `.claude/` to `.gitignore` if intended to stay
  local-only. Not actioned (would need user confirmation on intent, per
  the prior audit's note).
- `data/release_artifacts/` (144 files), `data/document_sft_exports/` (74),
  `data/manual_verification_phase20/` (18), `data/manual_verification_
  phase20_clean/` (19), `data/manual_verification_phase21a/` (64) — all
  still present, still not covered by `.gitignore`. Recommend adding
  `.gitignore` entries matching the existing pattern for sibling
  directories (`data/core_models/`, `data/corpus_exports/`, etc.). Not
  actioned.
- `docs/database_schema_v2.md`–`v19.md` (11 files) — recommend archiving
  under `docs/archive/`, not actioned (see `documentation_completion_
  report.md`).

## New check this pass: build/cache artifacts

- `__pycache__/` — already correctly gitignored (`.gitignore:4`); the many
  `backend/services/__pycache__/*.pyc` files observed during this pass's
  greps are correctly untracked and require no action.
- No stray `node_modules/`, `.pytest_cache/`, `dist/`, or `build/`
  directories were found inside tracked source trees during this pass's
  greps (all such directories, where present, matched existing `.gitignore`
  patterns).

## No new cleanup candidates found

This pass's additional review (backend TODO/FIXME scan, frontend page
review, Admin Assistant registry checks) did not surface any new unused
files, temporary files, duplicate scripts, or unused assets beyond what
`repository_cleanup_audit.md` already found. The Phase-1 placeholder
interfaces discussed in `backend_completion_report.md` (Finding 1) are
explicitly **not** recommended for cleanup here — they are historical,
test-covered, and not confusing live-path code, not cleanup debris.

## Summary of all outstanding recommendations (both passes combined)

1. Remove `data/brud_ai.db` (0-byte stray file).
2. Add `.gitignore` entries for `data/release_artifacts/`, `data/
   document_sft_exports/`, `data/manual_verification_phase20*/21a/`.
3. Decide `.claude/` directory's intended tracking status; ignore if
   local-only.
4. Archive `docs/database_schema_v2.md`–`v19.md` under `docs/archive/`.
5. (From `admin_assistant_completion_report.md`) Complete 5 missing
   `helpRegistry.js` entries when a dedicated content pass is scheduled.
6. (From `frontend_completion_report.md`) Author Playwright coverage for
   the ~25 dashboard pages with zero live test evidence, prioritized by
   the newest/most security-sensitive areas first.

None of the six items above were actioned in this pass.
