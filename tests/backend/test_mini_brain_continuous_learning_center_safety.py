"""MB-09: structural safety proofs for
MiniBrainContinuousLearningCenterService.

Static-analysis checks on the service source itself -- they prove the
"planning and recommendation layer only" boundary is enforced by what
code exists, not merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_continuous_learning_center_service.py"
)


def _module_ast() -> ast.Module:
    return ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))


def _attribute_calls(tree: ast.Module) -> list[tuple[str, str]]:
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            if isinstance(receiver, ast.Attribute) and isinstance(receiver.value, ast.Name):
                receiver_name = f"{receiver.value.id}.{receiver.attr}"
            elif isinstance(receiver, ast.Name):
                receiver_name = receiver.id
            else:
                continue
            calls.append((receiver_name, node.func.attr))
    return calls


def test_only_calls_read_only_mb08_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.continuous_learning"}
    assert used == {"list_sessions", "session"}, f"unexpected MB-08 method(s) called: {used}"


def test_only_calls_read_only_dataset_intelligence_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.dataset_intelligence"}
    assert used <= {"training", "analyze"}, f"unexpected MiniBrainDatasetIntelligenceService method(s) called: {used}"


def test_only_calls_expected_duplicate_service_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.duplicate_service"}
    assert used <= {"group_normalized_duplicates", "find_conflicts"}, (
        f"unexpected ExternalDatasetDuplicateService method(s) called: {used}"
    )


def test_never_imports_dataset_service_write_class_beyond_construction() -> None:
    """DatasetService is only ever constructed to hand to
    MiniBrainDatasetIntelligenceService (read-only) -- MB-09 must never
    call .create_source()/.create_record()/.update_source() on it
    directly."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (".create_source(", ".create_record(", ".update_source("):
        assert forbidden not in source, f"MB-09 must not call DatasetService.{forbidden}"


def test_never_imports_training_release_runtime_or_rag_services() -> None:
    """MB-09 must never reach into the Training Engine, MB-06, MB-07,
    Runtime, or RAG Sandbox -- proven by absence of the import."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "PretrainingService", "ModelReleaseService", "MiniBrainInMemoryModelLoader",
        "MiniBrainLearningSupervisorService", "MiniBrainReleasePipelineService",
        "RagSandboxEligibilityService", "RagSandboxCorpusService", "RagSandboxIndexService",
        "RagSandboxRetrievalService", "RagSandboxAnswerService", "RagSandboxEvaluationService",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-09 must not import {name}"


def test_never_imports_or_calls_an_external_ai_provider_client() -> None:
    """No Anthropic/OpenAI/Gemini/OpenRouter client library or API call
    exists anywhere in this file -- Multi-Provider Consensus is
    request-preparation and already-collected-result comparison only."""
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("anthropic", "openai", "google.generativeai", "genai.", "requests.post", "httpx.post", "urllib.request"):
        assert forbidden not in source, f"MB-09 must never call an external provider ({forbidden} found)"


def test_no_raw_sql_statements_in_service() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\bINSERT\s+INTO\b|\bDELETE\s+FROM\b|\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE)
    matches = pattern.findall(source)
    assert matches == [], f"unexpected raw SQL statement(s) found in the orchestrator: {matches}"


def test_no_direct_sqlite3_connection_usage() -> None:
    tree = _module_ast()
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.asname or alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.asname or alias.name for alias in node.names)
    assert "sqlite3" not in imported_names
    assert "database_connection" not in imported_names


def test_admin_review_never_calls_another_phases_service() -> None:
    """All six admin decisions (reject/edit/approve_draft/
    request_provider_consensus/send_to_rag/archive) must only ever
    record the decision -- none may call MB-06, MB-07, Dataset Studio,
    or RAG Sandbox."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    admin_review_body = source.split("def admin_review(")[1].split("\n\n\n")[0]
    for forbidden in (
        "MiniBrainLearningSupervisorService", "MiniBrainReleasePipelineService",
        "RagSandbox", "DatasetService(", "create_source", "create_record",
    ):
        assert forbidden not in admin_review_body, f"admin_review() must not reference {forbidden}"


def test_learning_memory_table_is_never_updated_or_deleted_by_the_service() -> None:
    """Learning memory is permanent -- the service must only ever call
    the repository's insert-only record_memory()/list_memory()/
    get_memory(), never anything implying mutation."""
    tree = _module_ast()
    calls = _attribute_calls(tree)
    memory_related = {m for r, m in calls if r == "self.repository" and "memory" in m.lower()}
    assert memory_related <= {"record_memory", "list_memory", "get_memory"}, (
        f"unexpected memory repository call(s): {memory_related}"
    )
