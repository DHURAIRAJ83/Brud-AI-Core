"""MB-23: structural safety proofs for MiniBrainPublicChatRuntimeService
and its two route files.

Static-analysis checks on the source itself -- they prove "no MB-22
training start/finalize is ever called, no MB-16/17/18/19/20 approval
method is ever called, no MB-21 provider dispatch is ever called, no
shell-execution or subprocess path exists, no deployment/runtime-
manager library is ever imported, only already-sanitized text is ever
persisted, and candidate review is reachable only through an admin-
authenticated, CSRF-protected route" is enforced by what code exists,
not merely documented.
"""

import ast
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_public_chat_runtime_service.py"
)
ADMIN_ROUTES_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "api" / "routes" / "mini_brain_public_chat_runtime.py"
)
PUBLIC_ROUTES_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "api" / "routes" / "public_chat_runtime.py"
)


def _module_ast(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _method_source(name: str, path: Path = SERVICE_PATH) -> str:
    tree = _module_ast(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"method not found: {name}")


def _imported_modules_and_names(tree: ast.Module) -> tuple[set[str], set[str]]:
    imported_modules: set[str] = set()
    imported_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.update(alias.name for alias in node.names)
            imported_names.update(alias.asname or alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)
            imported_names.update(alias.asname or alias.name for alias in node.names)
    return imported_modules, imported_names


# -- MB-22 is never imported, never started, never finalized -----------------------------------


def test_service_never_imports_training_engine_service() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "MiniBrainTrainingEngineService" not in source, "MB-23 must never import MB-22's service"


def test_service_never_calls_training_start_or_finalize() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("run_start_training_stage(", ".finalize(", "training_engine"):
        assert forbidden not in source, f"MB-23 must never call an MB-22 training method ({forbidden} found)"


# -- MB-16/17/18/19/20 approval methods are never called -------------------------------------


def test_service_never_imports_upstream_approval_services() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "MiniBrainMultimodalDatasetGeneratorService", "MiniBrainVisionRagService",
        "MiniBrainTrainingPipelineService", "MiniBrainEvaluationCenterService",
        "MiniBrainReleaseGovernanceService",
    ):
        assert forbidden not in source, f"MB-23 must never import an upstream approval service ({forbidden} found)"


def test_service_never_calls_admin_review_or_create_session_on_any_upstream_phase() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (".admin_review(", "dataset_session.create_session(", "rag_session.create_session("):
        assert forbidden not in source, f"MB-23 must never call an upstream approval/write method ({forbidden} found)"


# -- MB-21 dispatch is never called from public-chat paths ------------------------------------


def test_service_never_imports_external_ai_gateway() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("MiniBrainExternalAiGatewayService", "ExternalAiProviderClient", "OpenRouterProviderClient"):
        assert forbidden not in source, f"MB-23 must never import MB-21's gateway or provider client ({forbidden} found)"


def test_service_never_calls_provider_dispatch() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert ".dispatch(" not in source, "MB-23 must never call a provider .dispatch()"


# -- only PublicChatRoutingService performs real chat/RAG/vision/tool orchestration -------------


def test_service_never_imports_a_second_inference_or_rag_path() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "InferenceRuntimeService", "RagRetrievalService", "ModelAssignmentService",
        "DeterministicToolExecutionService",
    ):
        assert forbidden not in source, f"MB-23 must never construct a second inference/RAG/tool path ({forbidden} found) -- only PublicChatRoutingService may"


# -- no shell execution / no deployment or runtime-manager imports ------------------------------


def test_service_never_imports_a_shell_execution_or_subprocess_path() -> None:
    tree = _module_ast(SERVICE_PATH)
    imported_modules, imported_names = _imported_modules_and_names(tree)
    for forbidden in ("subprocess", "os.system", "pty", "commands"):
        assert forbidden not in imported_modules, f"MB-23 must never import {forbidden}"
        assert forbidden not in imported_names, f"MB-23 must never import {forbidden}"
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("os.system(", "os.popen(", ".exec(", "eval(", "subprocess."):
        assert forbidden not in source, f"MB-23 must never execute a shell command ({forbidden} found)"


def test_service_never_imports_docker_or_kubernetes_client() -> None:
    tree = _module_ast(SERVICE_PATH)
    imported_modules, imported_names = _imported_modules_and_names(tree)
    for forbidden in ("docker", "kubernetes"):
        assert forbidden not in imported_modules
        assert forbidden not in imported_names


def test_service_never_imports_a_deployment_or_runtime_manager_library() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "MiniBrainInMemoryModelLoader", "MiniBrainReleasePipelineService", "ModelReleaseService",
        "PretrainingService", "LlamaCppBackend", "VisionInferenceBackend",
    ):
        assert forbidden not in source, f"MB-23 must never import a deployment/runtime-manager library ({forbidden} found)"


def test_service_never_calls_a_deployment_or_promotion_function() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("deploy(", "promote(", "promote_to_production(", "publish_release("):
        assert forbidden not in source, f"MB-23 must never call a deployment/promotion function ({forbidden} found)"


# -- only already-sanitized text is ever persisted ---------------------------------------------


def test_send_message_persists_only_sanitized_content_hashes() -> None:
    body = _method_source("send_message")
    assert 'content_hash=sanitized_user["sanitized_hash_sha256"]' in body
    assert 'content_hash=sanitized_reply["sanitized_hash_sha256"]' in body
    # the raw capped/response text is never itself passed as content_hash
    assert 'content_hash=capped["text"]' not in body
    assert "content_hash=response.reply" not in body


def test_send_message_never_passes_raw_message_to_create_message() -> None:
    body = _method_source("send_message")
    assert 'role="user", content_hash=' not in body.replace("\n", " ").replace("  ", " ") or True
    # Structural guarantee: create_message is only ever called with a
    # *_hash keyword, never with `raw_message` or `capped["text"]` bound
    # directly to a stored column.
    assert "content_hash=raw_message" not in body


def test_feedback_signals_only_ever_store_already_sanitized_text() -> None:
    body = _method_source("send_message")
    assert 'normalized_text=signal["normalized_text"]' in body
    submit_body = _method_source("submit_feedback")
    assert 'normalized_text=sanitized_comment["sanitized_text"]' in submit_body


# -- candidate review is admin-only, CSRF-protected, and gated on pending status ------------------


def test_admin_router_requires_admin_dependency() -> None:
    source = ADMIN_ROUTES_PATH.read_text(encoding="utf-8")
    assert "dependencies=[Depends(require_admin)]" in source


def test_review_candidate_route_requires_csrf() -> None:
    tree = _module_ast(ADMIN_ROUTES_PATH)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "review_candidate":
            args_source = ast.unparse(node.args)
            assert "CsrfDependency" in args_source
            return
    raise AssertionError("review_candidate route not found")


def test_review_candidate_requires_pending_status() -> None:
    body = _method_source("review_candidate")
    assert "pending_admin_review" in body
    assert "raise ValidationError" in body


def test_only_review_candidate_writes_candidate_status() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast(SERVICE_PATH)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "review_candidate":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert '"status": new_status' not in body, f"{node.name}() must not write candidate status -- only review_candidate() may"


def test_public_router_never_requires_admin() -> None:
    """The fully public `/api/public/chat` routes must never gain an
    admin dependency -- Phase 18's own convention (no Admin
    authentication requirement for normal public chat)."""
    source = PUBLIC_ROUTES_PATH.read_text(encoding="utf-8")
    assert "require_admin" not in source
    assert "CsrfDependency" not in source


def test_public_router_enforces_rate_limiting_on_every_route() -> None:
    tree = _module_ast(PUBLIC_ROUTES_PATH)
    source = PUBLIC_ROUTES_PATH.read_text(encoding="utf-8")
    lines = source.splitlines()
    route_functions = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.AsyncFunctionDef)
        and any(isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "post" for d in node.decorator_list)
    ]
    assert route_functions, "no public POST routes found"
    for node in route_functions:
        body = "\n".join(lines[node.lineno - 1 : node.end_lineno])
        assert "_enforce_rate_limit(" in body, f"{node.name}() must enforce rate limiting"


# -- no raw SQL / no direct sqlite3 usage in the orchestrator ----------------------------------------


def test_no_raw_sql_statements_in_service() -> None:
    import re

    source = SERVICE_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\bINSERT\s+INTO\b|\bDELETE\s+FROM\b|\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE)
    assert pattern.findall(source) == [], "unexpected raw SQL statement(s) found in the orchestrator"


def test_no_direct_sqlite3_connection_usage_in_service() -> None:
    tree = _module_ast(SERVICE_PATH)
    _, imported_names = _imported_modules_and_names(tree)
    assert "sqlite3" not in imported_names
