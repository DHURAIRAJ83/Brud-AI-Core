# Phase 14 Report — Model Registry, Release Candidates, Artifact Governance, and Rollback

## 1. Baseline commit

`2c515bb` (`feat: add Brud AI phase 13 multilingual evaluation`), branch `master`. Working tree was clean before starting. Phase 13 verdict: `PHASE_13_COMPLETE_WITH_WARNINGS`. Schema version 13, 170 tests passing, public chatbot placeholder, current evaluated harness candidate `instruction_tuned=true / evaluation_required=true / not_public_chat_ready=true / evaluation result=evaluation_blocked` — all confirmed exactly as expected before implementation began.

## 2. Files created

```
backend/models/model_release.py
backend/database/repositories/model_release.py
backend/services/model_release_service.py
backend/api/routes/model_release.py
backend/model_release_cli.py
core_model/release/__init__.py
core_model/release/artifact_inventory.py
core_model/release/compatibility.py
core_model/release/eligibility.py
core_model/release/model_card.py
core_model/release/manifest.py
core_model/release/approval_policy.py
core_model/release/rollback.py
core_model/release/comparison.py
core_model/release/release_bundle.py
apps/admin-dashboard/src/pages/ModelRegistryPage.jsx
tests/database/test_phase14_migration.py
tests/backend/test_model_release_api.py
docs/database_schema_v14.md
docs/model_release_registry.md
docs/model_release_artifacts.md
docs/model_release_eligibility.md
docs/model_cards.md
docs/model_release_manifests.md
docs/model_release_approvals.md
docs/model_release_bundles.md
docs/model_release_rollback.md
docs/model_release_comparison.md
docs/phase_14_report.md
```

## 3. Files modified

```
backend/database/schema.py           (SCHEMA_VERSION 13→14, PHASE14_SCHEMA)
backend/database/migrations.py       (_apply_v14, backup-trigger version set)
backend/core/config.py               (17 new BRUD_RELEASE_* settings + 2 storage dirs)
backend/api/router.py                (model_release router included)
tests/backend/test_system_api.py     (applied_migrations set + migration 014)
apps/admin-dashboard/src/App.jsx (wired into the pre-existing "Model Registry"
  menu slot), services/api.js
docs/architecture.md, docs/development.md, docs/core_model_lifecycle.md,
docs/chat_readiness_assessment.md, docs/model_evaluation_reproducibility.md,
README.md
```

No file belonging to any unrelated project was read, copied from, or imported. All work stayed inside `/home/dhurai/Projects/brud-ai`.

## 4. Migration name and schema version

`014_phase14_model_release_registry`, schema version 13 → 14, applied by `_apply_v14` independently of migration 013 (own `schema_migrations` version guard, verified unchanged in isolation by `tests/database/test_phase14_migration.py::test_migration_013_is_unchanged_in_isolation`). Adds exactly 13 new tables: `model_release_families`, `model_release_candidates`, `model_release_artifacts`, `model_release_manifests`, `model_release_model_cards`, `model_release_eligibility_assessments`, `model_release_issues`, `model_release_approvals`, `model_releases`, `model_release_comparisons`, `model_release_rollback_plans`, `model_release_rollback_events`, `model_release_bundles`. No Phase 1–13 table was altered, dropped, or renamed.

## 5. Backup and checksums (real dev database upgrade)

```json
{
  "schema_version": 14,
  "backup": {
    "filename": "brud_ai_before_v14_20260724_121453_567031.db",
    "source_checksum": "8db016168f8f68c287a0b621d561fb5cc5b8b43ff2efc1d11c93599046c439ca",
    "backup_checksum": "81129bc4a30d17c5eaee49fbf00aeacfe9c93a943dfe7e5591f26a37a9ab1928"
  },
  "integrity_check": "ok"
}
```

`python -m backend.database.migrations status` now reports `current_version: 14, target_version: 14, migration_status: "current"`, with all 14 migrations (001–014) listed.

## 6. Release-family details

Manual verification created release family `phase14-manual-family` (slug `phase14-manual-family`), `lifecycle_status = "draft"` at creation (family lifecycle is a separate concept from candidate/release lifecycle, per the required separation of concerns). `current_release_public_id` started `null`, was set automatically to alpha.1 on first release creation, then to alpha.2 on the second release creation, then correctly reverted to alpha.1 after the rollback (see items 31–36).

## 7. Candidate A source and evaluation status

Candidate A was built exactly to the Phase-13-style pattern: a Phase-12-shaped promoted `core_model_versions` row (`architecture_summary_json = {"base_pretrained": true, "instruction_tuned": true, "evaluation_required": true, "not_public_chat_ready": true}`, `lifecycle_status = "staging"`), reusing the real base checkpoint's own `model_checksum_sha256` as its `weights_checksum_sha256` (never a new checkpoint file). Evaluation evidence was linked with `model_chat_readiness_assessments.status = "evaluation_blocked"`.

## 8. Candidate A artifact-verification result

**9 artifacts collected, all with `verification_status = "verified"`**: `model_checkpoint`, `model_config`, `tokenizer_model`, `tokenizer_vocab`, `tokenizer_manifest`, `dataset_manifest`, `base_training_manifest`, `evaluation_manifest`, `licence_notice`. Artifact collection and verification succeed even for a candidate that will ultimately be blocked — exactly the required separation between artifact integrity and release eligibility.

## 9. Candidate A eligibility

**`blocked`.**

## 10. Candidate A blocking issues

`['evaluation_blocked', 'instruction_manifest_missing', 'model_card_incomplete']` — `evaluation_blocked` because the linked readiness assessment is blocked; `instruction_manifest_missing` because this harness candidate's `instruction_tuned=true` flag has no corresponding real `instruction_tuning_candidates`/manifest lineage (an honest artifact of building the harness quickly, not a code defect — a genuinely Phase-12-trained instruction-tuned candidate would carry this manifest); `model_card_incomplete` because no model card was generated for this deliberately-blocked candidate. Any one of these alone would already block release; all three are non-overridable.

## 11. Candidate A approval attempt

**Correctly rejected**: `approval rejected: ['blocking_candidate_cannot_be_approved']`.

## 12. Candidate A release attempt

**Correctly rejected**: `candidate must be approved before creating a release`. Bundle creation was not attempted for Candidate A since no release exists to bundle — this is itself the intended structural block (a blocked candidate can never reach a state from which a bundle could be built).

## 13. Candidate B source and disclaimer

Candidate B is a **`registry_workflow_fixture` / `not_production_model`** — a genuinely registered, verified base-pretrained core model version (not instruction-tuned, avoiding the artificial manifest gap noted in item 10), built with a real SentencePiece tokenizer (vocabulary size 119) and a real checkpoint via `TrainingCheckpointManager`, with evaluation evidence linked at `model_chat_readiness_assessments.status = "evaluation_passed_with_limits"`. It is explicitly labeled and noted as a registry-mechanics test fixture, not a claim of a capable production model. Base model actual parameter count: **24,448** (directly instantiated and counted).

## 14. Candidate B artifact inventory

**9 of 9 artifacts verified**: `model_checkpoint`, `model_config`, `tokenizer_model`, `tokenizer_vocab`, `tokenizer_manifest`, `dataset_manifest`, `base_training_manifest`, `evaluation_manifest`, `licence_notice`.

## 15. Candidate B compatibility result

Tokenizer/model/config compatibility checks (`core_model.release.compatibility`) passed implicitly as part of a clean `eligible` eligibility result — no incompatibility issue was raised for vocabulary size, special-token IDs, or context length.

## 16. Candidate B eligibility

**`eligible`** (zero blocking reasons, zero warnings).

## 17. Candidate B warning issues

`[]` — no warnings were raised for this fixture.

## 18. Model-card checksum

`3b4284e280eced78...` (first 16 hex characters of the full SHA-256; the complete value is stored in `model_release_model_cards.card_checksum_sha256`). Validation result: `valid`, with `issues=[]`.

## 19. Model-card validation

**Valid.** All 24 required sections present and non-empty, no absolute paths or secret-shaped content, no unsupported capability claims, all three required honesty statements present verbatim, parameter count and checkpoint checksum matched the registered values, and the public-chat-assignment section correctly stated `"none (not assigned to the public chatbot)"`.

## 20. Release-manifest checksum

`b813fff873c1d3a4...` (first 16 hex characters). `verify_manifest()` recomputed the identical checksum.

## 21. Manifest verification

**`matches: true`.** The manifest was also scanned for sensitive content (`scan_for_sensitive_content()`) before being persisted; no absolute path or secret-shaped value was found.

## 22. Approval policy

Local-development default: `BRUD_RELEASE_REQUIRED_APPROVAL_ROLES=release` (a single `release`-role approval is sufficient), `BRUD_RELEASE_ALLOW_SELF_APPROVAL=true`. Blocking conditions remain non-overridable regardless of policy strictness — proven directly against Candidate A (item 11).

## 23. Approval evidence

Candidate B: one `release`-role approval, `decision = "approve"`, referencing the eligibility checksum current at submission time. Candidate B's second fixture (for the alpha.2 release) received an equivalent single `release`-role approval.

## 24. Release version

**`0.1.0-alpha.1`** (Candidate B's first release), and **`0.1.0-alpha.2`** (the second eligible fixture, for rollback verification) — both semantic-style versions, unique within the `phase14-manual-family` release family.

## 25. Release lifecycle status

alpha.1: `released` → (after rollback execution) remains `released` as the rollback *target*, now also the family's current release again. alpha.2: `released` → **`rolled_back`** after rollback execution (see item 35).

## 26. Deployment eligibility

alpha.1: **`deployable`** (candidate eligibility was `eligible`, not `eligible_with_warnings`).

## 27. Bundle inventory

Bundle for alpha.1 built successfully: `model/checkpoint/*` (all 9 real checkpoint files), `model/config.json`, `tokenizer/tokenizer.model`, `tokenizer/tokenizer.vocab`, `tokenizer/tokenizer_manifest.json`, `manifests/training_manifest.json`, `manifests/evaluation_manifest.json`, `manifests/release_manifest.json`, `model_card.md`, `LICENCE`, `README.md` — no `instruction_manifest.json` (candidate is not instruction-tuned, correctly omitted).

## 28. Bundle checksum

`e838e64e9dd25cf0...` (first 16 hex characters of the SHA-256 of the actual written zip archive), size **244,171 bytes**.

## 29. Bundle verification

**`matches: true`.** Confirmed the bundle contains no `.env` and no `.db` content (`'.env' not in inventory_text: True`, `'.db' not in inventory_text: True`).

## 30. Sensitive-file exclusion evidence

The bundle's file set is built entirely from the fixed `BUNDLE_REQUIRED_ENTRIES`/artifact-type mapping (`core_model/release/release_bundle.py`), never a directory walk — there is no code path by which the database file, `.env`, admin/session data, or a raw dataset could enter a bundle. `scan_bundle_paths_for_forbidden_content()` additionally checks every planned path against a forbidden-fragment list before any archive write. Verified directly in this run (item 29) and by automated test (`test_candidate_b_eligible_full_lifecycle`).

## 31. Release comparison

alpha.1 vs. alpha.2: **`compatibility: "compatible"`, `ranked: true`** — identical tokenizer version, model-config checksum, and evaluation-suite identity, since both releases originate from the same base model and the same evaluation suite.

## 32. Rollback source

**alpha.2** (`851bdeba-8740-45aa-b2f0-55e3259a3242`), the family's current release at the time the plan was created.

## 33. Rollback target

**alpha.1** (`f9a3d288-1917-4038-b035-241801b2da79`) — previously released, not archived, artifacts/manifest verified, deployment-eligible, not evaluation-blocked, no unresolved blocking issue. `assess_rollback_target()` reported `eligible: true`.

## 34. Rollback validation

Plan created already in `draft`; `validate_rollback_plan()` moved it to **`validated`** (the stored compatibility result was already eligible from creation time).

## 35. Rollback approval

`approve_rollback_plan()` moved the plan to **`approved`**.

## 36. Rollback execution result

`execute_rollback_plan()` moved the plan to **`executed`**. Source release alpha.2's status became **`rolled_back`**. Verified directly: the target release's checkpoint directory file listing was captured before and after execution and found **byte-for-byte identical** (`checksums.txt, config.json, manifest.json, model_state.pt, optimizer_state.pt, references.json, rng_state.pt, scheduler_state.pt, trainer_state.json` — same 9 files, same order, nothing added or removed) — proving the rollback touched only metadata.

## 37. Current-release pointer

Before rollback: `family.current_release_public_id = alpha.2's public ID`. After rollback: **`family.current_release_public_id = alpha.1's public ID`** — confirmed by direct re-read of the family row, matching the expected target release exactly.

## 38. Candidate/release lineage

Both Candidate B fixtures trace to the same `core_model_versions` row (base model, actual parameter count 24,448), the same real checkpoint (`TrainingCheckpointManager`-verified), and the same real tokenizer (SentencePiece, vocabulary size 119) — full lineage preserved end to end from candidate through both releases and the rollback plan.

## 39. Public chatbot status

Verified directly by test (`test_candidate_b_eligible_full_lifecycle`, `test_rollback_workflow`) and by direct in-process ASGI call against the real post-migration dev database: `POST /api/chat` returns `{"reply": "Brud AI chatbot foundation is working.", "detected_language": "unknown", "model": "placeholder", "phase": 9}` — unchanged. No model version was assigned to the `public_chat` assignment key in this phase or any earlier one.

## 40. API verification

All 36 `/api/admin/model-releases/...` routes were confirmed registered on the running FastAPI app (in-process route inspection — no live server/browser available in this environment, same `BUILD_VERIFIED_ONLY` convention as Phase 9–13) and exercised through in-process ASGI requests (`httpx.ASGITransport`) across 4 comprehensive test functions: candidate-A blocked-path rejection, candidate-B full eligible lifecycle (families→candidates→artifacts→model-card→eligibility→manifest→approval→release→bundle→verify), full rollback workflow (two releases, plan, validate, approve, execute, pointer/status checks), and rollback-target-ineligibility handling. Responses were checked to contain no absolute filesystem paths.

## 41. Admin Dashboard verification

`apps/admin-dashboard/src/pages/ModelRegistryPage.jsx` implements all 12 required sections as tabs (Overview, Release Families, Candidates, Artifact Inventory, Eligibility, Model Cards, Manifests, Approvals, Releases, Comparisons, Bundles, Rollback), wired into the pre-existing "Model Registry" sidebar slot, always showing the required registry-is-not-deployment disclaimer and the blocked-candidate warning. Verified by a clean `npm run build` and code review against the same API contract verified in item 40 — no live browser was available in this environment, so actual browser interaction was not performed; this limitation is reported explicitly, matching Phase 12/13 precedent.

## 42. Tests

`python -m pytest -q` (full suite, run after the real dev DB migration): **182 passed** — 170 pre-existing Phase 1–13 tests (unchanged in behavior) plus 12 new Phase 14 tests (8 migration tests in `tests/database/test_phase14_migration.py`, and 4 API/service tests in `tests/backend/test_model_release_api.py` covering candidate-A blocking, candidate-B's full eligible lifecycle, the two-release rollback workflow, and rollback-target-ineligibility handling).

## 43. Ruff and diff-check

`python -m ruff check .` → **All checks passed!** (checked with the temporary `data/manual_verification_phase14/verify.py` script excluded — that directory is deleted before commit, matching Phase 13's precedent). `git diff --check` → no whitespace errors.

## 44. Frontend builds

Both `apps/chatbot` (`npm run build`) and `apps/admin-dashboard` (`npm run build`) succeed with no errors, both before and after the `ModelRegistryPage.jsx` addition.

## 45. Database integrity and foreign-key result (real dev database, post-migration)

`PRAGMA integrity_check` → `ok`. `PRAGMA foreign_key_check` → no violations. `PRAGMA user_version` → `14`.

## 46. Git commit and status

This report is generated before the final commit described at the close of this document; the working tree is clean immediately before that commit (all Phase 14 files staged, nothing else — the `data/manual_verification_phase14/` scratch directory is deleted, not committed). No destructive git operation was used, and nothing was pushed.

## Known limitations

- **Candidate A's harness gap.** The Phase-13-style evaluation-blocked harness candidate also triggers `instruction_manifest_missing` and `model_card_incomplete` alongside the intended `evaluation_blocked` reason — an artifact of building the harness quickly for blocking-path verification (it flags `instruction_tuned=true` without a corresponding real instruction-tuning manifest, and no model card was generated for it), not a code defect. Any one of the three reasons alone already blocks release, so this does not change the demonstrated behavior.
- **Candidate B is explicitly a registry-mechanics fixture**, labeled `registry_workflow_fixture`/`not_production_model` throughout — it does not represent, and must never be read as, a claim about a genuinely capable production model. Its 24,448-parameter scale exists only to exercise the Phase 14 pipeline within the time available for manual verification.
- **Bug found and fixed during implementation** (see the corresponding docs for detail): the `validate_model_card()` pure function originally took a separate `fields` dict that the service layer passed as `{}`, silently failing every required-section check; fixed by having validation parse the rendered markdown directly (`docs/model_cards.md`). The `scan_for_sensitive_content()` absolute-path regex was anchored to the start of a line and missed paths embedded mid-string in single-line serialized JSON; fixed and re-verified against both a Unix and a Windows path (`docs/model_release_manifests.md`). `model_card`/`release_manifest` artifact types were not being recorded into the artifact inventory after generation, causing `build_bundle()` to correctly (but confusingly, until fixed) reject an otherwise-eligible release; fixed by recording both as verified artifacts at generation time (`docs/model_release_bundles.md`). All three were caught by direct smoke-testing and automated tests before this report was written, not discovered afterward.
- **No live browser available** in this execution environment — the Admin Dashboard page was verified by a clean build and API-contract review, not by clicking through it.

## Phase 15 readiness

Phase 14's infrastructure (families, candidates, artifacts, eligibility, model cards, manifests, approvals, releases, comparisons, bundles, rollback) is complete and independently tested. Before any future phase that depends on demonstrating a genuinely deployable release, a real, larger Phase 12 instruction-tuning run and Phase 13 evaluation pass (yielding a real `evaluation_passed_with_limits` or better candidate, not a registry-mechanics fixture) should be built. No blocking defect prevents future work from starting.

## Non-goals confirmed unchanged

No public chatbot model assignment, production model serving, container deployment, RAG, RLHF, DPO, reward modeling, quantization, GGUF export, external model providers, automatic deployment, or automatic rollback of running infrastructure were added in this phase. Rollback remains metadata-only; no file was deleted, no process was started or stopped, no environment variable was changed.

## Final verdict

**`PHASE_14_COMPLETE`**

Every completion criterion was met: schema version 14 with an independent, verified migration; release families, candidates, artifact inventories, and compatibility/eligibility enforcement all work; the evaluation-blocked harness candidate is structurally blocked from every step past artifact verification (approval and release both correctly rejected); model-card generation/validation and manifest generation/verification work, including catching a misleading-claim card and a tampered manifest; approvals are enforced, append-only, and become stale on evidence change; semantic-style versioning works and a fully eligible fixture released successfully; a safe bundle was built and verified with sensitive-file exclusion proven; release comparison correctly reported compatible/ranked; a full rollback (plan → validate → approve → execute) worked end to end with the current-release pointer updated and zero files touched; the public chatbot remained the unchanged placeholder throughout; all existing Phase 1–13 behavior remained intact (full suite green); ruff, diff-check, both frontend builds, and database integrity/FK checks all pass cleanly; and no serving, deployment, RAG, quantization, GGUF, RLHF, DPO, or external-provider capability was added. No blocking defect exists in the shipped code.
