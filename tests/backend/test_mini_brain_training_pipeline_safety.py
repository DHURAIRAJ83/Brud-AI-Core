"""MB-18: structural safety proofs for MiniBrainTrainingPipelineService.

Static-analysis checks on the service source itself -- they prove "no
training job is ever started, no torch/transformers.Trainer/accelerate/
llama_cpp training API is ever called, no quantization/export/
deployment/runtime API is ever called, no Dataset Studio or Document
Workspace write method is ever called, no MB-13/14/16/17 write method
is ever called, only admin_review() can set an approved state, and
build_package() cannot call any training function" is enforced by what
code exists, not merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_training_pipeline_service.py"
)


def _module_ast() -> ast.Module:
    return ast.parse(SERVICE_PATH.read_text(encoding="utf-8"))


def _method_source(name: str) -> str:
    tree = _module_ast()
    lines = SERVICE_PATH.read_text(encoding="utf-8").splitlines()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return "\n".join(lines[node.lineno - 1 : node.end_lineno])
    raise AssertionError(f"method not found: {name}")


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


def test_only_calls_read_methods_on_multimodal_dataset() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.multimodal_dataset"}
    assert used == {"session", "list_records"}, f"unexpected MiniBrainMultimodalDatasetGeneratorService method(s) called: {used}"


def test_only_calls_read_methods_on_vision_rag() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.vision_rag"}
    assert used == {"session", "list_memory"}, f"unexpected MiniBrainVisionRagService method(s) called: {used}"


def test_only_calls_read_methods_on_language_intelligence() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.language_intelligence"}
    assert used == {"session"}, f"unexpected MiniBrainLanguageIntelligenceService method(s) called: {used}"


def test_only_calls_read_methods_on_vision_intelligence() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.vision_intelligence"}
    assert used == {"list_images"}, f"unexpected MiniBrainVisionIntelligenceService method(s) called: {used}"


def test_only_calls_read_methods_on_dataset_intelligence_and_advanced_dataset() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    di_used = {m for r, m in calls if r == "self.dataset_intelligence"}
    adv_used = {m for r, m in calls if r == "self.advanced_dataset"}
    assert di_used == {"training"}, f"unexpected MiniBrainDatasetIntelligenceService method(s) called: {di_used}"
    assert adv_used == {"report"}, f"unexpected MiniBrainAdvancedDatasetService method(s) called: {adv_used}"


def test_never_calls_a_dataset_studio_write_method() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    dataset_service_calls = {m for r, m in calls if r == "dataset_service" or r == "self.dataset_service"}
    forbidden = {"create_source", "update_source", "delete_source", "create_record", "update_record", "delete_record"}
    assert not (dataset_service_calls & forbidden), f"MB-18 must not call a Dataset Studio write method: {dataset_service_calls & forbidden}"


def test_never_calls_a_document_workspace_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DocumentService" not in source, "MB-18 must not import or compose DocumentService"


def test_never_calls_an_upstream_phase_write_method() -> None:
    """MB-18 must never write to MB-13/14/16/17's own tables -- proven
    by the absence of any of their qualified mutating method calls."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "self.multimodal_dataset.run_", "self.multimodal_dataset.admin_review(",
        "self.multimodal_dataset.delete_draft(", "self.multimodal_dataset.split_dataset(",
        "self.multimodal_dataset.merge_datasets(",
        "self.vision_rag.run_", "self.vision_rag.correct(", "self.vision_rag.admin_review(",
        "self.language_intelligence.run_", "self.language_intelligence.admin_review(",
        "self.vision_intelligence.run_", "self.vision_intelligence.annotate(",
        "self.vision_intelligence.admin_review(",
    ):
        assert forbidden not in source, f"MB-18 must not call upstream write method {forbidden}"


def test_never_imports_torch_training_apis() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("import torch", "torch.optim", "torch.nn", "torch.cuda", "backward()", "optimizer.step"):
        assert forbidden not in source, f"MB-18 must never call a torch training API ({forbidden} found)"


def test_never_imports_transformers_trainer() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in ("transformers.Trainer", "TrainingArguments", "from transformers import"):
        assert forbidden not in source, f"MB-18 must never use transformers.Trainer ({forbidden} found)"


def test_never_imports_accelerate() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    assert "accelerate" not in source, "MB-18 must never import accelerate"


def test_never_calls_llama_cpp_training_apis() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("llama_cpp", "llama.cpp", "finetune", "fine_tune", "lora_train"):
        assert forbidden not in source, f"MB-18 must never call a llama.cpp training API ({forbidden} found)"


def test_never_calls_quantization_or_export_apis() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("quantize(", "convert_to_gguf", ".gguf", "export_onnx", "torch.save", "state_dict"):
        assert forbidden not in source, f"MB-18 must never call a quantization/export API ({forbidden} found)"


def test_never_calls_deployment_or_runtime_apis() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "MiniBrainInMemoryModelLoader", "MiniBrainReleasePipelineService", "ModelReleaseService",
        "PretrainingService", "MiniBrainLearningSupervisorService", "RagSandboxRetrievalService",
        "RagRetrievalService",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-18 must not import {name}"


def test_never_activates_a_runtime_or_loads_a_model() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("load_model(", "activate_runtime", "llamacppbackend", "visioninferencebackend"):
        assert forbidden not in source, f"MB-18 must never activate a runtime or load a model ({forbidden} found)"


def test_never_imports_or_calls_an_external_ai_provider_client() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("anthropic", "openai", "google.generativeai", "genai.", "requests.post", "httpx.post", "urllib.request"):
        assert forbidden not in source, f"MB-18 must never call an external provider ({forbidden} found)"


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


def test_build_package_stage_cannot_call_any_training_function() -> None:
    body = _method_source("run_build_package_stage")
    for forbidden in (
        ".train(", ".fit(", "trainer.", "optimizer.", ".backward(", "quantize(", "deploy(",
        "activate_runtime", "load_model(",
    ):
        assert forbidden not in body, f"run_build_package_stage() must never call a training function ({forbidden})"


def test_admin_review_never_calls_another_phases_write_method() -> None:
    body = _method_source("admin_review")
    for forbidden in (
        "PretrainingService", "MiniBrainReleasePipelineService", "MiniBrainLearningSupervisorService",
        "create_job", "create_source", "create_record", "update_record", "run_generation", "run_evaluation",
        "quantize", "export", "deploy", "train(", "fit(",
    ):
        assert forbidden not in body, f"admin_review() must not reference {forbidden}"


def test_admin_review_is_the_only_method_that_sets_admin_decision() -> None:
    """Structural proof no method other than `admin_review()` writes
    `admin_decision` -- an approved/rejected/archived state is never
    set automatically."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "admin_review":
            body_lines = source.splitlines()[node.lineno - 1 : node.end_lineno]
            body = "\n".join(body_lines)
            assert '"admin_decision": decision' not in body, f"{node.name}() must not write admin_decision -- only admin_review() may"


def test_create_session_never_produces_model_weights() -> None:
    body = _method_source("create_session")
    for forbidden in (".gguf", "state_dict", "torch.save"):
        assert forbidden not in body


def test_optional_mb05_readiness_signals_are_wrapped_in_not_found_handling() -> None:
    """MB-05/MB-05.1 readiness signals are only ever attempted when an
    optional Dataset Studio source link happens to exist -- and must
    never hard-fail the stage when it doesn't."""
    body = _method_source("run_collect_datasets_stage")
    assert "NotFoundError" in body
    assert "except NotFoundError" in body
