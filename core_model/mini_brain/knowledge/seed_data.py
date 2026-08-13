"""MB-02 seed content for the Brud Knowledge Core.

Every item below describes something directly verified in this
codebase during this engagement (an architecture audit, the MB-01
build, and the phase-history audit) -- file paths, route prefixes,
and behavioral claims are all real, not invented. This is a
representative seed, not an exhaustive catalog: ~50 items across 7
domains, not one row per table/route/service in a 400+ table schema.
Coverage numbers computed from this seed are honest about that scope,
never inflated.

`REFERENCE_COUNTS` holds real counts from the architecture audit
(`docs` artifact this session) used to compute honest catalog-coverage
percentages -- e.g. "8 admin_dashboard items out of 43 real backend
route modules" rather than a fabricated 100%.
"""

from __future__ import annotations

from typing import Any

DOMAINS: list[dict[str, str]] = [
    {"key": "admin_dashboard", "name": "Admin Dashboard",
     "description": "Every page, module, feature, component, workflow, button, menu, "
     "setting, API, and backend service of the admin-dashboard React app."},
    {"key": "dataset_system", "name": "Dataset System",
     "description": "Dataset types, rules, validation, quality, cleaning, approval, "
     "export, and standards."},
    {"key": "training_system", "name": "Training System",
     "description": "Tokenizer, pretraining, instruction tuning, evaluation, model "
     "registry, inference runtime, production readiness."},
    {"key": "rag", "name": "RAG",
     "description": "Knowledge spaces, chunking, embedding workflow, retrieval, "
     "knowledge routing, knowledge gaps, trusted web."},
    {"key": "architecture", "name": "Architecture",
     "description": "Folder structure, backend, frontend, core model, services, "
     "repositories, database, APIs, runtime."},
    {"key": "development_rules", "name": "Development Rules",
     "description": "Coding standards, naming standards, security rules, testing "
     "standards, documentation standards, error handling."},
    {"key": "brud_ai_policies", "name": "Brud AI Policies",
     "description": "Admin rules, approval rules, workflow rules, safety rules, "
     "development policies, future expansion policies."},
]

# Real counts from this session's architecture audit -- used only to
# compute honest catalog_coverage_pct, never presented as if this seed
# covers all of them.
REFERENCE_COUNTS: dict[str, int] = {
    "admin_dashboard": 39,   # admin-dashboard pages
    "dataset_system": 9,     # dataset_sample_*_service.py modules (quality/dup/contamination/etc.)
    "training_system": 15,   # tokenizer/pretraining/incremental_training/model_release services
    "rag": 24,                # RAG schema tables (Phase 16)
    "architecture": 6,        # top-level architectural layers documented
    "development_rules": 6,   # rule categories requested for this domain
    "brud_ai_policies": 5,    # policy categories requested for this domain
}


def _item(
    title: str, category: str, description: str, *,
    keywords: list[str], tags: list[str],
    related_features: list[str] | None = None,
    related_apis: list[str] | None = None,
    related_services: list[str] | None = None,
    related_documentation: list[str] | None = None,
    source: str, version: str = "1.0",
) -> dict[str, Any]:
    return {
        "title": title, "category": category, "description": description,
        "keywords": keywords, "tags": tags,
        "related_features": related_features or [],
        "related_apis": related_apis or [],
        "related_services": related_services or [],
        "related_documentation": related_documentation or [],
        "source": source, "version": version,
    }


ITEMS: dict[str, list[dict[str, Any]]] = {
    "admin_dashboard": [
        _item("Documents Page", "Page",
              "PDF upload, OCR/embedded extraction, page review, cleanup, Tamil quality, "
              "candidates, SFT export -- one shared React page across all document stages.",
              keywords=["documents", "pdf", "ocr", "upload"], tags=["page", "document-sft"],
              related_apis=["/api/admin/documents"], related_services=["document_service"],
              related_documentation=["docs/document_processing.md"],
              source="apps/admin-dashboard/src/pages/DocumentsPage.jsx"),
        _item("Conversation & Memory Page", "Page",
              "14-tab page hosting the Grounded Conversation Lab -- memory policies, "
              "sessions, chat orchestration, memory retrieval, evaluation.",
              keywords=["conversation", "memory", "chat lab", "rag"], tags=["page", "chat"],
              related_apis=["/api/admin/conversation-memory"],
              related_services=["ChatOrchestrationService", "MemoryService"],
              related_documentation=["docs/conversation_memory_architecture.md", "docs/admin_chat_lab.md"],
              source="apps/admin-dashboard/src/pages/ConversationMemoryPage.jsx"),
        _item("Admin Assistant Widget", "Component",
              "Floating, always-mounted widget. Deterministic-first: read-only "
              "questions never touch the LLM. Never mutates directly.",
              keywords=["assistant", "widget", "floating"], tags=["component", "admin-assistant"],
              related_apis=["/api/admin/assistant"],
              related_services=["AdminAssistantChatService", "AdminAssistantService"],
              related_documentation=["docs/admin_assistant.md"],
              source="apps/admin-dashboard/src/components/admin-assistant/AdminAssistantWidget.jsx"),
        _item("Brud Mini Brain Page", "Page",
              "MB-01/MB-02: independent admin-only module page -- status, settings, "
              "logs, diagnostics, and (MB-02) the Knowledge Core browser.",
              keywords=["mini brain", "framework", "knowledge core"], tags=["page", "mini-brain"],
              related_apis=["/api/admin/mini-brain"],
              related_services=["MiniBrainService", "MiniBrainKnowledgeService"],
              related_documentation=["MB-01 Completion Report", "MB-02 Completion Report"],
              source="apps/admin-dashboard/src/pages/MiniBrainPage.jsx"),
        _item("Sidebar Navigation", "Component",
              "Single source of truth nav tree (`navTree`) -- a collapsible 'Data' "
              "group plus 21 top-level entries, 3 of which (Chat Testing, Audit Logs, "
              "Settings) route to a generic placeholder, not a real page.",
              keywords=["sidebar", "navigation", "menu"], tags=["component", "navigation"],
              related_documentation=["Architecture Audit report"],
              source="apps/admin-dashboard/src/components/Sidebar.jsx"),
        _item("Knowledge & RAG Page", "Page",
              "Knowledge spaces, sources, chunk-sets, embeddings, vector/keyword "
              "indexes, retrieval profiles.",
              keywords=["rag", "knowledge space", "embeddings"], tags=["page", "rag"],
              related_apis=["/api/admin/rag"], related_services=["RagRetrievalService", "RagIngestionService"],
              related_documentation=["docs/rag_architecture.md"],
              source="apps/admin-dashboard/src/pages/RagPage.jsx"),
        _item("Inference Runtime Page", "Page",
              "Runtime profiles, instances, load/unload, scoped assignments "
              "(validate -> approve -> activate).",
              keywords=["inference", "runtime", "assignment"], tags=["page", "runtime"],
              related_apis=["/api/admin/inference-runtime"], related_services=["InferenceRuntimeService"],
              related_documentation=["docs/inference_runtime_architecture.md"],
              source="apps/admin-dashboard/src/pages/InferenceRuntimePage.jsx"),
        _item("Admin Session Authentication", "Backend Service",
              "Cookie session token (`require_admin`) plus double-submit CSRF "
              "cookie/header (`require_csrf`) -- single admin trust tier, no RBAC.",
              keywords=["auth", "csrf", "session"], tags=["service", "security"],
              related_services=["require_admin", "require_csrf"],
              source="backend/api/auth.py"),
        _item("Settings Nav Entry", "Setting",
              "Present in the sidebar nav tree but has no matching branch in "
              "App.jsx -- falls through to a generic placeholder page. Not implemented.",
              keywords=["settings", "placeholder", "gap"], tags=["setting", "known-gap"],
              related_documentation=["Architecture Audit report"],
              source="apps/admin-dashboard/src/components/Sidebar.jsx"),
        _item("Chat Testing Nav Entry", "Menu",
              "Present in the sidebar nav tree but has no matching branch in "
              "App.jsx -- falls through to a generic placeholder page. Not implemented.",
              keywords=["chat testing", "placeholder", "gap"], tags=["menu", "known-gap"],
              related_documentation=["Architecture Audit report"],
              source="apps/admin-dashboard/src/components/Sidebar.jsx"),
    ],
    "dataset_system": [
        _item("Dataset Import Pipeline", "Workflow",
              "Upload, parse, mapping, confirm, cancel, report -- 10 endpoints.",
              keywords=["import", "upload", "mapping"], tags=["workflow", "dataset"],
              related_apis=["/api/admin/datasets/imports"], related_services=["import_service"],
              related_documentation=["docs/dataset_imports.md"],
              source="backend/api/routes/imports.py"),
        _item("Dataset Sample Quality Service", "Service",
              "Automated quality checks run before a sample can be approved.",
              keywords=["quality", "validation"], tags=["service", "dataset"],
              related_services=["dataset_sample_quality_service"],
              related_documentation=["docs/dataset_quality.md"],
              source="backend/services/dataset_sample_quality_service.py"),
        _item("Dataset Verification & Rights", "Workflow",
              "Licence/rights verification gate -- a source with an unknown or "
              "mismatched licence is structurally blocked from training eligibility.",
              keywords=["licence", "rights", "verification"], tags=["workflow", "rule"],
              related_apis=["/api/admin/dataset-verification"],
              related_services=["dataset_verification_source_rights_service"],
              source="backend/api/routes/dataset_verification.py"),
        _item("Duplicate Detection", "Rule",
              "Exact and near-duplicate detection across dataset samples, hash-based.",
              keywords=["duplicate", "dedup"], tags=["rule", "dataset"],
              related_services=["dataset_sample_duplicate_service"],
              source="backend/services/dataset_sample_duplicate_service.py"),
        _item("Dataset Export", "Workflow",
              "JSONL export of approved records; finalizing an export never starts "
              "training automatically.",
              keywords=["export", "jsonl"], tags=["workflow", "dataset"],
              related_documentation=["docs/dataset_export.md"],
              source="backend/services/document_sft_export_service.py"),
        _item("Dataset Versioning", "Standard",
              "Immutable, checksummed dataset versions -- never edited in place.",
              keywords=["versioning", "immutable", "checksum"], tags=["standard", "dataset"],
              related_documentation=["docs/dataset_versioning.md"],
              source="backend/services/dataset_versioning.py"),
        _item("Contamination Checking", "Rule",
              "Detects evaluation/test/regression-fixture leakage into training data.",
              keywords=["contamination", "leakage"], tags=["rule", "dataset"],
              related_services=["dataset_sample_contamination_service"],
              source="backend/services/dataset_sample_contamination_service.py"),
        _item("Sample Import & Quarantine", "Workflow",
              "Approved sample import with file-safety validation and quarantine "
              "review before use.",
              keywords=["quarantine", "sample import"], tags=["workflow", "dataset"],
              related_apis=["/api/admin/dataset-sample-import"],
              source="backend/api/routes/dataset_sample_import.py"),
    ],
    "training_system": [
        _item("Tokenizer Training", "Module",
              "SentencePiece BPE tokenizer training, corpus management, candidate "
              "comparison.",
              keywords=["tokenizer", "sentencepiece", "bpe"], tags=["module", "training"],
              related_apis=["/api/admin/tokenizers"], related_services=["tokenizer_corpus_service"],
              related_documentation=["docs/tokenizer_architecture.md"],
              source="backend/api/routes/tokenizers.py"),
        _item("Bounded Pretraining", "Module",
              "CPU-bounded pretraining worker; trains only from registered "
              "immutable dataset versions and verified tokenizer metadata.",
              keywords=["pretraining", "cpu", "worker"], tags=["module", "training"],
              related_apis=["/api/admin/pretraining"], related_services=["pretraining_service"],
              related_documentation=["docs/pretraining_architecture.md"],
              source="backend/api/routes/pretraining.py"),
        _item("Instruction Tuning", "Module",
              "Response-only masked supervised fine-tuning -- system/user/padding "
              "tokens never contribute to loss.",
              keywords=["instruction tuning", "sft", "masking"], tags=["module", "training"],
              related_apis=["/api/admin/instruction-tuning"],
              related_documentation=["docs/instruction_tuning_training.md"],
              source="backend/api/routes/instruction_tuning.py"),
        _item("Multilingual Evaluation", "Module",
              "Fixture-suite evaluation, safety validation, human review, "
              "conservative chat-readiness gate.",
              keywords=["evaluation", "safety", "readiness gate"], tags=["module", "training"],
              related_apis=["/api/admin/model-evaluation"],
              related_documentation=["docs/multilingual_evaluation.md"],
              source="backend/api/routes/model_evaluation.py"),
        _item("Model Release Registry", "Module",
              "Release families/candidates, 14-dimension eligibility, model cards, "
              "approvals, semantic-style versioning, metadata-only rollback.",
              keywords=["model release", "registry", "eligibility"], tags=["module", "training"],
              related_apis=["/api/admin/model-release"], related_services=["model_release_service"],
              related_documentation=["docs/model_release_registry.md"],
              source="backend/api/routes/model_release.py"),
        _item("Inference Runtime", "Module",
              "Verify-then-load pipeline, scoped assignments, admin chat lab, "
              "canary, rollback.",
              keywords=["inference", "runtime", "canary"], tags=["module", "training"],
              related_apis=["/api/admin/inference-runtime"],
              related_services=["InferenceRuntimeService", "model_assignment_service"],
              related_documentation=["docs/inference_runtime_architecture.md"],
              source="backend/api/routes/inference_runtime.py"),
        _item("Production Readiness", "Module",
              "Backup, rollback, canary, secret-scan, and abuse-readiness checks "
              "before a release goes live.",
              keywords=["production", "readiness", "rollback"], tags=["module", "training"],
              related_apis=["/api/admin/production-readiness"],
              source="backend/api/routes/production_readiness.py"),
        _item("Incremental Training", "Module",
              "Checkpoint promotion, human review, comparison, acceptance for "
              "ongoing (post-initial) training runs.",
              keywords=["incremental training", "checkpoint"], tags=["module", "training"],
              related_apis=["/api/admin/incremental-training"],
              source="backend/api/routes/incremental_training.py"),
    ],
    "rag": [
        _item("Knowledge Spaces", "Concept",
              "Approved-source knowledge spaces -- only `approved` sources' chunks "
              "are ever eligible for embedding or keyword indexing.",
              keywords=["knowledge space", "approved source"], tags=["concept", "rag"],
              related_documentation=["docs/rag_knowledge_ingestion.md"],
              source="backend/services/rag_ingestion_service.py"),
        _item("Semantic Chunking", "Workflow",
              "Deterministic chunking with quality and prompt-injection filtering "
              "applied before a chunk can ever enter an index.",
              keywords=["chunking", "injection filter"], tags=["workflow", "rag"],
              related_documentation=["docs/rag_chunking.md"],
              source="backend/services/semantic_chunk_service.py"),
        _item("Embedding Workflow", "Workflow",
              "Versioned embedding runs against a registered embedding model, tied "
              "to a specific chunk-set.",
              keywords=["embedding", "embedding run"], tags=["workflow", "rag"],
              related_documentation=["docs/rag_embeddings.md"],
              source="backend/api/routes/rag.py"),
        _item("Hybrid Retrieval", "Feature",
              "Vector + FTS5 keyword hybrid retrieval with deterministic "
              "tie-breaking; access filters applied before scoring, never after.",
              keywords=["retrieval", "hybrid", "fts5"], tags=["feature", "rag"],
              related_services=["RagRetrievalService"],
              related_documentation=["docs/rag_hybrid_retrieval.md"],
              source="backend/services/rag_retrieval_service.py"),
        _item("Citation Validation", "Rule",
              "Citations assigned only from retrieved evidence, validated against "
              "4 outcomes: valid/valid_with_warning/invalid/not_present.",
              keywords=["citation", "grounding"], tags=["rule", "rag"],
              related_documentation=["docs/rag_citations_and_grounding.md"],
              source="backend/services/chat_orchestration_service.py"),
        _item("Knowledge Routing", "Module",
              "7-way public chat router: core_model/approved_rag/memory/"
              "trusted_web/tool/clarify/refuse, plus an insufficient fail-closed "
              "fallback.",
              keywords=["routing", "public chat"], tags=["module", "rag"],
              related_services=["PublicChatRoutingService"],
              source="backend/services/public_chat_routing_service.py"),
        _item("Knowledge Gap Registry", "Module",
              "Captures unanswerable public questions, clusters and prioritizes "
              "them, routes back into the data pipeline.",
              keywords=["knowledge gap", "gap registry"], tags=["module", "rag"],
              related_apis=["/api/admin/knowledge-gaps"],
              source="backend/api/routes/knowledge_gap_admin.py"),
        _item("Trusted Web Gateway", "Module",
              "Bounded external web search fallback with citation and PII "
              "handling.",
              keywords=["trusted web", "web search"], tags=["module", "rag"],
              related_apis=["/api/admin/trusted-web"],
              source="backend/api/routes/trusted_web_admin.py"),
    ],
    "architecture": [
        _item("core_model / backend split", "Pattern",
              "Every domain area has a `core_model/<area>` package (pure functions, "
              "zero I/O) and a matching `backend/services/<area>_service.py` "
              "(impure DB/repository orchestration). Applied with zero exceptions "
              "across 177 service modules.",
              keywords=["core_model", "backend", "separation of concerns"],
              tags=["pattern", "architecture"],
              related_documentation=["Architecture Audit report"],
              source="core_model/, backend/services/"),
        _item("Repository Base Class", "Pattern",
              "`BaseRepository.transaction()` -- a context manager wrapping "
              "BEGIN/commit/rollback, with automatic audit-log write on "
              "ValidationError.",
              keywords=["repository", "transaction", "base class"], tags=["pattern", "architecture"],
              source="backend/database/repositories/base.py"),
        _item("Route Authentication Pattern", "Pattern",
              "Router-level `Depends(require_admin)`; mutating routes additionally "
              "declare a `CsrfDependency` parameter.",
              keywords=["route", "auth", "dependency injection"], tags=["pattern", "architecture"],
              source="backend/api/auth.py, backend/api/routes/*.py"),
        _item("Additive-Only Migration System", "Pattern",
              "46 sequential `_apply_vN` functions, each idempotent via a "
              "`schema_migrations` lookup, each executing its own "
              "`PHASE{N}_SCHEMA` script -- never an in-place rewrite of an "
              "earlier migration.",
              keywords=["migration", "schema version"], tags=["pattern", "architecture"],
              source="backend/database/migrations.py"),
        _item("Single Inference Provider", "Fact",
              "Exactly one AI provider exists (`InferenceRuntimeService`, local "
              "PyTorch, CPU). No provider interface/ABC, no Ollama, no "
              "OpenAI-compatible integration anywhere in this codebase.",
              keywords=["inference provider", "no ollama"], tags=["fact", "architecture"],
              related_documentation=["Architecture Audit report"],
              source="backend/services/inference_runtime_service.py"),
        _item("Repository Root Layout", "Reference",
              "backend/ (API+services+DB), core_model/ (pure domain logic), "
              "apps/admin-dashboard/ (React UI), tests/backend/ (pytest suite), "
              "docs/ (per-phase reports and architecture docs).",
              keywords=["folder structure", "layout"], tags=["reference", "architecture"],
              source="repository root"),
    ],
    "development_rules": [
        _item("Never Fabricate a Result", "Standard",
              "Every tool/service either returns real data or an honest "
              "`{\"available\": false}` -- never a fabricated status, count, or "
              "success. Directly quoted from admin_assistant_tools.py's own "
              "docstring and reused as MB-01/MB-02's own placeholder convention.",
              keywords=["honesty", "no fabrication"], tags=["standard", "rule"],
              source="backend/services/admin_assistant_tools.py"),
        _item("No Plugin Auto-Loading", "Security Rule",
              "\"No plugin auto-loading from any location, no arbitrary tool name "
              "accepted\" -- tools must be explicitly registered in code, never "
              "dynamically loaded.",
              keywords=["plugin", "security", "tool registry"], tags=["security rule", "rule"],
              source="backend/services/deterministic_tool_registry.py"),
        _item("CSRF Required on Mutations", "Security Rule",
              "Every POST/PATCH/DELETE admin route requires a `CsrfDependency` "
              "parameter -- GET routes never do.",
              keywords=["csrf", "security"], tags=["security rule", "rule"],
              source="backend/api/auth.py"),
        _item("Additive-Only Schema Changes", "Standard",
              "New migrations only ever add tables/columns; an existing CHECK "
              "constraint that needs to change requires a full table rebuild, "
              "never an in-place ALTER that could corrupt existing rows.",
              keywords=["migration", "schema"], tags=["standard", "rule"],
              source="backend/database/migrations.py"),
        _item("public_row() Boolean Convention", "Coding Standard",
              "Repository `public_row()` helpers must explicitly `bool()`-cast "
              "INTEGER flag columns before returning them as JSON -- found and "
              "fixed as a real bug in MB-01's own MiniBrainRepository.",
              keywords=["public_row", "boolean", "json"], tags=["coding standard", "rule"],
              source="backend/database/repositories/*.py"),
        _item("Append-Only Audit Tables", "Standard",
              "Diagnostic/log tables (audit_logs, mini_brain_events, this domain's "
              "own validation_reports) use `BEFORE UPDATE`/`BEFORE DELETE` "
              "triggers that RAISE(ABORT) -- immutability enforced at the "
              "database level, not just by convention.",
              keywords=["append-only", "immutable", "trigger"], tags=["standard", "rule"],
              source="backend/database/schema.py"),
    ],
    "brud_ai_policies": [
        _item("Admin Assistant Never Mutates Directly", "Policy",
              "Propose -> Admin Review approval -> execute via an existing, "
              "already-secured service call. Never a bespoke write path.",
              keywords=["admin assistant", "governance", "propose review execute"],
              tags=["policy", "governance"],
              related_documentation=["docs/admin_assistant.md"],
              source="backend/services/admin_assistant_service.py"),
        _item("Training Action Blocklist", "Safety Rule",
              "`BLOCKED_ACTION_SUBSTRINGS = (\"train\", \"pretrain\")` -- any action "
              "type containing either word is refused regardless of the action "
              "registry's contents. Defense in depth, not just registry scoping.",
              keywords=["training", "blocklist", "safety"], tags=["safety rule", "policy"],
              source="core_model/admin_assistant/action_registry.py"),
        _item("Public Chatbot Remains a Placeholder", "Policy",
              "`POST /api/chat` has never been wired to any model, across every "
              "phase audited this session (main track through Phase 22, and the "
              "later Data Studio / Smart Routing expansion).",
              keywords=["public chat", "placeholder"], tags=["policy", "known-limitation"],
              related_documentation=["Phase History Audit report"],
              source="backend/api/routes/chat.py"),
        _item("Mini Brain Never Answers Public Chat", "Policy",
              "MB-01's own hard rule -- Brud Mini Brain has no route, no code "
              "path, and no consideration anywhere for handling Public Chat "
              "traffic.",
              keywords=["mini brain", "public chat", "boundary"], tags=["policy", "mini-brain"],
              related_documentation=["MB-01 Completion Report"],
              source="backend/api/routes/mini_brain.py"),
        _item("No Role-Based Access Control", "Policy",
              "Every admin account is exactly as privileged as any other -- a "
              "documented, honest limitation, not a hidden gap.",
              keywords=["rbac", "permissions", "known-limitation"], tags=["policy", "known-limitation"],
              related_documentation=["Architecture Audit report"],
              source="backend/api/auth.py"),
    ],
}

# (from_title, to_title, relationship_type, description) -- titles are
# resolved to item public_ids at seed time, within and across domains.
# The first chain matches the exact example in the MB-02 task itself:
# Dataset -> Training -> Evaluation -> Model Registry -> Inference
# Runtime -> Production.
RELATIONSHIPS: list[tuple[str, str, str, str]] = [
    ("Dataset Export", "Tokenizer Training", "flows_to", "Exported dataset feeds tokenizer training."),
    ("Tokenizer Training", "Bounded Pretraining", "flows_to", "Trained tokenizer is required before pretraining."),
    ("Bounded Pretraining", "Instruction Tuning", "flows_to", "Pretrained checkpoint is the input to instruction tuning."),
    ("Instruction Tuning", "Multilingual Evaluation", "flows_to", "Tuned candidate is evaluated before release."),
    ("Multilingual Evaluation", "Model Release Registry", "flows_to", "Evaluation status gates release eligibility."),
    ("Model Release Registry", "Inference Runtime", "flows_to", "A released, eligible model can be assigned to a runtime."),
    ("Inference Runtime", "Production Readiness", "flows_to", "Runtime health feeds the production readiness gate."),
    ("Dataset Verification & Rights", "Dataset Export", "depends_on", "Export requires prior rights verification."),
    ("Duplicate Detection", "Contamination Checking", "related_to", "Both are pre-approval dataset safety checks."),
    ("Knowledge Spaces", "Semantic Chunking", "produces", "A knowledge space's sources are chunked."),
    ("Semantic Chunking", "Embedding Workflow", "flows_to", "Chunks are the input to an embedding run."),
    ("Embedding Workflow", "Hybrid Retrieval", "flows_to", "Embeddings back the vector half of hybrid retrieval."),
    ("Hybrid Retrieval", "Citation Validation", "flows_to", "Retrieved chunks are the source citations are validated against."),
    ("Knowledge Routing", "Trusted Web Gateway", "depends_on", "The router can select the trusted_web route."),
    ("Knowledge Routing", "Knowledge Gap Registry", "produces", "Unanswerable routed questions become gap candidates."),
    ("core_model / backend split", "Repository Base Class", "related_to", "Both are foundational architecture patterns."),
    ("Route Authentication Pattern", "CSRF Required on Mutations", "related_to", "The auth pattern is what CSRF enforcement builds on."),
    ("Admin Assistant Never Mutates Directly", "Admin Assistant Widget", "part_of", "The widget is the UI surface for this policy."),
    ("Training Action Blocklist", "Admin Assistant Never Mutates Directly", "depends_on", "Blocklist is enforced within the propose/execute flow."),
    ("Single Inference Provider", "Public Chatbot Remains a Placeholder", "related_to", "The one provider that exists has never been wired to /api/chat."),
    ("Mini Brain Never Answers Public Chat", "Public Chatbot Remains a Placeholder", "related_to", "Both describe the same public/admin boundary from different sides."),
    ("Brud Mini Brain Page", "Knowledge Spaces", "consumes", "MB-02's Knowledge Core browser will surface RAG knowledge-space facts as catalog items."),
]
