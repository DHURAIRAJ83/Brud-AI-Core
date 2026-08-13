"""Phase 15 controlled local inference runtime orchestration.

Composes the existing release registry (Phase 14), checkpoint verifier,
tokenizer registry, core-model loader, and Phase 12's bounded generation
loop — this module never trains, never duplicates a registry, and never
assigns anything to the public chatbot. Loading a model into the runtime
is not the same as assigning it to a scope, which is not the same as
public-chat activation; those stay in `model_assignment_service.py`.
"""

from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.inference_runtime import (
    InferenceRuntimeRepository,
    public_row,
)
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.models.inference_runtime import RuntimeProfileCreate, RuntimeProfilePatch
from backend.services.tokenizer_registry import TokenizerService
from core_model.architecture.config import BrudModelConfig
from core_model.inference_runtime import HEALTH_CHECK_TYPES, REGISTRY_FIXTURE_MARKERS
from core_model.inference_runtime.model_loader import (
    assess_runtime_compatibility,
    missing_special_tokens,
    verify_vocabulary_compatibility,
)
from core_model.inference_runtime.resource_guard import (
    ResourceAssessment,
    assess_resource_guard,
    estimate_peak_inference_bytes,
    estimate_static_model_bytes,
)
from core_model.inference_runtime.runtime_config import validate_runtime_profile
from core_model.inference_runtime.runtime_health import aggregate_health_status
from core_model.release.manifest import verify_manifest_checksum

# In-process loaded-model registry, keyed by (database path, runtime instance
# public id) — never by instance id alone, so two distinct databases (e.g.
# two isolated test runs, or a scratch-verification DB and the real one) in
# the same process never share loaded-model state. A real multi-process
# deployment would need a process-local guarantee too; Phase 15 targets a
# single bounded local process, so a module-level dict is the runtime's
# one-model-at-a-time slot for a given database.
_LOADED_MODELS: dict[tuple[str, str], dict[str, Any]] = {}


def _read_available_memory_bytes() -> tuple[int, str]:
    """Returns (bytes, label). Falls back to an unmeasurable-but-safe zero
    (never a fabricated 'measured' figure) when /proc/meminfo is unavailable."""

    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        for line in meminfo.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                kib = int(line.split()[1])
                return kib * 1024, "measured"
    return 0, "estimated"


class InferenceRuntimeService:
    def __init__(
        self,
        repository: InferenceRuntimeRepository,
        release_repository: ModelReleaseRepository,
        settings: Settings,
    ) -> None:
        self.repository = repository
        self.release_repository = release_repository
        self.settings = settings

    def _loaded_key(self, instance_public_id: str) -> tuple[str, str]:
        return (str(self.repository.database_path), instance_public_id)

    # --- runtime profiles -----------------------------------------------------

    def create_profile(self, payload: RuntimeProfileCreate, admin_id: str) -> dict[str, Any]:
        errors = validate_runtime_profile(
            runtime_type=payload.runtime_type,
            dtype=payload.dtype,
            maximum_loaded_models=payload.maximum_loaded_models,
            maximum_concurrent_requests=payload.maximum_concurrent_requests,
            maximum_context_length=payload.maximum_context_length,
            maximum_new_tokens=payload.maximum_new_tokens,
            request_timeout_seconds=payload.request_timeout_seconds,
            idle_unload_seconds=payload.idle_unload_seconds,
            minimum_available_memory_bytes=payload.minimum_available_memory_bytes,
            minimum_available_disk_bytes=payload.minimum_available_disk_bytes,
        )
        if errors:
            raise ValidationError("; ".join(errors))
        with self.repository.transaction() as connection:
            public_id = self.repository.create_profile(
                connection,
                {
                    "name": payload.name,
                    "runtime_type": payload.runtime_type,
                    "device": payload.device,
                    "dtype": payload.dtype,
                    "maximum_loaded_models": payload.maximum_loaded_models,
                    "maximum_concurrent_requests": payload.maximum_concurrent_requests,
                    "maximum_context_length": payload.maximum_context_length,
                    "maximum_new_tokens": payload.maximum_new_tokens,
                    "request_timeout_seconds": payload.request_timeout_seconds,
                    "idle_unload_seconds": payload.idle_unload_seconds,
                    "minimum_available_memory_bytes": payload.minimum_available_memory_bytes,
                    "minimum_available_disk_bytes": payload.minimum_available_disk_bytes,
                    "resource_policy_json": dumps_json(payload.resource_policy),
                    "generation_defaults_json": dumps_json(payload.generation_defaults),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "inference_runtime_profile_created", admin_id, public_id)
            return public_row(self.repository.profile(connection, public_id))

    def list_profiles(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_profiles(connection)]}

    def get_profile(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.profile(connection, public_id))

    def patch_profile(
        self, public_id: str, payload: RuntimeProfilePatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profile = self.repository.profile(connection, public_id)
            fields: dict[str, Any] = {}
            if payload.enabled is not None:
                fields["enabled"] = 1 if payload.enabled else 0
            for name in (
                "maximum_new_tokens",
                "maximum_context_length",
                "request_timeout_seconds",
                "idle_unload_seconds",
                "minimum_available_memory_bytes",
                "minimum_available_disk_bytes",
            ):
                value = getattr(payload, name)
                if value is not None:
                    fields[name] = value
            if payload.resource_policy is not None:
                fields["resource_policy_json"] = dumps_json(payload.resource_policy)
            if payload.generation_defaults is not None:
                fields["generation_defaults_json"] = dumps_json(payload.generation_defaults)
            new_max_new_tokens = fields.get("maximum_new_tokens", profile["maximum_new_tokens"])
            new_max_context = fields.get(
                "maximum_context_length", profile["maximum_context_length"]
            )
            if new_max_new_tokens > new_max_context:
                raise ValidationError("maximum_new_tokens must not exceed maximum_context_length")
            self.repository.update_profile(connection, profile["id"], fields)
            self._audit(connection, "inference_runtime_profile_updated", admin_id, public_id)
            return public_row(self.repository.profile(connection, public_id))

    # --- runtime instances -----------------------------------------------------

    def create_instance(self, profile_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            profile = self.repository.profile(connection, profile_public_id)
            public_id = self.repository.create_instance(connection, profile["id"], {})
            self._audit(connection, "inference_runtime_instance_created", admin_id, public_id)
            return public_row(self.repository.instance(connection, public_id))

    def list_instances(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_instances(connection)
            return {"items": [public_row(row) for row in rows]}

    def get_instance(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.instance(connection, public_id))

    def start_instance(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            instance = self.repository.instance(connection, public_id)
            if instance["status"] not in {"offline", "stopped"}:
                raise ValidationError("instance must be offline or stopped to start")
            self.repository.update_instance(connection, instance["id"], {"status": "idle"})
            self._audit(connection, "inference_runtime_instance_started", admin_id, public_id)
            return public_row(self.repository.instance(connection, public_id))

    def stop_instance(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            instance = self.repository.instance(connection, public_id)
            _LOADED_MODELS.pop(self._loaded_key(public_id), None)
            self.repository.update_instance(
                connection,
                instance["id"],
                {
                    "status": "stopped",
                    "loaded_release_public_id": None,
                    "loaded_checkpoint_public_id": None,
                    "loaded_tokenizer_public_id": None,
                },
            )
            self._audit(connection, "inference_runtime_instance_stopped", admin_id, public_id)
            return public_row(self.repository.instance(connection, public_id))

    # --- release facts (shared by compatibility assessment and loading) -----

    def _model_config(self, connection, core_model_config_id: int) -> BrudModelConfig:
        row = connection.execute(
            "SELECT * FROM core_model_configs WHERE id=?", (core_model_config_id,)
        ).fetchone()
        return BrudModelConfig(
            vocabulary_size=row["vocabulary_size"],
            context_length=row["context_length"],
            hidden_size=row["hidden_size"],
            intermediate_size=row["intermediate_size"],
            num_hidden_layers=row["num_hidden_layers"],
            num_attention_heads=row["num_attention_heads"],
            num_key_value_heads=row["num_key_value_heads"],
            pad_token_id=row["pad_token_id"],
            bos_token_id=row["bos_token_id"],
            eos_token_id=row["eos_token_id"],
            unk_token_id=row["unk_token_id"],
        )

    def _is_registry_fixture(self, candidate, model_card_row, manifest_row) -> bool:
        haystacks = [
            candidate["label"] or "",
            candidate["notes"] or "",
            model_card_row["card_markdown"] if model_card_row else "",
            manifest_row["manifest_json"] if manifest_row else "",
        ]
        combined = " ".join(haystacks)
        return any(marker in combined for marker in REGISTRY_FIXTURE_MARKERS)

    def gather_release_facts(self, connection, release_public_id: str) -> dict[str, Any]:
        release = self.release_repository.release(connection, release_public_id)
        candidate = self.release_repository.candidate(
            connection, release["model_release_candidate_public_id"]
        )
        artifacts = self.release_repository.artifacts_for_candidate(connection, candidate["id"])
        by_type = {row["artifact_type"]: dict(row) for row in artifacts}
        manifest_row = self.release_repository.latest_manifest(connection, candidate["id"])
        model_card_row = self.release_repository.latest_model_card(connection, candidate["id"])
        issues = connection.execute(
            "SELECT * FROM model_release_issues WHERE model_release_candidate_id=?",
            (candidate["id"],),
        ).fetchall()
        has_blocking_release_issue = any(row["severity"] == "blocking" for row in issues)

        manifest_verified = bool(
            manifest_row
            and release["release_manifest_public_id"] == manifest_row["public_id"]
            and verify_manifest_checksum(
                manifest_row["manifest_json"], manifest_row["manifest_checksum_sha256"]
            )
        )
        required_verified = {
            "model_checkpoint",
            "model_config",
            "tokenizer_model",
            "tokenizer_vocab",
        }
        artifacts_verified = all(
            by_type.get(artifact_type, {}).get("verification_status") == "verified"
            for artifact_type in required_verified
        )
        checkpoint_structurally_present = (
            by_type.get("model_checkpoint", {}).get("verification_status") == "verified"
        )
        tokenizer_verified = (
            by_type.get("tokenizer_model", {}).get("verification_status") == "verified"
            and by_type.get("tokenizer_vocab", {}).get("verification_status") == "verified"
        )
        model_config_row = connection.execute(
            "SELECT vocabulary_size FROM core_model_configs WHERE id=?",
            (candidate["core_model_config_id"],),
        ).fetchone()
        model_config_matches = bool(model_config_row) and verify_vocabulary_compatibility(
            model_config_row["vocabulary_size"], candidate["tokenizer_vocabulary_size"]
        )

        evaluation_status = "not_assessed"
        if candidate["model_evaluation_run_public_id"]:
            readiness_row = connection.execute(
                """SELECT status FROM model_chat_readiness_assessments
                WHERE model_evaluation_run_id=(
                    SELECT id FROM model_evaluation_runs WHERE public_id=?
                ) ORDER BY created_at DESC LIMIT 1""",
                (candidate["model_evaluation_run_public_id"],),
            ).fetchone()
            if readiness_row:
                evaluation_status = readiness_row["status"]

        is_registry_fixture = self._is_registry_fixture(candidate, model_card_row, manifest_row)

        return {
            "release": release,
            "candidate": candidate,
            "artifacts_by_type": by_type,
            "manifest_verified": manifest_verified,
            "artifacts_verified": artifacts_verified,
            "checkpoint_structurally_present": checkpoint_structurally_present,
            "tokenizer_verified": tokenizer_verified,
            "model_config_matches": model_config_matches,
            "evaluation_status": evaluation_status,
            "has_blocking_release_issue": has_blocking_release_issue,
            "is_registry_fixture": is_registry_fixture,
        }

    # --- compatibility assessment -----------------------------------------------------

    def assess_compatibility(
        self, release_public_id: str, profile_public_id: str, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            facts = self.gather_release_facts(connection, release_public_id)
            profile = self.repository.profile(connection, profile_public_id)
            candidate = facts["candidate"]
            tokenizer_special_tokens = loads_json(candidate["tokenizer_special_tokens_json"])
            required_special_tokens = ("<bos>", "<eos>", "<system>", "<user>", "<assistant>")
            missing_tokens = missing_special_tokens(
                required_special_tokens, tokenizer_special_tokens
            )
            available_memory_bytes, _ = _read_available_memory_bytes()
            available_disk_bytes = shutil.disk_usage(
                self.settings.resolved_pretraining_dir
            ).free

            result = assess_runtime_compatibility(
                release_manifest_verified=facts["manifest_verified"],
                checkpoint_verified=facts["checkpoint_structurally_present"],
                tokenizer_verified=facts["tokenizer_verified"],
                vocabulary_compatible=not missing_tokens,
                special_tokens_missing=missing_tokens,
                model_config_matches=facts["model_config_matches"],
                requested_context_length=profile["maximum_context_length"],
                maximum_context_length=profile["maximum_context_length"],
                dtype=profile["dtype"],
                supported_dtypes=("float32",),
                device=profile["device"],
                supported_devices=("cpu",),
                memory_compatible=available_memory_bytes
                >= profile["minimum_available_memory_bytes"],
                disk_compatible=available_disk_bytes >= profile["minimum_available_disk_bytes"],
                generation_policy_compatible=True,
                evaluation_status=facts["evaluation_status"],
                scope="admin_diagnostic",
            )
            checksum = hashlib.sha256(dumps_json(result).encode("utf-8")).hexdigest()
            self.repository.record_compatibility(
                connection,
                {
                    "model_release_id": facts["release"]["id"],
                    "inference_runtime_profile_id": profile["id"],
                    "status": result["status"],
                    "dimension_scores_json": dumps_json(result["dimension_scores"]),
                    "blocking_issue_count": result["blocking_issue_count"],
                    "warning_issue_count": result["warning_issue_count"],
                    "rationale_json": dumps_json(
                        {"missing_special_tokens": missing_tokens}
                    ),
                    "compatibility_checksum_sha256": checksum,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection, "inference_compatibility_assessed", admin_id, release_public_id,
                status=result["status"],
            )
            row = self.repository.latest_compatibility(
                connection, facts["release"]["id"], profile["id"]
            )
            return public_row(row)

    def get_compatibility(self, release_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            release = self.release_repository.release(connection, release_public_id)
            row = connection.execute(
                """SELECT * FROM inference_model_compatibility_assessments
                WHERE model_release_id=? ORDER BY id DESC LIMIT 1""",
                (release["id"],),
            ).fetchone()
            if not row:
                raise NotFoundError("no compatibility assessment recorded for this release")
            return public_row(row)

    # --- resource guard + model load/unload -----------------------------------------------------

    def _resolve_processor(self, connection, tokenizer_version_public_id: str):
        return TokenizerService(
            TokenizerRepository(self.repository.database_path), self.settings
        ).processor_for_version(tokenizer_version_public_id)

    def load_instance(
        self, instance_public_id: str, release_public_id: str, admin_id: str
    ) -> dict[str, Any]:
        """Public entrypoint: opens its own transaction. Composing services
        that already hold an open connection (e.g. `ModelAssignmentService`,
        which may have just created the instance row in the same
        transaction) must call `load_instance_using_connection` directly
        instead — a second connection cannot see this one's uncommitted
        writes."""

        with self.repository.transaction() as connection:
            return self.load_instance_using_connection(
                connection, instance_public_id, release_public_id, admin_id
            )

    def load_instance_using_connection(
        self, connection, instance_public_id: str, release_public_id: str, admin_id: str
    ) -> dict[str, Any]:
        from core_model.architecture.model import BrudForCausalLM, count_parameters
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager

        instance = self.repository.instance(connection, instance_public_id)
        facts = self.gather_release_facts(connection, release_public_id)
        release = facts["release"]
        candidate = facts["candidate"]

        if release["status"] != "released":
            return self._fail_load(connection, instance, "release_not_eligible")
        if release["deployment_eligibility"] not in {"deployable", "deployable_with_warnings"}:
            return self._fail_load(connection, instance, "release_not_eligible")
        if facts["evaluation_status"] == "evaluation_blocked":
            return self._fail_load(connection, instance, "release_not_eligible")
        if not facts["manifest_verified"]:
            return self._fail_load(connection, instance, "manifest_mismatch")
        if not facts["artifacts_verified"]:
            return self._fail_load(connection, instance, "artifact_verification_failed")

        model_config = self._model_config(connection, candidate["core_model_config_id"])
        checkpoint_dir = (
            self.settings.resolved_pretraining_dir / candidate["checkpoint_safe_name"]
        )
        manager = TrainingCheckpointManager(
            self.settings.resolved_pretraining_dir, self.settings.core_checkpoint_max_bytes
        )
        model = BrudForCausalLM(model_config)
        try:
            states = manager.load_states(checkpoint_dir)
            model.load_state_dict(states["model"])
            checkpoint_verified = True
        except (OSError, ValueError, RuntimeError):
            checkpoint_verified = False
        if not checkpoint_verified:
            return self._fail_load(connection, instance, "checkpoint_corrupt")

        try:
            processor = self._resolve_processor(
                connection, candidate["tokenizer_version_public_id"]
            )
        except (ValidationError, NotFoundError, OSError):
            return self._fail_load(connection, instance, "tokenizer_invalid")

        if not verify_vocabulary_compatibility(
            model_config.vocabulary_size, candidate["tokenizer_vocabulary_size"]
        ):
            return self._fail_load(connection, instance, "vocabulary_mismatch")

        tokenizer_special_tokens = loads_json(candidate["tokenizer_special_tokens_json"])
        missing_tokens = missing_special_tokens(
            ("<bos>", "<eos>", "<system>", "<user>", "<assistant>"), tokenizer_special_tokens
        )
        if missing_tokens:
            return self._fail_load(connection, instance, "special_token_mismatch")

        parameter_count = count_parameters(model)
        static_bytes = estimate_static_model_bytes(parameter_count)
        peak_bytes = estimate_peak_inference_bytes(
            static_model_bytes=static_bytes,
            context_length=instance["profile_maximum_context_length"],
            hidden_size=model_config.hidden_size,
            num_hidden_layers=model_config.num_hidden_layers,
            generation_length=instance["profile_maximum_new_tokens"],
        )
        available_memory_bytes, memory_label = _read_available_memory_bytes()
        available_disk_bytes = shutil.disk_usage(
            self.settings.resolved_pretraining_dir
        ).free
        checkpoint_size_bytes = (
            sum(f.stat().st_size for f in checkpoint_dir.rglob("*") if f.is_file())
            if checkpoint_dir.is_dir()
            else 0
        )
        guard: ResourceAssessment = assess_resource_guard(
            available_memory_bytes=available_memory_bytes,
            available_disk_bytes=available_disk_bytes,
            estimated_peak_inference_bytes=peak_bytes,
            minimum_available_memory_bytes=instance["profile_minimum_available_memory_bytes"],
            minimum_available_disk_bytes=instance["profile_minimum_available_disk_bytes"],
            checkpoint_size_bytes=checkpoint_size_bytes,
            tokenizer_size_bytes=0,
            requested_context_length=instance["profile_maximum_context_length"],
            maximum_context_length=instance["profile_maximum_context_length"],
            requested_generation_limit=instance["profile_maximum_new_tokens"],
            maximum_new_tokens=instance["profile_maximum_new_tokens"],
            maximum_loaded_models=instance["profile_maximum_loaded_models"],
            # Count models loaded on OTHER instances in THIS database only — this
            # instance's own existing model (if any) is being replaced, not added
            # to, and a different database's loaded models are not this runtime's
            # concern at all.
            currently_loaded_model_count=sum(
                1
                for key in _LOADED_MODELS
                if key[0] == str(self.repository.database_path)
                and key != self._loaded_key(instance_public_id)
            ),
            maximum_concurrent_requests=instance["profile_maximum_concurrent_requests"],
            currently_active_request_count=0,
            measurement_label=memory_label,
        )
        if guard.verdict != "pass":
            return self._fail_load(
                connection, instance, "memory_guard_failed", details={"reasons": guard.reasons}
            )

        forbidden_ids = {
            processor.piece_to_id(token)
            for token in ("<system>", "<user>", "<assistant>")
            if processor.piece_to_id(token) >= 0
        }
        _LOADED_MODELS[self._loaded_key(instance_public_id)] = {
            "model": model,
            "processor": processor,
            "config": model_config,
            "release_public_id": release_public_id,
            "candidate_public_id": candidate["public_id"],
            "forbidden_role_token_ids": frozenset(forbidden_ids),
            "parameter_count": parameter_count,
            "estimated_peak_bytes": peak_bytes,
            "measurement_label": memory_label,
            "available_memory_at_load_bytes": available_memory_bytes,
        }
        self.repository.update_instance(
            connection,
            instance["id"],
            {
                "status": "ready",
                "loaded_release_public_id": release_public_id,
                "loaded_checkpoint_public_id": candidate["checkpoint_public_id"],
                "loaded_tokenizer_public_id": candidate["tokenizer_version_public_id"],
                "memory_snapshot_json": dumps_json(
                    {
                        "estimated_peak_inference_bytes": peak_bytes,
                        "available_memory_bytes": available_memory_bytes,
                        "measurement_label": memory_label,
                    }
                ),
            },
        )
        connection.execute(
            "UPDATE inference_runtime_instances SET loaded_at=CURRENT_TIMESTAMP WHERE id=?",
            (instance["id"],),
        )
        self._audit(
            connection, "inference_model_loaded", admin_id, instance_public_id,
            release_public_id=release_public_id, parameter_count=parameter_count,
        )
        return public_row(self.repository.instance(connection, instance_public_id))

    def _fail_load(
        self, connection, instance, failure_code: str, *, details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        _LOADED_MODELS.pop(self._loaded_key(instance["public_id"]), None)
        self.repository.update_instance(
            connection,
            instance["id"],
            {"status": "failed", "failure_code": failure_code, "failure_summary": failure_code},
        )
        self.repository.record_failure(
            connection,
            {
                "inference_runtime_instance_id": instance["id"],
                "failure_code": failure_code,
                "failure_summary": f"model load failed: {failure_code}",
                "details_json": dumps_json(details or {}),
            },
        )
        raise ValidationError(f"model load failed: {failure_code}")

    def unload_instance(self, instance_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            instance = self.repository.instance(connection, instance_public_id)
            _LOADED_MODELS.pop(self._loaded_key(instance_public_id), None)
            self.repository.update_instance(
                connection,
                instance["id"],
                {
                    "status": "idle",
                    "loaded_release_public_id": None,
                    "loaded_checkpoint_public_id": None,
                    "loaded_tokenizer_public_id": None,
                    "memory_snapshot_json": "{}",
                },
            )
            self._audit(connection, "inference_model_unloaded", admin_id, instance_public_id)
            return public_row(self.repository.instance(connection, instance_public_id))

    # --- health checks -----------------------------------------------------

    def run_health_check(self, instance_public_id: str, admin_id: str) -> dict[str, Any]:
        from core_model.checkpoints.training_checkpoint import TrainingCheckpointManager
        from core_model.inference_runtime.generation_engine import run_bounded_generation

        with self.repository.transaction() as connection:
            instance = self.repository.instance(connection, instance_public_id)
            loaded = _LOADED_MODELS.get(self._loaded_key(instance_public_id))
            results: dict[str, str] = {}
            results["runtime_process"] = "healthy"
            results["model_loaded"] = "healthy" if loaded else "unhealthy"
            results["tokenizer_loaded"] = "healthy" if loaded else "unhealthy"

            checkpoint_ok = False
            if loaded:
                candidate_public_id = loaded["candidate_public_id"]
                candidate = self.release_repository.candidate(connection, candidate_public_id)
                checkpoint_dir = (
                    self.settings.resolved_pretraining_dir / candidate["checkpoint_safe_name"]
                )
                manager = TrainingCheckpointManager(
                    self.settings.resolved_pretraining_dir,
                    self.settings.core_checkpoint_max_bytes,
                )
                try:
                    checkpoint_ok = manager.verify(checkpoint_dir)
                except (OSError, ValueError):
                    checkpoint_ok = False
            results["checkpoint_verified"] = "healthy" if checkpoint_ok else "unhealthy"

            available_memory_bytes, _ = _read_available_memory_bytes()
            memory_ok = (
                loaded is not None
                and available_memory_bytes
                >= instance["profile_minimum_available_memory_bytes"]
            )
            results["memory_available"] = "healthy" if memory_ok else "unhealthy"

            smoke_ok = False
            latency_ok = False
            special_token_safe = False
            if loaded:
                started = time.perf_counter()
                smoke = run_bounded_generation(
                    loaded["model"],
                    loaded["processor"],
                    [loaded["config"].bos_token_id],
                    max_new_tokens=4,
                    min_new_tokens=0,
                    eos_token_id=loaded["config"].eos_token_id,
                    forbidden_role_token_ids=loaded["forbidden_role_token_ids"],
                    sequence_length=loaded["config"].context_length,
                    vocabulary_size=loaded["config"].vocabulary_size,
                    timeout_seconds=instance["profile_request_timeout_seconds"],
                )
                elapsed_ms = (time.perf_counter() - started) * 1000
                smoke_ok = smoke["stop_reason"] != "invalid_token"
                latency_ok = elapsed_ms <= instance["profile_request_timeout_seconds"] * 1000
                special_token_safe = smoke["stop_reason"] != "role_token_leakage"
            results["generation_smoke_test"] = "healthy" if smoke_ok else "unhealthy"
            results["latency_within_limit"] = "healthy" if latency_ok else "degraded"
            results["special_token_output_safe"] = "healthy" if special_token_safe else "unhealthy"

            for check_type in HEALTH_CHECK_TYPES:
                self.repository.record_health_check(
                    connection,
                    instance["id"],
                    {"check_type": check_type, "status": results[check_type]},
                )
            overall = aggregate_health_status(results)
            if loaded:
                new_status = "ready" if overall == "healthy" else "degraded"
            else:
                new_status = instance["status"]
            self.repository.update_instance(connection, instance["id"], {"status": new_status})
            connection.execute(
                "UPDATE inference_runtime_instances SET last_health_at=CURRENT_TIMESTAMP "
                "WHERE id=?",
                (instance["id"],),
            )
            self._audit(
                connection, "inference_health_check_run", admin_id, instance_public_id,
                overall=overall,
            )
            return {
                "overall_status": overall,
                "checks": results,
                "instance": public_row(self.repository.instance(connection, instance_public_id)),
            }

    # --- generation primitive (shared by diagnostics/chat-lab/canary) --------

    def run_generation(
        self,
        instance_public_id: str,
        *,
        prompt_text: str,
        maximum_new_tokens: int,
        minimum_new_tokens: int = 0,
        timeout_seconds: float,
        decoding_mode: str = "greedy",
        top_k: int | None = None,
        temperature: float | None = None,
        seed: int | None = None,
        system_text: str = "",
    ) -> dict[str, Any]:
        from core_model.inference_runtime.generation_engine import (
            no_role_token_leakage,
            no_system_prompt_leakage,
            run_bounded_generation,
            valid_unicode,
        )

        loaded = _LOADED_MODELS.get(self._loaded_key(instance_public_id))
        if not loaded:
            raise ValidationError("runtime instance has no loaded model")
        processor = loaded["processor"]
        config = loaded["config"]
        prompt_ids = processor.encode(prompt_text, out_type=int)
        started = time.perf_counter()
        result = run_bounded_generation(
            loaded["model"],
            processor,
            prompt_ids,
            max_new_tokens=maximum_new_tokens,
            min_new_tokens=minimum_new_tokens,
            eos_token_id=config.eos_token_id,
            forbidden_role_token_ids=loaded["forbidden_role_token_ids"],
            sequence_length=config.context_length,
            vocabulary_size=config.vocabulary_size,
            timeout_seconds=timeout_seconds,
            decoding_mode=decoding_mode,
            top_k=top_k,
            temperature=temperature,
            seed=seed,
        )
        runtime_ms = int((time.perf_counter() - started) * 1000)
        generated_text = result["generated_text"]
        leakage = no_role_token_leakage(generated_text)
        prompt_leak = no_system_prompt_leakage(generated_text, system_text, prompt_text)
        unicode_result = valid_unicode(generated_text)
        return {
            **result,
            "runtime_milliseconds": runtime_ms,
            "role_token_leakage": leakage["status"] == "fail",
            "prompt_leakage": prompt_leak["status"] == "fail",
            "unicode_valid": unicode_result["status"] == "pass",
            "release_public_id": loaded["release_public_id"],
        }

    # --- audit -----------------------------------------------------

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event, "admin", "{}", str(uuid4()), event, "admin", admin_id,
                "inference_runtime", resource_id, "success", dumps_json(metadata),
            ),
        )
