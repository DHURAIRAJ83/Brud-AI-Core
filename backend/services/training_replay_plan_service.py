"""Phase 14 Step 9 replay-data plan.

A deterministic, seeded selection of already-approved records from
existing ready/archived dataset versions' *train* splits, mixed in
alongside new training candidates to mitigate catastrophic-forgetting
risk. 70-90% new / 10-30% replay is a recommendation, not a fixed
rule -- callers may pass any `new_data_ratio`; the plan records
whether the chosen ratio falls inside the recommended band so a human
reviewer can judge the exception. See
docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

import random
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.training_incremental import TrainingIncrementalRepository

_RECOMMENDED_MIN_NEW_RATIO = 0.70
_RECOMMENDED_MAX_NEW_RATIO = 0.90
_DEFAULT_NEW_RATIO = 0.80
_DEFAULT_SEED = 42


class TrainingReplayPlanService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)

    def create_plan(
        self, assessment_public_id: str, values: dict[str, Any], *, admin_id: str
    ) -> dict[str, Any]:
        new_record_count = int(values["new_record_count"])
        if new_record_count <= 0:
            raise ValidationError("new_record_count must be positive")
        new_ratio = float(values.get("new_data_ratio", _DEFAULT_NEW_RATIO))
        if not (0 < new_ratio <= 1):
            raise ValidationError("new_data_ratio must be within (0, 1]")
        seed = int(values.get("selection_seed", _DEFAULT_SEED))

        replay_ratio = 1 - new_ratio
        target_replay_count = (
            round(new_record_count * replay_ratio / new_ratio) if new_ratio < 1 else 0
        )

        with self._training.transaction() as connection:
            pool = connection.execute(
                """SELECT r.public_id, r.language, r.record_type, dv.public_id AS dv_public_id
                FROM dataset_version_items i
                JOIN dataset_records r ON r.id = i.dataset_record_id
                JOIN dataset_versions dv ON dv.id = i.dataset_version_id
                WHERE i.split='train' AND dv.status IN ('ready','archived') AND r.status='approved'
                ORDER BY r.id"""
            ).fetchall()

        pool_records = [dict(row) for row in pool]
        rng = random.Random(seed)
        rng.shuffle(pool_records)
        selected = pool_records[: min(target_replay_count, len(pool_records))]

        language_distribution: dict[str, int] = {}
        task_distribution: dict[str, int] = {}
        source_versions: set[str] = set()
        for record in selected:
            language_distribution[record["language"]] = (
                language_distribution.get(record["language"], 0) + 1
            )
            task_distribution[record["record_type"]] = (
                task_distribution.get(record["record_type"], 0) + 1
            )
            source_versions.add(record["dv_public_id"])

        within_recommended_range = (
            _RECOMMENDED_MIN_NEW_RATIO <= new_ratio <= _RECOMMENDED_MAX_NEW_RATIO
        )
        reason = (
            f"deterministic seed={seed} sample of {len(selected)} existing approved "
            f"train-split records (requested {target_replay_count}, pool had "
            f"{len(pool_records)} available) to mitigate catastrophic-forgetting risk; "
            f"new_data_ratio={new_ratio} is "
            f"{'within' if within_recommended_range else 'outside'} the recommended "
            f"{_RECOMMENDED_MIN_NEW_RATIO}-{_RECOMMENDED_MAX_NEW_RATIO} band"
        )
        if not selected and target_replay_count > 0:
            reason += " -- no approved prior train-split records were available to replay"

        plan = self._training.create_replay_plan(
            assessment_public_id,
            {
                "new_record_count": new_record_count,
                "replay_record_count": len(selected),
                "new_data_ratio": new_ratio,
                "replay_data_ratio": replay_ratio,
                "replay_source_version_ids": sorted(source_versions),
                "replay_record_ids": [record["public_id"] for record in selected],
                "language_distribution": language_distribution,
                "task_distribution": task_distribution,
                "domain_distribution": {},
                "selection_method": "deterministic_representative_sample",
                "selection_seed": seed,
                "reason": reason,
                "created_by_admin_public_id": admin_id,
            },
        )
        return plan

    def get_plan(self, public_id: str) -> dict[str, Any]:
        return self._training.get_replay_plan(public_id)

    def list_plans(self, assessment_public_id: str) -> list[dict[str, Any]]:
        return self._training.list_replay_plans(assessment_public_id)


__all__ = ["TrainingReplayPlanService"]
