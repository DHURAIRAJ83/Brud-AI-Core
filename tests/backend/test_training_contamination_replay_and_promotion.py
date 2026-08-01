import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import ValidationError
from backend.database.repositories.training_incremental import TrainingIncrementalRepository
from backend.services.training_contamination_service import TrainingContaminationService
from backend.services.training_dataset_promotion_service import TrainingDatasetPromotionService
from backend.services.training_example_transformation_service import (
    TrainingExampleTransformationService,
)
from backend.services.training_replay_plan_service import TrainingReplayPlanService
from backend.services.training_suitability_service import (
    TrainingSuitabilityAssessmentService,
    TrainingSuitabilityError,
)
from tests.backend.test_training_suitability_and_transformation import (
    ADMIN_ID,
    _build_accepted_experiment,
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "training_promotion.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _insert_evaluation_fixture(
    database_path: Path, *, prompt: str, reference_answer: str = ""
) -> None:
    with sqlite3.connect(database_path) as connection:
        suite_id = connection.execute(
            """INSERT INTO model_evaluation_suites(
            public_id,name,version,created_by_admin_public_id)
            VALUES (?,?,?,?)""",
            (str(uuid4()), "phase14-test-suite", "v1", ADMIN_ID),
        ).lastrowid
        fixture_set_id = connection.execute(
            """INSERT INTO model_evaluation_fixture_sets(
            public_id,model_evaluation_suite_id,name,created_by_admin_public_id)
            VALUES (?,?,?,?)""",
            (str(uuid4()), suite_id, "phase14-test-fixture-set", ADMIN_ID),
        ).lastrowid
        connection.execute(
            """INSERT INTO model_evaluation_fixtures(
            public_id,model_evaluation_fixture_set_id,category,language,prompt,reference_answer,
            checksum_sha256) VALUES (?,?,?,?,?,?,?)""",
            (
                str(uuid4()), fixture_set_id, "instruction_following", "ta", prompt,
                reference_answer, "chk-fixture-1",
            ),
        )
        connection.commit()


def _insert_ready_dataset_version_with_train_records(
    database_path: Path, *, count: int, name: str = "phase14-replay-source"
) -> str:
    with sqlite3.connect(database_path) as connection:
        version_public_id = str(uuid4())
        version_id = connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            (version_public_id, name, "v1", "ready", "chk-dataset-version"),
        ).lastrowid
        for index in range(count):
            record_public_id = str(uuid4())
            record_id = connection.execute(
                """INSERT INTO dataset_records(
                public_id,content,language,status,record_type,instruction,output_text,
                content_hash) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    record_public_id, f"replay content {index}", "ta", "approved", "instruction",
                    f"question {index}", f"answer {index}", f"chk-replay-{index}",
                ),
            ).lastrowid
            connection.execute(
                """INSERT INTO dataset_version_items(dataset_version_id,dataset_record_id,split,
                sequence_number) VALUES (?,?,?,?)""",
                (version_id, record_id, "train", index),
            )
        connection.commit()
    return version_public_id


def _approved_candidate(
    settings: Settings, *, prompt: str = "தமிழ் என்றால் என்ன?",
    assistant: str = "தமிழ் ஒரு திராவிட மொழி.", code_suffix: str = "1",
) -> tuple[dict, dict]:
    built = _build_accepted_experiment(settings, code_suffix=code_suffix)
    suitability = TrainingSuitabilityAssessmentService(settings)
    assessment = suitability.create_assessment(built["experiment"]["public_id"], admin_id=ADMIN_ID)
    suitability.run_assessment(assessment["public_id"], admin_id=ADMIN_ID)
    training = TrainingIncrementalRepository(settings.resolved_database_path)
    item = training.list_items(assessment["public_id"])[0]

    transformation = TrainingExampleTransformationService(settings)
    candidate = transformation.transform(
        item["public_id"],
        {
            "transformation_type": "instruction_response_pair",
            "prompt_text": prompt, "assistant_text": assistant, "language": "ta",
            "source_checksum": "chk-record-0",
        },
        admin_id=ADMIN_ID,
    )
    candidate = transformation.review_candidate(
        candidate["public_id"], {"decision": "approved", "reason": "looks correct"},
        admin_id=ADMIN_ID,
    )
    return assessment, candidate


# -- contamination recheck -------------------------------------------------------------------


def test_contamination_recheck_clear_for_novel_text(settings: Settings) -> None:
    _, candidate = _approved_candidate(settings)
    service = TrainingContaminationService(settings)
    result = service.recheck_candidates([candidate["public_id"]])
    assert result["candidates"][candidate["public_id"]]["result"] == "clear"
    assert result["blocking_candidate_ids"] == []


def test_contamination_recheck_confirms_overlap_with_evaluation_fixture(settings: Settings) -> None:
    _, candidate = _approved_candidate(
        settings, prompt="தமிழ் என்றால் என்ன?", assistant="தமிழ் ஒரு திராவிட மொழி."
    )
    _insert_evaluation_fixture(
        settings.resolved_database_path,
        prompt="தமிழ் என்றால் என்ன?\nதமிழ் ஒரு திராவிட மொழி.",
    )
    service = TrainingContaminationService(settings)
    result = service.recheck_candidates([candidate["public_id"]])
    assert result["candidates"][candidate["public_id"]]["result"] == "confirmed_overlap"
    assert candidate["public_id"] in result["blocking_candidate_ids"]


# -- replay plan -------------------------------------------------------------------------------


def test_replay_plan_creates_deterministic_selection(settings: Settings) -> None:
    _insert_ready_dataset_version_with_train_records(settings.resolved_database_path, count=10)
    assessment, _candidate = _approved_candidate(settings)
    service = TrainingReplayPlanService(settings)
    plan = service.create_plan(
        assessment["public_id"],
        {"new_record_count": 40, "new_data_ratio": 0.8, "selection_seed": 42},
        admin_id=ADMIN_ID,
    )
    assert plan["new_record_count"] == 40
    assert plan["replay_record_count"] == 10
    assert plan["selection_method"] == "deterministic_representative_sample"
    assert len(plan["replay_record_ids"]) == 10

    plan_again = service.create_plan(
        assessment["public_id"],
        {"new_record_count": 40, "new_data_ratio": 0.8, "selection_seed": 42},
        admin_id=ADMIN_ID,
    )
    assert plan_again["replay_record_ids"] == plan["replay_record_ids"]


def test_replay_plan_handles_empty_pool(settings: Settings) -> None:
    assessment, _candidate = _approved_candidate(settings)
    service = TrainingReplayPlanService(settings)
    plan = service.create_plan(
        assessment["public_id"], {"new_record_count": 10, "new_data_ratio": 0.8},
        admin_id=ADMIN_ID,
    )
    assert plan["replay_record_count"] == 0
    assert "no approved prior train-split records" in plan["reason"]


# -- dataset promotion request -----------------------------------------------------------------


def test_create_promotion_request_creates_draft_with_lineage_manifest(settings: Settings) -> None:
    assessment, candidate = _approved_candidate(settings)
    service = TrainingDatasetPromotionService(settings)
    request = service.create_request(
        assessment["public_id"], {"candidate_public_ids": [candidate["public_id"]]},
        admin_id=ADMIN_ID,
    )
    assert request["status"] == "draft"
    assert request["selected_candidate_ids"] == [candidate["public_id"]]
    assert "contamination_recheck" in request["lineage_manifest"]


def test_create_promotion_request_rejects_unapproved_candidate(settings: Settings) -> None:
    built = _build_accepted_experiment(settings)
    suitability = TrainingSuitabilityAssessmentService(settings)
    assessment = suitability.create_assessment(built["experiment"]["public_id"], admin_id=ADMIN_ID)
    suitability.run_assessment(assessment["public_id"], admin_id=ADMIN_ID)
    training = TrainingIncrementalRepository(settings.resolved_database_path)
    item = training.list_items(assessment["public_id"])[0]
    transformation = TrainingExampleTransformationService(settings)
    candidate = transformation.transform(
        item["public_id"],
        {
            "transformation_type": "instruction_response_pair", "prompt_text": "q",
            "assistant_text": "a", "source_checksum": "s",
        },
        admin_id=ADMIN_ID,
    )
    service = TrainingDatasetPromotionService(settings)
    with pytest.raises(TrainingSuitabilityError):
        service.create_request(
            assessment["public_id"], {"candidate_public_ids": [candidate["public_id"]]},
            admin_id=ADMIN_ID,
        )


def test_create_promotion_request_blocks_confirmed_overlap(settings: Settings) -> None:
    assessment, candidate = _approved_candidate(
        settings, prompt="தமிழ் என்றால் என்ன?", assistant="தமிழ் ஒரு திராவிட மொழி."
    )
    _insert_evaluation_fixture(
        settings.resolved_database_path,
        prompt="தமிழ் என்றால் என்ன?\nதமிழ் ஒரு திராவிட மொழி.",
    )
    service = TrainingDatasetPromotionService(settings)
    with pytest.raises(TrainingSuitabilityError):
        service.create_request(
            assessment["public_id"], {"candidate_public_ids": [candidate["public_id"]]},
            admin_id=ADMIN_ID,
        )


def test_approve_and_materialize_creates_dataset_version(settings: Settings) -> None:
    assessment, candidate = _approved_candidate(settings)
    service = TrainingDatasetPromotionService(settings)
    request = service.create_request(
        assessment["public_id"], {"candidate_public_ids": [candidate["public_id"]]},
        admin_id=ADMIN_ID,
    )
    service.submit_for_approval(request["public_id"], admin_id=ADMIN_ID)
    approved = service.approve(request["public_id"], admin_id=ADMIN_ID)
    assert approved["status"] == "approved"

    materialized = service.materialize(request["public_id"], admin_id=ADMIN_ID)
    assert materialized["status"] == "ready"
    assert materialized["dataset_version_public_id"]
    assert materialized["train_split_checksum"]

    training = TrainingIncrementalRepository(settings.resolved_database_path)
    linked_candidate = training.get_candidate(candidate["public_id"])
    assert linked_candidate["dataset_record_public_id"]


def test_materialize_rejects_non_approved_request(settings: Settings) -> None:
    assessment, candidate = _approved_candidate(settings)
    service = TrainingDatasetPromotionService(settings)
    request = service.create_request(
        assessment["public_id"], {"candidate_public_ids": [candidate["public_id"]]},
        admin_id=ADMIN_ID,
    )
    with pytest.raises(ValidationError):
        service.materialize(request["public_id"], admin_id=ADMIN_ID)


def test_approved_promotion_request_selection_is_immutable_at_sql_level(settings: Settings) -> None:
    """The Step 6/13 stale-state guard in `materialize()` is defense in
    depth -- the schema's immutable-once-approved trigger already makes
    it structurally impossible to change which candidates were approved
    after the fact, which this asserts directly."""

    assessment, candidate = _approved_candidate(settings)
    service = TrainingDatasetPromotionService(settings)
    request = service.create_request(
        assessment["public_id"], {"candidate_public_ids": [candidate["public_id"]]},
        admin_id=ADMIN_ID,
    )
    service.approve(request["public_id"], admin_id=ADMIN_ID)
    training = TrainingIncrementalRepository(settings.resolved_database_path)
    with pytest.raises(Exception, match="immutable"):
        training.update_promotion_request(
            request["public_id"], {"selected_candidate_ids_json": "[]"}
        )
