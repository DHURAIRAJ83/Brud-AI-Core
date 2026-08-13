"""MB-07: structural safety proofs for MiniBrainReleasePipelineService.

Static-analysis checks on the service source itself -- they prove the
safety boundary is enforced by what code exists, not merely
documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_release_pipeline_service.py"
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


def test_never_calls_training_execution_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    forbidden = {"validate_job", "queue_job", "pause", "resume", "cancel", "run_one", "create_job"}
    violations = [(r, m) for r, m in calls if r == "self.pretraining" and m in forbidden]
    assert violations == [], f"MB-07 must never trigger training: {violations}"


def test_only_calls_read_only_pretraining_method() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.pretraining"}
    assert used <= {"checkpoint"}, f"unexpected PretrainingService method(s) called: {used}"


def test_never_imports_or_uses_dataset_service() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DatasetService" not in source
    assert "dataset_service" not in source.lower().replace("dataset_version", "")


def test_never_writes_checkpoint_files() -> None:
    """MB-07 must only ever READ the checkpoint (via TrainingCheckpointManager
    .load_states()), never call .save() on it -- that would modify the
    source checkpoint, which is explicitly forbidden."""
    tree = _module_ast()
    calls = _attribute_calls(tree)
    checkpoint_manager_saves = [
        (r, m) for r, m in calls if "checkpoint_manager" in r.lower() and m == "save"
    ]
    assert checkpoint_manager_saves == []
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert ".save(" not in source


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


def test_only_activate_loads_a_model_into_the_shared_runtime_singleton() -> None:
    """Stage 6/7 (compatibility/performance) must use a throwaway
    LlamaCppBackend() instance, never MiniBrainInMemoryModelLoader's
    shared singleton -- otherwise an unapproved model could be
    activated into the real Runtime before Stage 11's admin gate."""
    tree = _module_ast()
    functions = {node.name: node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    for name, node in functions.items():
        calls = _attribute_calls(node)
        runtime_manager_calls = {m for r, m in calls if r == "self.runtime_manager"}
        if name == "activate":
            assert runtime_manager_calls == {"register_model", "load_model"}, (
                f"'activate' should only call register_model/load_model, found {runtime_manager_calls}"
            )
        else:
            assert not runtime_manager_calls, (
                f"'{name}' must not touch the shared Runtime singleton, found {runtime_manager_calls}"
            )


def test_admin_review_and_activate_are_gated_by_stage_and_decision() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    activate_body = source.split("def activate(")[1].split("\n\n    def ")[0]
    assert "admin_activation_decision" in activate_body
    assert "'production_activation'" in activate_body or '"production_activation"' in activate_body
