# Master Brud AI End-to-End Audit — 03: Dead Code & Orphan Code Audit

**Audit Date:** 2026-09-01  
**Auditor:** Principal Software Architect  
**Confidence Rating:** HIGH CONFIDENCE (Verified by grep usage analysis and runtime call graph inspection)  

---

## 1. Master Dead / Orphan Code Registry

| Registry ID | Category | Location / File Path | Active Alternative | Nature of Dead / Orphan Code | Risk Level | Recommended Non-Mutating Action |
|---|---|---|---|---|---|---|
| **DEAD-001** | Empty Directory / Stub | `core_model/inference/` | `core_model/inference_runtime/` | Contains only empty `__init__.py` (354 bytes). No inference code lives here. | Low | Retain in repository; document as superseded by `inference_runtime/`. |
| **DEAD-002** | Placeholder Models | `models/brud_v1.gguf`, `candidate_model.gguf`, `tiny_model.gguf`, `trained_model.gguf` | `artifacts/candidates/phase60/checkpoints/checkpoint_best.pt` | Dummy text files (9 to 21 bytes each) created as filesystem placeholders in early phases. | Low | Leave untouched; do not delete (tests may assert file existence). |
| **DEAD-003** | Uncalled Model Stubs | `core_model/rag/embedding.py::local_sentence_transformer` | `core_model/rag/embedding.py::local_custom_embedding` | Function registered in provider types but raises an exception if called; no model downloaded. | Low | Document that sentence-transformers is a planned future integration. |
| **ORPHAN-001** | Unwired Desktop Packaging | `apps/admin-dashboard/node_modules/playwright-core/lib/server/electron` | Web Browser Vite server (:5174) | Electron was documented in past plans as desktop target, but zero application wrapper exists. | Low | Clarify in documentation that Brud is a Web-first application, not an Electron desktop app. |
| **ORPHAN-002** | Legacy Checkpoint Adapters | `data/core_models/checkpoints/adapter-it-*` (1,200+ files) | `artifacts/candidates/phase60/checkpoints/` | Integration test artifacts from Phases 21-30 taking up ~150 MB of disk space. | Low | Preserve as historical test evidence; do not mutate. |
| **ORPHAN-003** | Root Phase Manifests | `./phase59_ws02_transformation_manifest.json`, `./phase59_ws07_manifest.json`, etc. | `artifacts/candidates/phase60/` | Manifests from previous completed phases left at repo root. | Low | Keep preserved for provenance audit. |
| **CONFLICT-001** | RBAC Role Persistence | `backend/services/admin_assistant_tool_governance.py` | `data/database/brud_ai.db` | Admin accounts table has no `role` column; roles are parsed from `BRUD_ADMIN_ROLE_OVERRIDES` in env. | Medium | Maintain env overrides until a formal database migration is scheduled. |
| **CONFLICT-002** | Public Chat Route vs Model State | `backend/api/routes/public_chat_runtime.py` | `PublicModelAssignmentResolver` | Public chat routes exist and are functional, but `public_chat_model_enabled` defaults to `False` and zero assignments exist. | Low | Desired security invariant: prevents untrained model from serving public traffic. |

---

## 2. Dead Code Impact Assessment

- **Is dead code degrading performance?** No. Dead files are not imported on hot execution paths and do not consume CPU or RAM at runtime.
- **Is dead code creating security vulnerabilities?** No. Placeholder GGUFs and empty directories have no executable code.
- **Action Directive:** Under the absolute read-only governance rule, **do not delete or rename any dead or orphan files**. Document their status to prevent developer confusion.
