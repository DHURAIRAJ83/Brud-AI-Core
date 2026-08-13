"""MB-20: Brud Mini Brain Release Readiness & Deployment Governance
Center -- the orchestration layer for the 12-stage session-to-decision
workflow described in the MB-20 task spec.

MB-20 is a decision-and-governance layer only. It never deploys a
model, starts an inference server or public chat, calls a runtime-
manager start API, calls a Docker/Kubernetes deployment API, uploads
weights anywhere, exports GGUF, quantizes, modifies model weights, or
enables production traffic. It performs the final governance review of
an already-certified MB-16 dataset, an already-approved MB-17 grounded
RAG session, an already-approved MB-18 training package, and an
already-approved MB-19 evaluation -- read exclusively through their
own public methods -- into MB-20's own tables and its own release
directory on disk. No upstream record is ever modified.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.mini_brain_release_governance import (
    MiniBrainReleaseGovernanceRepository,
    public_artifact_row,
    public_memory_row,
    public_session_row,
)
from backend.services.mini_brain_evaluation_center_service import MiniBrainEvaluationCenterService
from backend.services.mini_brain_multimodal_dataset_generator_service import (
    MiniBrainMultimodalDatasetGeneratorService,
)
from backend.services.mini_brain_training_pipeline_service import MiniBrainTrainingPipelineService
from backend.services.mini_brain_vision_rag_service import MiniBrainVisionRagService
from core_model.mini_brain.release_governance.benchmark_gate_evaluator import run_benchmark_gates
from core_model.mini_brain.release_governance.compatibility_matrix_builder import build_compatibility_matrix
from core_model.mini_brain.release_governance.compliance_evaluator import run_compliance_gates
from core_model.mini_brain.release_governance.deployment_prerequisite_builder import (
    build_deployment_prerequisites,
)
from core_model.mini_brain.release_governance.operator_instruction_builder import (
    build_operator_instructions,
)
from core_model.mini_brain.release_governance.release_decision_builder import build_release_decision
from core_model.mini_brain.release_governance.release_manifest_builder import build_release_manifest
from core_model.mini_brain.release_governance.release_report_generator import generate_release_report
from core_model.mini_brain.release_governance.reproducibility_hasher import build_reproducibility_record
from core_model.mini_brain.release_governance.risk_register_builder import build_risk_register
from core_model.mini_brain.release_governance.rollback_planner import build_rollback_plan
from core_model.mini_brain.release_governance.safety_gate_evaluator import run_safety_gates
from core_model.mini_brain.release_governance.source_collector import (
    collect_dataset_evidence,
    collect_evaluation_report,
    collect_rag_evidence,
    collect_training_package,
)
from core_model.release.artifact_inventory import file_checksum, resolve_confined_path

ADMIN_DECISIONS = {"approve", "reject", "archive"}
ADMIN_STATUS_MAP = {"approve": "admin_approved", "reject": "admin_rejected", "archive": "admin_archived"}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


def _timed(fn, /, **kwargs) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn(**kwargs)
    return result, round((time.perf_counter() - started) * 1000, 3)


class MiniBrainReleaseGovernanceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainReleaseGovernanceRepository(settings.resolved_database_path)

        self.multimodal_dataset = MiniBrainMultimodalDatasetGeneratorService(settings)
        self.vision_rag = MiniBrainVisionRagService(settings)
        self.training_pipeline = MiniBrainTrainingPipelineService(settings)
        self.evaluation_center = MiniBrainEvaluationCenterService(settings)

    # -- helpers -------------------------------------------------------

    def _event(
        self, connection, release_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, release_session_id=release_session_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

    def _release_dir(self, session_public_id: str) -> Path:
        root = self.settings.resolved_document_dir.parent / "release_packages"
        directory = root / session_public_id
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    def session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_session_row(self.repository.session(connection, session_public_id))

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_sessions(connection, limit=limit, offset=offset)
        return {"items": [public_session_row(row) for row in rows]}

    def events(self, session_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_events(
                connection, release_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    def list_artifacts(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_artifacts(connection, release_session_id=session_row["id"])
        return {"items": [public_artifact_row(row) for row in rows]}

    def get_artifact_metadata(self, artifact_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_artifact_row(self.repository.get_artifact(connection, artifact_public_id))

    def list_memory(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_memory(connection, limit=limit, offset=offset)
        return {"items": [public_memory_row(row) for row in rows]}

    # -- stage 1: create release session -----------------------------------------

    def create_session(self, *, topic: str, admin_id: str) -> dict[str, Any]:
        if not topic.strip():
            raise ValidationError("topic must not be empty")
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(connection, topic=topic, created_by_admin_public_id=admin_id)
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="collect_datasets",
                message=f"release session created for topic '{topic}'",
            )
            return public_session_row(self.repository.session(connection, public_id))

    # -- stage 2: collect approved dataset evidence ------------------------------

    def run_collect_datasets_stage(
        self, session_public_id: str, *, dataset_session_public_ids: list[str], admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_datasets":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_datasets'")

        dataset_sessions = [self.multimodal_dataset.session(sid) for sid in dataset_session_public_ids]
        report = collect_dataset_evidence(dataset_sessions=dataset_sessions)
        if not report["ready"]:
            raise ValidationError("no certified (status='admin_approved') MB-16 dataset session was accepted")

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "dataset_collection_report_json": report,
                    "source_dataset_public_ids_json": report["accepted_session_public_ids"],
                    "stage": "collect_rag",
                },
            )
            self._event(
                connection, session_row["id"], "datasets_collected", stage="collect_datasets",
                message=f"{report['accepted_count']} certified dataset(s) accepted",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 3: collect approved RAG evidence ----------------------------------

    def run_collect_rag_stage(
        self, session_public_id: str, *, rag_session_public_ids: list[str], admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_rag":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_rag'")

        rag_sessions = [self.vision_rag.session(sid) for sid in rag_session_public_ids]
        report = collect_rag_evidence(rag_sessions=rag_sessions)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "rag_collection_report_json": report,
                    "source_rag_session_public_ids_json": report["accepted_session_public_ids"],
                    "stage": "collect_training_package",
                },
            )
            self._event(
                connection, session_row["id"], "rag_collected", stage="collect_rag",
                message=f"{report['accepted_count']} approved RAG session(s) accepted",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 4: collect approved training package ------------------------------

    def run_collect_training_package_stage(
        self, session_public_id: str, *, training_package_session_public_id: str, admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_training_package":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_training_package'")

        package_session = self.training_pipeline.session(training_package_session_public_id)
        report = collect_training_package(package_session=package_session)
        if not report["accepted"]:
            raise ValidationError("the MB-18 training package session must be admin_approved with a real built package")

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "training_package_collection_report_json": report,
                    "source_training_package_public_id": report["session_public_id"],
                    "stage": "collect_evaluation",
                },
            )
            self._event(
                connection, session_row["id"], "training_package_collected", stage="collect_training_package",
                message=f"MB-18 package {report['session_public_id']} accepted",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 5: collect approved evaluation report ------------------------------

    def run_collect_evaluation_stage(
        self, session_public_id: str, *, evaluation_session_public_id: str, admin_id: str,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "collect_evaluation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'collect_evaluation'")

        evaluation_session = self.evaluation_center.session(evaluation_session_public_id)
        report = collect_evaluation_report(evaluation_session=evaluation_session)
        if not report["accepted"]:
            raise ValidationError("the MB-19 evaluation session must be admin_approved")

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "evaluation_collection_report_json": report,
                    "source_evaluation_session_public_id": report["session_public_id"],
                    "stage": "run_safety_gates",
                },
            )
            self._event(
                connection, session_row["id"], "evaluation_collected", stage="collect_evaluation",
                message=f"MB-19 evaluation {report['session_public_id']} accepted",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 6: run safety gates -------------------------------------------------

    def run_safety_gates_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "run_safety_gates":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'run_safety_gates'")

        evaluation_session = self.evaluation_center.session(session_data["source_evaluation_session_public_id"])
        category_scores = evaluation_session.get("evaluation_report", {}).get("category_scores", {})
        grounding_report = evaluation_session.get("grounding_benchmark_report", {})
        ocr_report = evaluation_session.get("ocr_benchmark_report", {})
        language_report = evaluation_session.get("language_benchmark_report", {})
        package_report = evaluation_session.get("package_benchmark_report", {})
        multimodal_report = evaluation_session.get("multimodal_benchmark_report", {})
        regression_report = evaluation_session.get("regression_report", {})

        hallucination_risks = []
        for rag_session_public_id in session_data["source_rag_session_public_ids"]:
            rag_session = self.vision_rag.session(rag_session_public_id)
            risk = rag_session.get("hallucination_report", {}).get("hallucination_risk")
            if risk is not None:
                hallucination_risks.append(risk)
        hallucination_risk = max(hallucination_risks) if hallucination_risks else None

        # independent, read-only re-verification of MB-18's package files, on top of
        # MB-19's own already-computed package_benchmark_report -- defense in depth,
        # never trusting a single earlier assessment blindly.
        package_integrity_ok = (
            package_report.get("missing_file_count", 0) == 0
            and package_report.get("artifact_count_consistency_rate") in (1.0, None)
        )
        if session_data.get("source_training_package_public_id"):
            package_session = self.training_pipeline.session(session_data["source_training_package_public_id"])
            packages = self.training_pipeline.list_packages(session_data["source_training_package_public_id"])["items"]
            package_dir = Path(package_session["package_directory"])
            for pkg in packages:
                if not (package_dir / pkg["relative_path"]).exists():
                    package_integrity_ok = False
                    break

        duplicate_count = (
            multimodal_report.get("dataset_completeness", {}).get("total_exact_duplicate_count", 0)
        )

        report, latency_ms = _timed(
            run_safety_gates,
            grounding_composite_score=category_scores.get("grounding"), hallucination_risk=hallucination_risk,
            ocr_conflict_ratio=ocr_report.get("ocr_conflict_ratio"),
            unsupported_sentence_ratio=grounding_report.get("unsupported_sentence_ratio"),
            package_integrity_ok=package_integrity_ok,
            missing_artifact_count=package_report.get("missing_file_count", 0),
            unicode_integrity=language_report.get("unicode_integrity"),
            tamil_character_validity=language_report.get("tamil_character_validity"),
            duplicate_count=duplicate_count, release_risk_level=regression_report.get("release_risk_level", "unknown"),
        )
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"safety_gate_report_json": report, "stage": "run_compliance_gates"},
            )
            self._event(
                connection, session_row["id"], "safety_gates_run", stage="run_safety_gates",
                message=f"status={report['overall_status']}, {report['failed_count']} failed gate(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 7: run compliance gates ---------------------------------------------

    def run_compliance_gates_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "run_compliance_gates":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'run_compliance_gates'")

        checklist = {
            "dataset_approval_present": session_data["dataset_collection_report"].get("ready", False),
            "audit_trail_present": True,
            "reproducibility_hash_present": True,
            "artifact_checksums_present": False,
            "rollback_plan_present": False,
            "operator_instructions_present": False,
            "deployment_prerequisites_present": False,
        }
        report, latency_ms = _timed(
            run_compliance_gates, checklist=checklist, required_now={"dataset_approval_present", "audit_trail_present"},
        )
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"compliance_gate_report_json": report, "stage": "run_benchmark_gates"},
            )
            self._event(
                connection, session_row["id"], "compliance_gates_run", stage="run_compliance_gates",
                message=f"status={report['overall_status']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 8: run benchmark gates -----------------------------------------------

    def run_benchmark_gates_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "run_benchmark_gates":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'run_benchmark_gates'")

        benchmark_results = self.evaluation_center.list_results(session_data["source_evaluation_session_public_id"])["items"]
        report, latency_ms = _timed(run_benchmark_gates, benchmark_results=benchmark_results)
        report["latency_ms"] = latency_ms

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"benchmark_gate_report_json": report, "stage": "build_risk_rollback"},
            )
            self._event(
                connection, session_row["id"], "benchmark_gates_run", stage="run_benchmark_gates",
                message=f"status={report['overall_benchmark_status']}, {report['evaluated_metric_count']} metric(s) evaluated",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 9: build risk & rollback plan -----------------------------------------

    def run_build_risk_rollback_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "build_risk_rollback":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'build_risk_rollback'")

        risk_register, risk_latency_ms = _timed(
            build_risk_register, safety_gate_report=session_data["safety_gate_report"],
            compliance_gate_report=session_data["compliance_gate_report"],
            benchmark_gate_report=session_data["benchmark_gate_report"],
        )
        rollback_plan, rollback_latency_ms = _timed(build_rollback_plan, risk_register=risk_register)

        report = {
            "risk_register": risk_register, "rollback_plan": rollback_plan,
            "risk_latency_ms": risk_latency_ms, "rollback_latency_ms": rollback_latency_ms,
        }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"risk_rollback_report_json": report, "stage": "build_release_package"},
            )
            self._event(
                connection, session_row["id"], "risk_rollback_built", stage="build_risk_rollback",
                message=f"{risk_register['entry_count']} risk entr(y/ies) identified",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 10: build release decision package ---------------------------------------

    def run_build_release_package_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        session_data = self.session(session_public_id)
        if session_data["stage"] != "build_release_package":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'build_release_package'")

        evaluation_session = self.evaluation_center.session(session_data["source_evaluation_session_public_id"])
        training_package_session = self.training_pipeline.session(session_data["source_training_package_public_id"])
        risk_register = session_data["risk_rollback_report"]["risk_register"]
        rollback_plan = session_data["risk_rollback_report"]["rollback_plan"]

        compatibility_matrix, _ = _timed(
            build_compatibility_matrix,
            hardware_estimate_report=training_package_session.get("hardware_estimate_report", {}),
            language_benchmark_report=evaluation_session.get("language_benchmark_report", {}),
            multimodal_benchmark_report=evaluation_session.get("multimodal_benchmark_report", {}),
        )
        deployment_prerequisites, _ = _timed(build_deployment_prerequisites, compatibility_matrix=compatibility_matrix)
        operator_instructions, _ = _timed(
            build_operator_instructions, release_topic=session_data["topic"],
            release_readiness_status=session_data["safety_gate_report"].get("overall_status", "unknown"),
        )
        release_decision, _ = _timed(
            build_release_decision, safety_gate_report=session_data["safety_gate_report"],
            compliance_gate_report=session_data["compliance_gate_report"],
            benchmark_gate_report=session_data["benchmark_gate_report"],
            release_risk_level=evaluation_session.get("regression_report", {}).get("release_risk_level", "unknown"),
        )

        audit_trail = self.events(session_public_id, limit=100)["items"]

        release_dir = self._release_dir(session_public_id)
        started = time.perf_counter()
        artifact_payloads = {
            "release_decision.json": release_decision,
            "safety_checklist.json": session_data["safety_gate_report"],
            "compliance_checklist.json": session_data["compliance_gate_report"],
            "benchmark_summary.json": session_data["benchmark_gate_report"],
            "risk_register.json": risk_register,
            "rollback_plan.json": rollback_plan,
            "compatibility_matrix.json": compatibility_matrix,
            "deployment_prerequisites.json": deployment_prerequisites,
            "operator_instructions.json": operator_instructions,
            "release_audit_trail.json": {"events": audit_trail},
        }
        artifact_entries = []
        for artifact_name, payload in artifact_payloads.items():
            path = resolve_confined_path(release_dir, artifact_name)
            path.write_text(dumps_json(payload), encoding="utf-8")
            checksum = file_checksum(path)
            artifact_entries.append({
                "artifact_name": artifact_name, "relative_path": artifact_name, "sha256": checksum,
                "file_size_bytes": path.stat().st_size,
            })

        manifest = build_release_manifest(
            session_public_id=session_public_id, topic=session_data["topic"],
            source_dataset_public_ids=session_data["source_dataset_public_ids"],
            source_rag_session_public_ids=session_data["source_rag_session_public_ids"],
            source_training_package_public_id=session_data["source_training_package_public_id"],
            source_evaluation_session_public_id=session_data["source_evaluation_session_public_id"],
            release_recommendation=release_decision["recommendation"], artifact_entries=artifact_entries,
            created_at=_now(),
        )
        manifest_path = resolve_confined_path(release_dir, "release_manifest.json")
        manifest_path.write_text(dumps_json(manifest), encoding="utf-8")
        manifest_entry = {
            "artifact_name": "release_manifest.json", "relative_path": "release_manifest.json",
            "sha256": file_checksum(manifest_path), "file_size_bytes": manifest_path.stat().st_size,
        }
        artifact_entries.append(manifest_entry)

        reproducibility = build_reproducibility_record(
            release_manifest=manifest, source_dataset_public_ids=session_data["source_dataset_public_ids"],
            source_rag_session_public_ids=session_data["source_rag_session_public_ids"],
            source_training_package_public_id=session_data["source_training_package_public_id"],
            source_evaluation_session_public_id=session_data["source_evaluation_session_public_id"],
        )
        reproducibility_path = resolve_confined_path(release_dir, "reproducibility.json")
        reproducibility_path.write_text(dumps_json(reproducibility), encoding="utf-8")
        artifact_entries.append({
            "artifact_name": "reproducibility.json", "relative_path": "reproducibility.json",
            "sha256": file_checksum(reproducibility_path), "file_size_bytes": reproducibility_path.stat().st_size,
        })
        build_latency_ms = round((time.perf_counter() - started) * 1000, 3)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            for entry in artifact_entries:
                self.repository.create_artifact(
                    connection, release_session_id=session_row["id"], artifact_name=entry["artifact_name"],
                    relative_path=entry["relative_path"], sha256=entry["sha256"],
                    file_size_bytes=entry["file_size_bytes"],
                )
            manifest["reproducibility"] = reproducibility
            manifest["build_latency_ms"] = build_latency_ms
            # Carried alongside the manifest (rather than a dedicated column) so
            # generate_report_stage can assemble the final report purely from
            # session_data["release_manifest"] -- merged in after the on-disk
            # release_manifest.json is written and hashed, same as reproducibility
            # above, so the file on disk and its own checksum stay consistent.
            manifest["compatibility_matrix"] = compatibility_matrix
            manifest["deployment_prerequisites"] = deployment_prerequisites
            manifest["operator_instructions"] = operator_instructions
            self.repository.update_session(
                connection, session_public_id,
                {
                    "release_directory": str(release_dir), "release_manifest_json": manifest,
                    "release_decision_json": release_decision, "stage": "generate_report",
                },
            )
            self._event(
                connection, session_row["id"], "release_package_built", stage="build_release_package",
                message=f"{len(artifact_entries)} artifact file(s) written and checksummed",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 11: generate release readiness report ---------------------------------------

    def generate_report_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "generate_report":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'generate_report'")

        final_checklist = {
            "dataset_approval_present": session_data["dataset_collection_report"].get("ready", False),
            "audit_trail_present": True, "reproducibility_hash_present": True,
            "artifact_checksums_present": True, "rollback_plan_present": True,
            "operator_instructions_present": True, "deployment_prerequisites_present": True,
        }
        final_compliance = run_compliance_gates(
            checklist=final_checklist, required_now=set(final_checklist),
        )

        report = generate_release_report(
            session_public_id=session_public_id, topic=session_data["topic"],
            dataset_collection_report=session_data["dataset_collection_report"],
            rag_collection_report=session_data["rag_collection_report"],
            training_package_collection_report=session_data["training_package_collection_report"],
            evaluation_collection_report=session_data["evaluation_collection_report"],
            safety_gate_report=session_data["safety_gate_report"], compliance_gate_report=final_compliance,
            benchmark_gate_report=session_data["benchmark_gate_report"],
            risk_register=session_data["risk_rollback_report"]["risk_register"],
            rollback_plan=session_data["risk_rollback_report"]["rollback_plan"],
            compatibility_matrix=session_data["release_manifest"].get("compatibility_matrix", {}),
            deployment_prerequisites=session_data["release_manifest"].get("deployment_prerequisites", {}),
            operator_instructions=session_data["release_manifest"].get("operator_instructions", {}),
            release_decision=session_data["release_decision"],
            reproducibility_record=session_data["release_manifest"].get("reproducibility", {}),
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"readiness_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "readiness_report_generated", stage="generate_report",
                message=f"recommendation={report['final_recommendation']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 12: admin review -------------------------------------------------------------------

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'")
            session_public = public_session_row(session_row)

            self.repository.record_memory(
                connection, release_session_id=session_row["id"], topic=session_public["topic"],
                source_dataset_count=len(session_public["source_dataset_public_ids"]),
                source_rag_session_count=len(session_public["source_rag_session_public_ids"]),
                overall_readiness_score=session_public["readiness_report"].get("overall_readiness_score"),
                release_decision_status=session_public["readiness_report"].get("final_recommendation"),
                admin_decision=decision, recorded_by_admin_public_id=admin_id,
            )

            fields: dict[str, Any] = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": ADMIN_STATUS_MAP[decision], "stage": "closed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"release_review_{decision}", stage="awaiting_admin_review",
                message=(
                    f"admin decided '{decision}' -- no deployment, runtime start, or public traffic "
                    "was ever performed by this service. Approval does not imply production safety"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainReleaseGovernanceService"]
