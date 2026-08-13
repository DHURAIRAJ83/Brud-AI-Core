# Documentation Index

Produced by the Repository Stabilization pass (2026-08-01). Maps every
document under `docs/` (243 `.md` files) to its purpose. No document was
rewritten, merged, or deleted — this is a map, not an edit.

## Critical finding: three overlapping phase-numbering systems

The repository uses the word "Phase N" for **three independent, unrelated
sequences that reuse the same integers**. This is not a defect in any one
document — each track is internally consistent and correctly labelled with
its own scope — but reading "Phase 20" without knowing which track is being
discussed is genuinely ambiguous:

| Track | Where | Phase 20 means | Status |
|---|---|---|---|
| **Main Brud AI** (core model/training pipeline) | `docs/phase_N_report.md` (1–19), `README.md` (20 onward) | Clean corpus release verification | Committed (`31a7152`) |
| **Data Studio** (admin dashboard data workflows) | `docs/data_studio/phaseN_*.md` (1–7) | *(track ends at 7; no Phase 20)* | Uncommitted |
| **Smart Routing** (public chat answer routing) | `docs/smart_routing/phaseN_*.md` (16–26) | Trusted Web & Tool/MCP Gateway | Uncommitted (see finding in `repository_cleanup_audit.md` — already implemented, not just planned) |

**Recommendation** (not actioned): when any of this uncommitted work is
eventually committed, prefix future phase references with the track name
("Smart Routing Phase 20") in commit messages and new docs to avoid
collision with the Main Brud AI track's own Phase 20. Do not rename existing
files — that would rewrite history this task must preserve.

## Main Brud AI track — `docs/phase_1..19_report.md` + `docs/phase_9r_final_repair_report.md`

20 files. One report per phase of the core model/training pipeline
(foundation → data → training → RAG → conversation memory → feedback →
Tamil corpus). All committed. Status: authoritative, no action.

## Root-level `docs/*.md` (150 files, all committed)

Stable reference documentation for the already-shipped pipeline, organized
by subsystem prefix — not phase-numbered, evergreen:

| Prefix | Files | Subsystem |
|---|---|---|
| `tokenizer_*`, `dataset_*`, `document_processing.md`, `document_segmentation.md`, `ocr_processing.md`, `pdf_security.md` | ~15 | Corpus/tokenizer pipeline (Phases 2–7) |
| `core_model_*`, `pretraining_*` | ~13 | Base model architecture + pretraining (Phases 8–9) |
| `base_training_*`, `instruction_*`, `evaluation_leakage_repetition.md`, `factual_support_evaluation.md`, `human_evaluation.md`, `multilingual_evaluation.md` | ~17 | Training + evaluation (Phases 10–13) |
| `model_release_*`, `model_evaluation_*`, `model_cards.md`, `model_assignment_*`, `inference_*` | ~19 | Release registry + inference runtime (Phases 14–15) |
| `rag_*` | ~14 | RAG pipeline (Phase 16) |
| `conversation_*`, `memory_*`, `context_orchestration.md`, `chat_*`, `admin_chat_lab.md`, `admin_diagnostic_inference.md` | ~14 | Conversation memory + admin chat (Phase 17) |
| `feedback_*` | ~13 | Feedback/improvement pipeline (Phase 18) |
| `database_schema_v2..19.md`, `database_backup_and_recovery.md` | 11 | Schema evolution reference (superseded per-version snapshots — see recommendation below) |
| `admin_assistant.md`, `admin_authentication.md`, `architecture.md`, `development.md`, `checkpoint_retention.md`, `current_state_audit_before_phase10.md`, `text_normalization.md`, `safety_refusal_evaluation.md`, `conversation_injection_guard.md`, `chat_readiness_assessment.md` | ~10 | Cross-cutting / miscellaneous | 

**Recommendation** (not actioned): `database_schema_v2.md` through
`database_schema_v19.md` (11 files) are point-in-time schema snapshots for
versions that have all since been superseded (current schema is 44). They
are historically useful but should be clearly marked as archival, or moved
to a `docs/archive/` subdirectory, so a reader doesn't mistake `v19` for the
current schema. Not moved in this pass — recommendation only.

## `docs/data_studio/` — 30 files (28 uncommitted, see finding)

Two sub-sequences:

**Phase 1–7 (Data Studio track, uncommitted)**: `phase1_existing_data_
system_audit.md`, `phase1_unified_data_navigation.md`,
`phase2_source_rights_registry.md` (+ `_plan.md`),
`phase3_manual_data_studio.md` (+ `_plan.md`),
`phase4_pdf_research_workspace.md` (+ `_plan.md`),
`phase5_semantic_chunk_structured_record_studio.md` (+ `_plan.md`),
`phase6_quality_duplicate_conflict_approval.md` (+ `_plan.md`),
`phase7_dataset_rag_training_integration.md` (+ `_plan.md`). Each numbered
phase has a completion report and a plan document — a genuine audit→plan→
completion pair per phase, not a duplicate.

**Document SFT sub-sequence (not numbered, 4 passes, uncommitted except the
final 2)**:
1. `document_sft_workflow_audit.md` → `document_sft_workflow_completion_plan.md` (Workflow pass)
2. `document_sft_production_integration_audit.md` → `document_sft_production_integration_plan.md` → `document_sft_production_readiness.md` (Production Integration pass)
3. `document_sft_finalization_audit.md` → `document_sft_finalization_plan.md` (Finalization pass — navigation/deep-link/Admin Assistant integration)
4. `document_sft_closure_audit.md` → `document_sft_closure_plan.md` → **`document_sft_full_browser_verification.md`** → **`document_sft_final_production_readiness.md`** (Production Closure pass — the last two are already committed in `26611fc`)

Plus reference docs from the Finalization/Closure passes:
`document_sft_admin_api.md`, `document_sft_admin_assistant_navigation.md`,
`document_sft_admin_dashboard.md`, `document_sft_browser_workflow.md`,
`document_sft_deep_link_contract.md`.

Each numbered pass's own report explicitly states its own scope and does
not claim completion beyond it — verified while writing this index, no
contradictory "done" claims found across the chain. This is preserved as
historical evidence per this task's instruction, not merged.

## `docs/smart_routing/` — 23 files (all uncommitted)

Phase 16 (audit + `phase16_phase17_to_phase26_implementation_map.md`,
`phase16_capability_matrix.md`, `phase16_duplication_prevention_map.md`,
`phase16_existing_system_audit_and_gap_report.md`,
`phase16_existing_system_audit_plan.md`, `phase16_risk_register.md`) through
Phase 20 (`phase20_mcp_readiness_and_security_boundary.md`,
`phase20_web_source_trust_and_verification_policy.md`). Phases 21–26 are
referenced in the implementation map (`phase16_phase17_to_phase26_
implementation_map.md`) as forward planning; only phases 16–20 have their
own dedicated doc files present. See the phase-numbering finding above —
this track's "Phase 20" is Trusted Web, unrelated to Main Brud AI's own
Phase 20 (corpus release).

## `docs/admin_assistant/`, `docs/data_discovery/`, `docs/data_providers/`, `docs/data_verification/`, `docs/production/`, `docs/rag_sandbox/`, `docs/sample_import/`, `docs/training/`

4 + 2 + 2 + 2 + 4 + 2 + 2 + 2 = 20 files, all uncommitted. One doc set per
feature area listed in `repository_cleanup_audit.md`'s category-A table;
each corresponds 1:1 to the backend/frontend implementation of that same
area (e.g. `docs/production/phase15a_production_verification_and_
remediation.md` documents the `production_readiness_governance` code area).
No orphan docs found (every doc here has a matching, real implementation
directory) and no orphan implementation found without a doc.

## Summary

- Total doc files: 243
- Committed / stable reference: 170 (Main Brud AI track + root subsystem docs)
- Uncommitted, matching real uncommitted implementation: 72 (data_studio 28 new + admin_assistant/data_discovery/data_providers/data_verification/production/rag_sandbox/sample_import/training/smart_routing 44)
- Duplicate documents found: 0
- Contradictory completion claims found: 0
- Stale/archival candidates flagged (not moved): 11 (`database_schema_v2..19.md`)
