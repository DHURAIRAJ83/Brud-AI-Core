"""Phase 21A CPU-safe base-model resource estimation. Wraps
`core_model.pretraining_readiness.resource_profiles` (which itself
reuses Phase 8's parameter/memory formulas unchanged) with
persistence for audit purposes."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.pretraining_readiness import (
    PretrainingReadinessRepository,
    public_row,
)
from backend.models.pretraining_readiness import ResourceEstimateCreate
from core_model.pretraining_readiness.resource_profiles import (
    DEFAULT_SAFE_RAM_CEILING_BYTES,
    estimate_resource_profile,
)


class BaseModelResourceService:
    def __init__(self, repository: PretrainingReadinessRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def create_estimate(self, payload: ResourceEstimateCreate, admin_id: str) -> dict[str, Any]:
        ceiling = payload.safe_ram_ceiling_bytes or DEFAULT_SAFE_RAM_CEILING_BYTES
        estimate = estimate_resource_profile(
            payload.profile_name,
            payload.vocabulary_size,
            total_training_tokens=payload.total_training_tokens,
            safe_ram_ceiling_bytes=ceiling,
        )
        with self.repository.transaction() as connection:
            public_id = self.repository.create_base_model_resource_estimate(
                connection,
                {
                    "profile_name": estimate.profile_name,
                    "vocabulary_size": estimate.config.vocabulary_size,
                    "context_length": estimate.config.context_length,
                    "hidden_size": estimate.config.hidden_size,
                    "num_hidden_layers": estimate.config.num_hidden_layers,
                    "num_attention_heads": estimate.config.num_attention_heads,
                    "intermediate_size": estimate.config.intermediate_size,
                    "parameter_count": estimate.parameter_count,
                    "parameter_memory_bytes": estimate.parameter_memory_bytes,
                    "gradient_memory_bytes": estimate.gradient_memory_bytes,
                    "optimizer_state_memory_bytes": estimate.optimizer_state_memory_bytes,
                    "activation_memory_bytes": estimate.activation_memory_bytes,
                    "estimated_peak_ram_bytes": estimate.estimated_peak_ram_bytes,
                    "checkpoint_disk_bytes": estimate.checkpoint_disk_bytes,
                    "optimizer_disk_bytes": estimate.optimizer_disk_bytes,
                    "estimated_tokens_per_second": estimate.estimated_tokens_per_second,
                    "estimated_training_duration_seconds_min": (
                        estimate.estimated_training_duration_seconds_min
                    ),
                    "estimated_training_duration_seconds_max": (
                        estimate.estimated_training_duration_seconds_max
                    ),
                    "safe_ram_ceiling_bytes": estimate.safe_ram_ceiling_bytes,
                    "within_safe_limit": int(estimate.within_safe_limit),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(
                connection, "base_model_resource_estimate_created", admin_id, public_id,
                profile_name=estimate.profile_name, within_safe_limit=estimate.within_safe_limit,
            )
            return public_row(
                self.repository.base_model_resource_estimate(connection, public_id)
            )

    def get_estimate(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.base_model_resource_estimate(connection, public_id))

    def list_estimates(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {
                "items": [
                    public_row(row)
                    for row in self.repository.list_base_model_resource_estimates(connection)
                ]
            }

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
                "pretraining_readiness", resource_id, "success", dumps_json(metadata),
            ),
        )
