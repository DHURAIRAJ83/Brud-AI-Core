"""MB-06: structural safety proofs for MiniBrainLearningSupervisorService.

These are static-analysis checks on the service source itself, not
behavioral tests -- they prove the safety boundary is enforced by what
code exists (it CANNOT call the forbidden methods because no such call
site exists), not merely documented. This matches the same discipline
already used for MB-06's `training_request_builder`/`training_result_analyzer`
reuse of `core_model.training.diagnostics` unchanged.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_learning_supervisor_service.py"
)

FORBIDDEN_PRETRAINING_METHODS = {
    "validate_job", "queue_job", "pause", "resume", "cancel", "run_one",
}


def _module_ast() -> ast.Module:
    return ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))


def _attribute_calls(tree: ast.Module) -> list[tuple[str, str]]:
    """Return (receiver_name, method_name) for every `X.method(...)` call
    where X is a simple name (e.g. `self.pretraining`)."""
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


def test_never_calls_forbidden_pretraining_execution_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    violations = [
        (receiver, method) for receiver, method in calls
        if receiver == "self.pretraining" and method in FORBIDDEN_PRETRAINING_METHODS
    ]
    assert violations == [], f"forbidden Training Engine execution call(s) found: {violations}"


def test_only_calls_permitted_pretraining_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {method for receiver, method in calls if receiver == "self.pretraining"}
    permitted = {
        "create_job", "get_job", "events", "metrics", "checkpoints", "checkpoint",
        "evaluations", "evaluation", "promote",
    }
    assert used <= permitted, f"unexpected pretraining method(s) called: {used - permitted}"
    # sanity: the permitted set isn't vacuously satisfied by calling nothing
    assert used, "expected the service to call at least one PretrainingService method"


def test_never_calls_rag_sandbox_setup_methods() -> None:
    """Corpus/index/query-set/retrieval creation must remain admin-driven
    through the existing RAG Sandbox admin flow -- MB-06 only runs
    generation, evaluation, and report finalization on top of them."""
    tree = _module_ast()
    calls = _attribute_calls(tree)
    forbidden_receivers = {
        "self.rag_corpus", "self.rag_index", "self.rag_query_set", "self.rag_retrieval",
        "self.rag_eligibility", "self.rag_approval",
    }
    violations = [(receiver, method) for receiver, method in calls if receiver in forbidden_receivers]
    assert violations == [], f"MB-06 must not perform RAG Sandbox setup itself: {violations}"


def test_no_raw_sql_statements_in_service() -> None:
    """MB-06 must do zero direct database manipulation outside its own
    two tables -- proven by having no raw SQL string in the file at all;
    every persistence call goes through MiniBrainLearningRepository or
    another system's own service methods."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    pattern = re.compile(r"\bINSERT\s+INTO\b|\bDELETE\s+FROM\b|\bUPDATE\s+\w+\s+SET\b", re.IGNORECASE)
    matches = pattern.findall(source)
    assert matches == [], f"unexpected raw SQL statement(s) found in the orchestrator: {matches}"


def test_no_direct_sqlite3_connection_usage() -> None:
    """MB-06 must never open its own ad-hoc database connection -- all
    reads/writes go through the repository/service layers that already
    own transaction and immutability discipline."""
    tree = _module_ast()
    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_names.update(alias.asname or alias.name for alias in node.names)
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.asname or alias.name for alias in node.names)
    assert "sqlite3" not in imported_names
    assert "database_connection" not in imported_names
