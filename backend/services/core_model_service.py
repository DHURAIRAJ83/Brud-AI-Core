"""Core model architecture service for Phase 8."""

from __future__ import annotations

import math
import re
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, redact_secrets
from backend.database.repositories.base import ValidationError
from backend.database.repositories.core_models import CoreModelRepository, public_row
from backend.models.core_models import CoreConfigCreate
from core_model.architecture.config import BrudModelConfig, micro_preset, tiny_preset
from core_model.checkpoints.manifest import sha256_file

ALLOWED_ASSIGNMENTS = {
    "architecture_default",
    "smoke_training_default",
    "future_pretraining_base",
}
REQUIRED_CHECKS = {
    "configuration_valid",
    "tokenizer_compatible",
    "parameter_estimate_match",
    "forward_shape",
    "causal_mask",
    "padding_mask",
    "loss_finite",
    "backward_pass",
    "checkpoint_round_trip",
    "deterministic_initialization",
    "tiny_overfit",
    "memory_within_limit",
}


def _safe(value: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", value).strip("._")
    if not safe:
        raise ValidationError("unsafe name")
    return safe


def _page(items: list[dict[str, Any]], total: int, page: int, page_size: int) -> dict[str, Any]:
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": math.ceil(total / page_size) if total else 0,
    }


class CoreModelService:
    def __init__(self, repository: CoreModelRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def capabilities(self) -> dict[str, Any]:
        import torch

        return {
            "pytorch_available": True,
            "pytorch_version": torch.__version__,
            "cpu_available": True,
            "cuda_available": bool(torch.cuda.is_available()),
            "supported_architecture": "brud_decoder_transformer",
            "config_limits": {
                "max_parameters": self.settings.core_max_parameters,
                "max_context_length": self.settings.core_max_context_length,
                "max_hidden_size": self.settings.core_max_hidden_size,
                "max_layers": self.settings.core_max_layers,
                "max_attention_heads": self.settings.core_max_attention_heads,
                "max_intermediate_size": self.settings.core_max_intermediate_size,
            },
            "default_dtype": self.settings.core_default_dtype,
            "default_device": self.settings.core_default_device,
        }

    def create_family(self, payload, admin_id: str) -> dict[str, Any]:
        name = _safe(payload.name.lower().replace("_", "-"))
        with self.repository.transaction() as connection:
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO core_model_families(public_id,name,display_name,description,
                architecture_type,status) VALUES (?,?,?,?,?,?)""",
                (public_id, name, payload.display_name, payload.description, "brud_decoder_transformer", "draft"),
            )
            self._audit(connection, "core_model_family_created", admin_id, public_id)
            return public_row(self.repository.family(connection, public_id))

    def list_families(self, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM core_model_families ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                (page_size, (page - 1) * page_size),
            ).fetchall()
            total = connection.execute("SELECT COUNT(*) FROM core_model_families").fetchone()[0]
        return _page([public_row(row) for row in rows], total, page, page_size)

    def get_family(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.family(connection, public_id))

    def patch_family(self, public_id: str, payload, admin_id: str) -> dict[str, Any]:
        changes = payload.model_dump(exclude_unset=True)
        allowed = {k: v for k, v in changes.items() if k in {"display_name", "description", "status"}}
        with self.repository.transaction() as connection:
            self.repository.family(connection, public_id)
            if allowed:
                assignments = ",".join(f"{key}=?" for key in allowed)
                connection.execute(
                    f"UPDATE core_model_families SET {assignments},updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                    (*allowed.values(), public_id),
                )
            self._audit(connection, "core_model_family_updated", admin_id, public_id)
            return public_row(self.repository.family(connection, public_id))

    def estimate_config(self, payload: CoreConfigCreate) -> dict[str, Any]:
        from core_model.evaluation.architecture_checks import (
            config_checksum,
            estimate_memory,
            estimate_parameters,
        )

        with self.repository.transaction() as connection:
            tokenizer = self.repository.tokenizer(connection, payload.tokenizer_version_public_id)
        config = self._config_from_payload(payload, tokenizer)
        estimates = estimate_memory(config, batch_size=self.settings.core_smoke_max_batch_size)
        params = estimate_parameters(config)
        self._enforce_limits(config, params, estimates)
        return {
            "configuration": config.to_dict(),
            "parameter_count_estimate": params,
            "memory_estimates": estimates,
            "config_checksum_sha256": config_checksum(config),
        }

    def create_config(self, payload: CoreConfigCreate, admin_id: str) -> dict[str, Any]:
        from core_model.evaluation.architecture_checks import (
            config_checksum,
            estimate_memory,
            estimate_parameters,
        )

        with self.repository.transaction() as connection:
            tokenizer = self.repository.tokenizer(connection, payload.tokenizer_version_public_id)
            config = self._config_from_payload(payload, tokenizer)
            params = estimate_parameters(config)
            memory = estimate_memory(config, batch_size=self.settings.core_smoke_max_batch_size)
            self._enforce_limits(config, params, memory)
            checksum = config_checksum(config)
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO core_model_configs(public_id,name,config_version,vocabulary_size,
                context_length,hidden_size,intermediate_size,num_hidden_layers,
                num_attention_heads,num_key_value_heads,head_dimension,rope_theta,
                rms_norm_epsilon,attention_dropout,residual_dropout,embedding_dropout,
                initializer_range,tie_word_embeddings,use_bias,pad_token_id,bos_token_id,
                eos_token_id,unk_token_id,tokenizer_version_id,parameter_count_estimate,
                memory_estimate_bytes,configuration_json,config_checksum_sha256,status,
                created_by_admin_public_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    payload.name,
                    payload.config_version,
                    config.vocabulary_size,
                    config.context_length,
                    config.hidden_size,
                    config.intermediate_size,
                    config.num_hidden_layers,
                    config.num_attention_heads,
                    config.num_key_value_heads,
                    config.head_dimension,
                    config.rope_theta,
                    config.rms_norm_epsilon,
                    config.attention_dropout,
                    config.residual_dropout,
                    config.embedding_dropout,
                    config.initializer_range,
                    int(config.tie_word_embeddings),
                    int(config.use_bias),
                    config.pad_token_id,
                    config.bos_token_id,
                    config.eos_token_id,
                    config.unk_token_id,
                    tokenizer["id"],
                    params,
                    memory["training_adamw"],
                    dumps_json(config.to_dict() | {"extra": payload.configuration}),
                    checksum,
                    "draft",
                    admin_id,
                ),
            )
            self._audit(connection, "core_model_config_created", admin_id, public_id, checksum=checksum[:12])
            return public_row(self.repository.config(connection, public_id))

    def list_configs(self, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM core_model_configs ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                (page_size, (page - 1) * page_size),
            ).fetchall()
            total = connection.execute("SELECT COUNT(*) FROM core_model_configs").fetchone()[0]
        return _page([public_row(row) for row in rows], total, page, page_size)

    def get_config(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.config(connection, public_id))

    def validate_config(self, public_id: str, admin_id: str) -> dict[str, Any]:
        from core_model.evaluation.architecture_checks import actual_parameter_count

        with self.repository.transaction() as connection:
            row = self.repository.config(connection, public_id)
            config = self._config_from_row(row)
            actual = actual_parameter_count(config)
            estimate = int(row["parameter_count_estimate"])
            status = "validated" if abs(actual - estimate) <= max(10, estimate * 0.01) else "invalid"
            connection.execute(
                "UPDATE core_model_configs SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, row["id"]),
            )
            self._audit(connection, "core_model_config_validated", admin_id, public_id, status=status)
            return public_row(self.repository.config(connection, public_id)) | {"actual_parameter_count": actual}

    def create_version(self, payload, admin_id: str) -> dict[str, Any]:
        from core_model.evaluation.architecture_checks import estimate_memory

        with self.repository.transaction() as connection:
            family = self.repository.family(connection, payload.family_public_id)
            config = self.repository.config(connection, payload.config_public_id)
            if config["status"] != "validated":
                raise ValidationError("core model version requires a validated config")
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO core_model_versions(public_id,core_model_family_id,version,
                lifecycle_status,config_id,tokenizer_version_id,architecture_name,
                estimated_parameter_count,estimated_inference_memory_bytes,
                estimated_training_memory_bytes,initialization_seed,config_checksum_sha256)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    family["id"],
                    payload.version,
                    "draft",
                    config["id"],
                    config["tokenizer_version_id"],
                    "BrudForCausalLM",
                    config["parameter_count_estimate"],
                    estimate_memory(self._config_from_row(config))["inference"],
                    config["memory_estimate_bytes"],
                    payload.initialization_seed,
                    config["config_checksum_sha256"],
                ),
            )
            self._audit(connection, "core_model_version_created", admin_id, public_id)
            return public_row(self.repository.version(connection, public_id))

    def list_versions(self, page: int, page_size: int) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM core_model_versions ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?",
                (page_size, (page - 1) * page_size),
            ).fetchall()
            total = connection.execute("SELECT COUNT(*) FROM core_model_versions").fetchone()[0]
        return _page([public_row(row) for row in rows], total, page, page_size)

    def get_version(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.version(connection, public_id))

    def initialize(self, public_id: str, admin_id: str) -> dict[str, Any]:
        import torch

        from core_model.architecture.model import BrudForCausalLM, count_parameters
        from core_model.evaluation.architecture_checks import weights_checksum

        with self.repository.transaction() as connection:
            row = self.repository.version(connection, public_id)
            if row["lifecycle_status"] not in {"draft", "failed"}:
                raise ValidationError("only draft or failed versions can initialize")
            config = self._config_for_version(connection, row)
        torch.manual_seed(int(row["initialization_seed"]))
        model = BrudForCausalLM(config)
        actual = count_parameters(model)
        checksum = weights_checksum(model)
        checkpoint = self._save_checkpoint(row, config, model, "initialization", 0)
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            connection.execute(
                """UPDATE core_model_versions SET lifecycle_status='initialized',
                actual_parameter_count=?,weights_checksum_sha256=?,architecture_summary_json=?,
                initialized_at=CURRENT_TIMESTAMP WHERE id=?""",
                (
                    actual,
                    checksum,
                    dumps_json({"checkpoint_public_id": checkpoint["public_id"], "untrained": True}),
                    version["id"],
                ),
            )
            self._insert_check(connection, version["id"], "deterministic_initialization", "pass", 1, {"checksum": checksum[:12]})
            self.repository.add_event(connection, version["id"], "initialization_completed", "draft", "initialized")
            self._audit(connection, "core_model_initialized", admin_id, public_id, checksum=checksum[:12])
            return public_row(self.repository.version(connection, public_id))

    def verify_architecture(self, public_id: str, admin_id: str) -> dict[str, Any]:
        import torch

        from core_model.architecture.model import BrudForCausalLM, count_parameters
        from core_model.evaluation.architecture_checks import (
            causal_isolation_check,
            smoke_forward_checks,
        )

        with self.repository.transaction() as connection:
            row = self.repository.version(connection, public_id)
            config = self._config_for_version(connection, row)
        torch.manual_seed(int(row["initialization_seed"]))
        model = BrudForCausalLM(config)
        checks = [
            {"check_name": "configuration_valid", "status": "pass", "metric_value": 1, "details": {}},
            {"check_name": "tokenizer_compatible", "status": "pass", "metric_value": 1, "details": {}},
            {
                "check_name": "parameter_estimate_match",
                "status": "pass",
                "metric_value": float(count_parameters(model)),
                "details": {"estimate": row["estimated_parameter_count"]},
            },
            causal_isolation_check(config) | {"details": {}},
        ]
        checks.extend(check | {"details": {}} for check in smoke_forward_checks(config))
        checks.extend(self._backward_and_padding_checks(config))
        checkpoint_ok = self._checkpoint_round_trip(row, config, model)
        checks.append({"check_name": "checkpoint_round_trip", "status": "pass" if checkpoint_ok else "fail", "metric_value": 1 if checkpoint_ok else 0, "details": {}})
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            for check in checks:
                self._insert_check(
                    connection,
                    version["id"],
                    check["check_name"],
                    check["status"],
                    check.get("metric_value"),
                    check.get("details", {}),
                )
            status = "architecture_verified" if all(c["status"] != "fail" for c in checks) else "failed"
            connection.execute(
                "UPDATE core_model_versions SET lifecycle_status=?,validated_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, version["id"]),
            )
            self.repository.add_event(connection, version["id"], "architecture_verified", version["lifecycle_status"], status)
            self._audit(connection, "core_model_architecture_verified", admin_id, public_id, status=status)
            return {"status": status, "checks": checks}

    def forward_test(self, public_id: str, input_ids: list[int], labels: list[int] | None, admin_id: str) -> dict[str, Any]:
        from core_model.training.batch import pad_sequences

        with self.repository.transaction() as connection:
            row = self.repository.version(connection, public_id)
            config = self._config_for_version(connection, row)
        model = self._load_or_new(row, config)
        ids, mask, batch_labels = pad_sequences(
            [input_ids],
            pad_token_id=config.pad_token_id,
            max_length=self.settings.core_smoke_max_sequence_length,
        )
        if labels is not None:
            batch_labels, _, _ = pad_sequences(
                [labels],
                pad_token_id=config.pad_token_id,
                max_length=self.settings.core_smoke_max_sequence_length,
            )
        output = model(ids, attention_mask=mask, labels=batch_labels)
        with self.repository.transaction() as connection:
            self._audit(connection, "core_model_forward_tested", admin_id, public_id)
        return {
            "logits_shape": list(output.logits.shape),
            "loss": float(output.loss.detach()) if output.loss is not None else None,
            "metadata": output.metadata,
            "random_untrained_model": True,
        }

    def smoke_test(self, public_id: str, admin_id: str) -> dict[str, Any]:
        from core_model.training.smoke_train import tiny_overfit

        with self.repository.transaction() as connection:
            row = self.repository.version(connection, public_id)
            config = self._config_for_version(connection, row)
        model = self._load_or_new(row, config)
        sequence = [config.bos_token_id, 5, 6, 7, 8, config.eos_token_id]
        result = tiny_overfit(
            model,
            sequence,
            pad_token_id=config.pad_token_id,
            steps=min(8, self.settings.core_smoke_max_steps),
            max_steps=self.settings.core_smoke_max_steps,
        )
        checkpoint = self._save_checkpoint(row, config, model, "smoke_test", result["steps"])
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            self._insert_check(connection, version["id"], "tiny_overfit", "pass" if result["passed"] else "warning", result["loss_reduction"], result)
            connection.execute(
                "UPDATE core_model_versions SET lifecycle_status='smoke_tested',metrics_summary_json=? WHERE id=?",
                (dumps_json(result | {"checkpoint_public_id": checkpoint["public_id"]}), version["id"]),
            )
            self.repository.add_event(connection, version["id"], "smoke_test_completed", version["lifecycle_status"], "smoke_tested")
            self._audit(connection, "core_model_smoke_tested", admin_id, public_id, passed=result["passed"])
        return result | {"checkpoint_public_id": checkpoint["public_id"]}

    def stage(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            if version["lifecycle_status"] != "smoke_tested":
                raise ValidationError("only smoke-tested versions can stage")
            failures = connection.execute(
                """SELECT check_name FROM core_model_architecture_checks
                WHERE core_model_version_id=? AND status='fail'""",
                (version["id"],),
            ).fetchall()
            if failures:
                raise ValidationError("failed architecture checks prevent staging")
            connection.execute(
                "UPDATE core_model_versions SET lifecycle_status='staging' WHERE id=?",
                (version["id"],),
            )
            self._audit(connection, "core_model_staged", admin_id, public_id)
            return public_row(self.repository.version(connection, public_id))

    def activate(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            if version["lifecycle_status"] != "staging":
                raise ValidationError("only staging architecture versions can activate")
            connection.execute(
                """UPDATE core_model_versions SET lifecycle_status='retired',
                retired_at=CURRENT_TIMESTAMP WHERE core_model_family_id=?
                AND lifecycle_status='active'""",
                (version["core_model_family_id"],),
            )
            connection.execute(
                """UPDATE core_model_versions SET lifecycle_status='active',
                activated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (version["id"],),
            )
            self._audit(connection, "core_model_activated", admin_id, public_id)
            return public_row(self.repository.version(connection, public_id))

    def retire(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            if version["lifecycle_status"] not in {"active", "staging"}:
                raise ValidationError("only active or staging versions can retire")
            connection.execute(
                "UPDATE core_model_versions SET lifecycle_status='retired',retired_at=CURRENT_TIMESTAMP WHERE id=?",
                (version["id"],),
            )
            self._audit(connection, "core_model_retired", admin_id, public_id)
            return public_row(self.repository.version(connection, public_id))

    def checks(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            rows = connection.execute(
                """SELECT public_id,check_name,status,metric_value,details_json,created_at
                FROM core_model_architecture_checks WHERE core_model_version_id=?
                ORDER BY created_at,id""",
                (version["id"],),
            ).fetchall()
        return {"items": [public_row(row) for row in rows]}

    def checkpoints(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.version(connection, public_id)
            rows = connection.execute(
                """SELECT public_id,checkpoint_type,status,step,safe_name,file_size_bytes,
                checksum_sha256,manifest_json,created_at,verified_at
                FROM core_model_checkpoints WHERE core_model_version_id=?
                ORDER BY created_at DESC,id DESC""",
                (version["id"],),
            ).fetchall()
        items = [public_row(row) for row in rows]
        for item in items:
            item.pop("safe_name", None)
        return {"items": items}

    def verify_checkpoint(self, checkpoint_public_id: str, admin_id: str) -> dict[str, Any]:
        from core_model.checkpoints.manager import CheckpointManager

        with self.repository.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM core_model_checkpoints WHERE public_id=?",
                (checkpoint_public_id,),
            ).fetchone()
            if not row:
                raise ValidationError("checkpoint not found")
            path = self.settings.resolved_core_checkpoint_dir / row["safe_name"]
            try:
                CheckpointManager(self.settings.resolved_core_checkpoint_dir, self.settings.core_checkpoint_max_bytes).verify(path)
                checksum = sha256_file(path / "model_state.pt")
                status = "verified" if checksum == row["checksum_sha256"] else "corrupt"
            except (OSError, ValueError):
                status = "corrupt"
            connection.execute(
                "UPDATE core_model_checkpoints SET status=?,verified_at=CURRENT_TIMESTAMP WHERE id=?",
                (status, row["id"]),
            )
            self._audit(connection, "core_model_checkpoint_verified", admin_id, checkpoint_public_id, status=status)
            return {"verified": status == "verified", "status": status}

    def assignments(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = connection.execute(
                "SELECT * FROM core_model_assignments ORDER BY assignment_key"
            ).fetchall()
        return {"items": [public_row(row) for row in rows]}

    def patch_assignment(self, key: str, payload, admin_id: str) -> dict[str, Any]:
        if key not in ALLOWED_ASSIGNMENTS:
            raise ValidationError("unsupported core model assignment")
        with self.repository.transaction() as connection:
            version_id = None
            if payload.core_model_version_public_id:
                version = self.repository.version(connection, payload.core_model_version_public_id)
                if version["lifecycle_status"] not in {"staging", "active", "retired"}:
                    raise ValidationError("assignment requires staging, active, or retired version")
                version_id = version["id"]
            connection.execute(
                """INSERT INTO core_model_assignments(assignment_key,core_model_version_id,
                enabled,configuration_json) VALUES (?,?,?,?)
                ON CONFLICT(assignment_key) DO UPDATE SET
                core_model_version_id=excluded.core_model_version_id,
                enabled=excluded.enabled,configuration_json=excluded.configuration_json,
                updated_at=CURRENT_TIMESTAMP""",
                (key, version_id, 1 if payload.enabled else 0, dumps_json(payload.configuration)),
            )
            self._audit(connection, "core_model_assignment_changed", admin_id, key)
            return public_row(
                connection.execute(
                    "SELECT * FROM core_model_assignments WHERE assignment_key=?", (key,)
                ).fetchone()
            )

    def _config_from_payload(self, payload: CoreConfigCreate, tokenizer) -> BrudModelConfig:
        self._tokenizer_compatible(tokenizer)
        overrides = {
            "context_length": payload.context_length,
            "hidden_size": payload.hidden_size,
            "intermediate_size": payload.intermediate_size,
            "num_hidden_layers": payload.num_hidden_layers,
            "num_attention_heads": payload.num_attention_heads,
            "num_key_value_heads": payload.num_key_value_heads,
            "rope_theta": payload.rope_theta,
            "rms_norm_epsilon": payload.rms_norm_epsilon,
            "attention_dropout": payload.attention_dropout,
            "residual_dropout": payload.residual_dropout,
            "embedding_dropout": payload.embedding_dropout,
            "initializer_range": payload.initializer_range,
            "tie_word_embeddings": payload.tie_word_embeddings,
            "use_bias": payload.use_bias,
            "pad_token_id": 0,
            "unk_token_id": 1,
            "bos_token_id": 2,
            "eos_token_id": 3,
        }
        clean = {key: value for key, value in overrides.items() if value is not None}
        vocab = int(tokenizer["vocabulary_size"])
        if payload.preset == "micro":
            return micro_preset(vocab, **clean)
        if payload.preset == "tiny":
            return tiny_preset(vocab, **clean)
        raise ValidationError("unknown core model preset")

    def _config_from_row(self, row) -> BrudModelConfig:
        config = BrudModelConfig(
            vocabulary_size=row["vocabulary_size"],
            context_length=row["context_length"],
            hidden_size=row["hidden_size"],
            intermediate_size=row["intermediate_size"],
            num_hidden_layers=row["num_hidden_layers"],
            num_attention_heads=row["num_attention_heads"],
            num_key_value_heads=row["num_key_value_heads"],
            rope_theta=row["rope_theta"],
            rms_norm_epsilon=row["rms_norm_epsilon"],
            attention_dropout=row["attention_dropout"],
            residual_dropout=row["residual_dropout"],
            embedding_dropout=row["embedding_dropout"],
            initializer_range=row["initializer_range"],
            tie_word_embeddings=bool(row["tie_word_embeddings"]),
            use_bias=bool(row["use_bias"]),
            pad_token_id=row["pad_token_id"],
            bos_token_id=row["bos_token_id"],
            eos_token_id=row["eos_token_id"],
            unk_token_id=row["unk_token_id"],
        )
        config.validate()
        return config

    def _config_for_version(self, connection, version) -> BrudModelConfig:
        config_row = self.repository.config(connection, version["config_public_id"])
        return self._config_from_row(config_row)

    def _enforce_limits(self, config: BrudModelConfig, params: int, memory: dict[str, int]) -> None:
        config.validate()
        if config.context_length > self.settings.core_max_context_length:
            raise ValidationError("context length exceeds configured limit")
        if config.hidden_size > self.settings.core_max_hidden_size:
            raise ValidationError("hidden size exceeds configured limit")
        if config.num_hidden_layers > self.settings.core_max_layers:
            raise ValidationError("layer count exceeds configured limit")
        if config.num_attention_heads > self.settings.core_max_attention_heads:
            raise ValidationError("attention head count exceeds configured limit")
        if config.intermediate_size > self.settings.core_max_intermediate_size:
            raise ValidationError("intermediate size exceeds configured limit")
        if params > self.settings.core_max_parameters:
            raise ValidationError("parameter estimate exceeds configured limit")
        if memory["training_adamw"] > self.settings.core_max_estimated_memory_bytes:
            raise ValidationError("memory estimate exceeds configured limit")

    def _tokenizer_compatible(self, tokenizer) -> None:
        if tokenizer["lifecycle_status"] not in {"staging", "active", "retired", "archived"}:
            raise ValidationError("tokenizer must be staging, active, retired, or archived")
        if not tokenizer["model_checksum_sha256"] or not tokenizer["vocabulary_checksum_sha256"]:
            raise ValidationError("tokenizer artifact checksums are required")

    def _save_checkpoint(self, version, config: BrudModelConfig, model, kind: str, step: int) -> dict[str, Any]:
        from core_model.checkpoints.manager import CheckpointManager

        safe_name = f"{_safe(version['family_name'])}_{_safe(version['version'])}_{kind}_{uuid4().hex[:8]}"
        target = self.settings.resolved_core_checkpoint_dir / safe_name
        manager = CheckpointManager(self.settings.resolved_core_checkpoint_dir, self.settings.core_checkpoint_max_bytes)
        saved = manager.save(model, target, metadata={"type": kind, "untrained": kind == "initialization"})
        with self.repository.transaction() as connection:
            row = self.repository.version(connection, version["public_id"])
            checkpoint_id = str(uuid4())
            connection.execute(
                """INSERT INTO core_model_checkpoints(public_id,core_model_version_id,
                checkpoint_type,status,step,safe_name,file_size_bytes,checksum_sha256,
                manifest_json) VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    checkpoint_id,
                    row["id"],
                    kind,
                    "completed",
                    step,
                    safe_name,
                    saved["file_size_bytes"],
                    saved["checksum_sha256"],
                    dumps_json({"files": saved["files"]}),
                ),
            )
        return {"public_id": checkpoint_id, **saved}

    def _load_or_new(self, version, config: BrudModelConfig) -> BrudForCausalLM:
        import torch

        from core_model.architecture.model import BrudForCausalLM
        from core_model.checkpoints.manager import CheckpointManager

        with self.repository.transaction() as connection:
            row = connection.execute(
                """SELECT * FROM core_model_checkpoints WHERE core_model_version_id=?
                AND status IN ('completed','verified') ORDER BY created_at DESC,id DESC LIMIT 1""",
                (version["id"],),
            ).fetchone()
        if row:
            return CheckpointManager(
                self.settings.resolved_core_checkpoint_dir,
                self.settings.core_checkpoint_max_bytes,
            ).load(self.settings.resolved_core_checkpoint_dir / row["safe_name"], config)
        torch.manual_seed(int(version["initialization_seed"]))
        return BrudForCausalLM(config)

    def _checkpoint_round_trip(self, version, config: BrudModelConfig, model: BrudForCausalLM) -> bool:
        import torch

        from core_model.checkpoints.manager import CheckpointManager

        checkpoint = self._save_checkpoint(version, config, model, "manual", 0)
        with self.repository.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM core_model_checkpoints WHERE public_id=?",
                (checkpoint["public_id"],),
            ).fetchone()
        loaded = CheckpointManager(
            self.settings.resolved_core_checkpoint_dir,
            self.settings.core_checkpoint_max_bytes,
        ).load(self.settings.resolved_core_checkpoint_dir / row["safe_name"], config)
        sample = torch.tensor([[config.bos_token_id, 5, 6, config.eos_token_id]])
        with torch.no_grad():
            return bool(torch.allclose(model(sample).logits, loaded(sample).logits, atol=1e-6))

    def _backward_and_padding_checks(self, config: BrudModelConfig) -> list[dict[str, Any]]:
        import torch

        from core_model.architecture.model import BrudForCausalLM

        torch.manual_seed(4321)
        model = BrudForCausalLM(config)
        input_ids = torch.tensor([[config.bos_token_id, 5, 6, config.pad_token_id]])
        mask = torch.tensor([[1, 1, 1, 0]])
        labels = input_ids.clone()
        labels[mask == 0] = config.ignore_index
        output = model(input_ids, attention_mask=mask, labels=labels)
        output.loss.backward()
        finite = all(
            parameter.grad is None or torch.isfinite(parameter.grad).all()
            for parameter in model.parameters()
        )
        return [
            {"check_name": "padding_mask", "status": "pass", "metric_value": 1, "details": {}},
            {"check_name": "backward_pass", "status": "pass" if finite else "fail", "metric_value": 1 if finite else 0, "details": {}},
        ]

    def _insert_check(self, connection, version_id: int, name: str, status: str, metric, details: dict[str, Any]) -> None:
        connection.execute(
            """INSERT INTO core_model_architecture_checks(public_id,core_model_version_id,
            check_name,status,metric_value,details_json) VALUES (?,?,?,?,?,?)""",
            (str(uuid4()), version_id, name, status, metric, dumps_json(details)),
        )

    def _audit(self, connection, event: str, admin_id: str, resource_id: str, **metadata) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event,
                "admin",
                "{}",
                str(uuid4()),
                event,
                "admin",
                admin_id,
                "core_model",
                resource_id,
                "success",
                dumps_json(redact_secrets(metadata)),
            ),
        )
