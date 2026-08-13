"""MB-19: structural safety proofs for MiniBrainEvaluationCenterService.

Static-analysis checks on the service source itself -- they prove "no
training/fine-tuning/GGUF-export/quantization API is ever called, no
deployment or runtime API is ever called, no Dataset Studio or
Document Workspace write method is ever called, no MB-16/17/18 write
method is ever called, and only admin_review() can set an approved
state" is enforced by what code exists, not merely documented.
"""

import ast
import re
from pathlib import Path

SERVICE_PATH = (
    Path(__file__).resolve().parents[2]
    / "backend" / "services" / "mini_brain_evaluation_center_service.py"
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
    assert used == {"session", "list_evidence"}, f"unexpected MiniBrainVisionRagService method(s) called: {used}"


def test_only_calls_read_methods_on_training_pipeline() -> None:
    tree = _module_ast()
    calls = _attribute_calls(tree)
    used = {m for r, m in calls if r == "self.training_pipeline"}
    assert used == {"session", "list_packages"}, f"unexpected MiniBrainTrainingPipelineService method(s) called: {used}"


def test_never_calls_a_dataset_studio_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DatasetService" not in source, "MB-19 must not import or compose DatasetService"


def test_never_calls_a_document_workspace_write_method() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    assert "DocumentService" not in source, "MB-19 must not import or compose DocumentService"


def test_never_calls_an_upstream_phase_write_method() -> None:
    """MB-19 must never write to MB-16/17/18's own tables -- proven by
    the absence of any of their qualified mutating method calls."""
    source = SERVICE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "self.multimodal_dataset.run_", "self.multimodal_dataset.admin_review(",
        "self.multimodal_dataset.delete_draft(", "self.multimodal_dataset.split_dataset(",
        "self.multimodal_dataset.merge_datasets(",
        "self.vision_rag.run_", "self.vision_rag.correct(", "self.vision_rag.admin_review(",
        "self.training_pipeline.run_", "self.training_pipeline.admin_review(",
        "self.training_pipeline.create_session(",
    ):
        assert forbidden not in source, f"MB-19 must not call upstream write method {forbidden}"


def test_never_imports_training_apis() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("import torch", "torch.optim", "transformers.trainer", "trainingarguments", "accelerate"):
        assert forbidden not in source, f"MB-19 must never call a training API ({forbidden} found)"


def test_never_calls_fine_tuning_or_llama_cpp_training_apis() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("finetune", "fine_tune", "lora_train", "llama_cpp"):
        assert forbidden not in source, f"MB-19 must never fine-tune or train ({forbidden} found)"


def test_never_exports_gguf_or_quantizes() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("convert_to_gguf", ".gguf", "quantize(", "export_onnx", "torch.save", "state_dict"):
        assert forbidden not in source, f"MB-19 must never export or quantize a model ({forbidden} found)"


def test_never_deploys_or_activates_a_runtime() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8")
    forbidden_imports = (
        "MiniBrainInMemoryModelLoader", "MiniBrainReleasePipelineService", "ModelReleaseService",
        "PretrainingService", "MiniBrainLearningSupervisorService", "RagSandboxRetrievalService",
        "RagRetrievalService", "LlamaCppBackend",
    )
    for name in forbidden_imports:
        assert name not in source, f"MB-19 must not import {name}"


def test_never_calls_model_inference() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in (".generate(", ".predict(", "load_model(", "visioninferencebackend"):
        assert forbidden not in source, f"MB-19 must never run model inference ({forbidden} found)"


def test_never_downloads_models_or_calls_external_ai_providers() -> None:
    source = SERVICE_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("anthropic", "openai", "google.generativeai", "genai.", "requests.post", "httpx.post", "urllib.request", "huggingface_hub"):
        assert forbidden not in source, f"MB-19 must never call an external provider or download a model ({forbidden} found)"


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


def test_package_benchmarks_stage_never_writes_to_a_package_file() -> None:
    """The service reads real files from an MB-18 package directory to
    compute checksums -- it must never open one for writing."""
    body = _method_source("run_package_benchmarks_stage")
    for forbidden in ('"wb"', "'wb'", '"w"', "'w'", ".write_text(", ".write_bytes(", ".unlink(", "shutil."):
        assert forbidden not in body, f"run_package_benchmarks_stage() must never write to an MB-18 package file ({forbidden})"


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


def test_benchmark_modules_are_pure() -> None:
    """Every one of the 13 core_model/mini_brain/evaluation_center/
    modules must import no database, filesystem-write, or HTTP
    library -- proving they are pure, deterministic functions."""
    package_dir = (
        Path(__file__).resolve().parents[2] / "core_model" / "mini_brain" / "evaluation_center"
    )
    forbidden_imports = ("sqlite3", "fastapi", "requests", "httpx", "backend.database", "backend.api")
    for path in sorted(package_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        for forbidden in forbidden_imports:
            assert forbidden not in source, f"{path.name} must stay pure -- found forbidden import {forbidden}"


def test_benchmark_modules_never_open_a_file_for_writing() -> None:
    package_dir = (
        Path(__file__).resolve().parents[2] / "core_model" / "mini_brain" / "evaluation_center"
    )
    for path in sorted(package_dir.glob("*.py")):
        if path.name == "__init__.py":
            continue
        source = path.read_text(encoding="utf-8")
        for forbidden in ('open(', '.write_text(', '.write_bytes('):
            assert forbidden not in source, f"{path.name} must never write a file -- found {forbidden}"
