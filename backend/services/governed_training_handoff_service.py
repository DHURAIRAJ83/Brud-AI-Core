"""Governed tokenizer/pretraining/instruction-tuning/evaluation handoff
(Phase 7, Steps 14-17).

`TokenizerCorpusService.build_corpus()` is structurally scoped to a
Phase 19-21A `corpus_release` and cannot accept Data-Studio content
directly (confirmed by direct inspection -- see plan doc section 1.3);
`PretrainingService`/`InstructionTuningService.create_experiment()`
already accept a `dataset_version_id`/`dataset_version_public_id`
directly. This service's real job is therefore the governed
*selection* (already done by `GovernedBuildService`) plus marking a
completed, governed dataset_version as offered to a specific pipeline
-- it never creates a `pretraining_jobs`/`instruction_tuning_experiments`
row itself (rule: "no automatic training start"), and never
recomputes `core_model.pretraining_readiness.readiness.overall_readiness()`
(a 17-dimension check spanning the tokenizer/model/training-loop
systems this service does not own -- reusing it would require
fabricating inputs Phase 7 has no basis for). The existing, separate,
manual admin action of creating a real job that points at this
dataset_version_id remains exactly as it is today.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.governed_builds import GovernedBuildRepository, public_row

_HANDOFF_EVENT_TYPES = {
    "tokenizer": "tokenizer_handoff",
    "pretraining": "pretraining_handoff",
    "instruction_tuning": "sft_handoff",
    "evaluation": "evaluation_handoff",
}


def _audit(connection, event: str, admin_id: str, resource_id: str, **metadata: Any) -> None:
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
            "governed_training_handoff",
            resource_id,
            "success",
            dumps_json(metadata),
        ),
    )


class GovernedTrainingHandoffService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = GovernedBuildRepository(settings.resolved_database_path)

    def _handoff(
        self, build_request_public_id: str, *, target_pipeline: str, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request_row = self.repository.build_request(connection, build_request_public_id)
            request = public_row(request_row)
            if request["target_pipeline"] != target_pipeline:
                raise ValidationError(
                    f"this build request was not created for the {target_pipeline} pipeline"
                )
            is_completed_version = (
                request["status"] == "completed"
                and request["result_entity_type"] == "dataset_version"
            )
            if not is_completed_version:
                raise ValidationError(
                    "the governed build must be completed (a dataset version created) before "
                    "this handoff"
                )
            version_public_id = request["result_entity_public_id"]
            self.repository.create_lineage_event(
                connection,
                {
                    "build_request_id": request_row["id"],
                    "event_type": _HANDOFF_EVENT_TYPES[target_pipeline],
                    "performed_by_admin_public_id": admin_id,
                    "notes": f"dataset_version={version_public_id}",
                },
            )
            _audit(
                connection,
                f"governed_{target_pipeline}_handoff",
                admin_id,
                build_request_public_id,
                dataset_version_public_id=version_public_id,
            )
        return {
            "build_request_public_id": build_request_public_id,
            "target_pipeline": target_pipeline,
            "dataset_version_public_id": version_public_id,
            "ready": True,
            "message": (
                f"This governed dataset version is ready for {target_pipeline}. Start the "
                f"actual {target_pipeline} run through its existing workflow, pointing it at "
                f"this dataset_version_id -- this handoff never starts a run automatically."
            ),
        }

    def tokenizer_handoff(self, build_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        return self._handoff(
            build_request_public_id, target_pipeline="tokenizer", admin_id=admin_id
        )

    def pretraining_handoff(self, build_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        return self._handoff(
            build_request_public_id, target_pipeline="pretraining", admin_id=admin_id
        )

    def sft_handoff(self, build_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        return self._handoff(
            build_request_public_id, target_pipeline="instruction_tuning", admin_id=admin_id
        )

    def evaluation_handoff(self, build_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        return self._handoff(
            build_request_public_id, target_pipeline="evaluation", admin_id=admin_id
        )


__all__ = ["GovernedTrainingHandoffService"]
