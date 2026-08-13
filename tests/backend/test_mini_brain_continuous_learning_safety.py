"""MB-08: structural safety proofs for
MiniBrainContinuousLearningService.

Static-analysis checks on the service source itself -- they prove the
"advisory only, never writes to another system's tables" boundary is
enforced by what code exists, not merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_continuous_learning_service.py"
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


def test_only_calls_read_only_knowledge_gap_repository_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.knowledge_gap"}
    assert used == {"list_cases"}, f"unexpected KnowledgeGapRepository method(s) called: {used}"


def test_only_calls_read_only_public_chat_repository_methods() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.public_chat"}
    assert used <= {"list_events", "list_feedback_events"}, (
        f"unexpected PublicChatRoutingRepository method(s) called: {used}"
    )


def test_never_imports_knowledge_gap_write_services() -> None:
    """MB-08 must never call capture/classify/resolve/assess-handoff/
    merge/deletion -- those remain the Knowledge Gap Registry's own,
    separately admin-driven workflow. Proven by absence of the import,
    not just absence of a call site."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "KnowledgeGapCaptureService", "KnowledgeGapPriorityService",
        "KnowledgeGapHandoffAssessmentService", "KnowledgeGapResearchService",
        "KnowledgeGapResolutionService", "KnowledgeGapReviewService",
        "KnowledgeGapMergeService", "KnowledgeGapDeletionService",
        "KnowledgeGapCanonicalizationService", "KnowledgeGapClusteringService",
        "KnowledgeGapDailyReportService",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-08 must not import {name}"


def test_never_imports_training_release_or_runtime_services() -> None:
    """MB-08 is purely observational -- it never touches the Training
    Engine, Model Release governance, or MB-04 Runtime activation."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "PretrainingService", "ModelReleaseService", "MiniBrainInMemoryModelLoader",
        "MiniBrainLearningSupervisorService", "MiniBrainReleasePipelineService",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-08 must not import {name}"


def test_never_imports_dataset_service() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DatasetService" not in source


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


def test_admin_review_never_creates_another_phases_session() -> None:
    """Approving a report must only record the admin's decision -- it
    must never call into MB-06/MB-07 to actually start anything."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    admin_review_body = source.split("def admin_review(")[1].split("\n\n\n")[0]
    assert "create_session" not in admin_review_body
    assert "MiniBrainLearningSupervisorService" not in admin_review_body
    assert "MiniBrainReleasePipelineService" not in admin_review_body
