import sqlite3
from pathlib import Path
from uuid import uuid4

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.base import NotFoundError, ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from tests.backend.test_training_suitability_and_transformation import (
    ADMIN_ID,
    _build_accepted_experiment,
)


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "production_readiness.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


@pytest.fixture
def repository(settings: Settings) -> ProductionReadinessRepository:
    return ProductionReadinessRepository(settings.resolved_database_path)


def _insert_knowledge_space(database_path: Path) -> str:
    public_id = str(uuid4())
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """INSERT INTO rag_knowledge_spaces(public_id,name,slug,created_by_admin_public_id)
            VALUES (?,?,?,?)""",
            (public_id, "Prod Space", f"prod-space-{public_id[:8]}", ADMIN_ID),
        )
        connection.commit()
    return public_id


def _accepted_rag_experiment(settings: Settings) -> dict:
    return _build_accepted_experiment(settings)


def _insert_minimal_model_candidate(database_path: Path) -> str:
    """Minimal FK chain for `core_model_versions` -- repository tests only
    need the row to exist, not a real loadable model, so no tokenizer
    artifact is trained."""

    with sqlite3.connect(database_path) as connection:
        suffix = uuid4().hex[:8]
        connection.execute(
            """INSERT INTO dataset_versions(public_id,name,version,status,checksum_sha256)
            VALUES (?,?,?,?,?)""",
            (str(uuid4()), f"ds-{suffix}", "v1", "ready", "f" * 64),
        )
        dataset_version_id = connection.execute(
            "SELECT id FROM dataset_versions WHERE name=?", (f"ds-{suffix}",)
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO tokenizer_families(public_id,name,display_name,status) VALUES (?,?,?,?)",
            (str(uuid4()), f"tok-{suffix}", "Tok", "active"),
        )
        family_id = connection.execute(
            "SELECT id FROM tokenizer_families WHERE name=?", (f"tok-{suffix}",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO tokenizer_versions(public_id,tokenizer_family_id,version,
            lifecycle_status,algorithm,vocabulary_size,character_coverage,
            normalization_rule_name,model_type,dataset_version_id,corpus_checksum_sha256,
            model_checksum_sha256,vocabulary_checksum_sha256,artifact_manifest_json,
            special_tokens_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(uuid4()), family_id, "v1", "active", "bpe", 64, 0.9995, "nmt_nfkc",
                "sentencepiece", dataset_version_id, "a" * 64, "b" * 64, "c" * 64, "{}", "[]",
            ),
        )
        tokenizer_id = connection.execute(
            "SELECT id FROM tokenizer_versions WHERE tokenizer_family_id=?", (family_id,)
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO core_model_families(public_id,name,display_name,status) VALUES (?,?,?,?)",
            (str(uuid4()), f"family-{suffix}", "Family", "active"),
        )
        core_family_id = connection.execute(
            "SELECT id FROM core_model_families WHERE name=?", (f"family-{suffix}",)
        ).fetchone()[0]
        connection.execute(
            """INSERT INTO core_model_configs(public_id,name,config_version,vocabulary_size,
            context_length,hidden_size,intermediate_size,num_hidden_layers,num_attention_heads,
            num_key_value_heads,head_dimension,rope_theta,rms_norm_epsilon,attention_dropout,
            residual_dropout,embedding_dropout,initializer_range,tie_word_embeddings,use_bias,
            pad_token_id,bos_token_id,eos_token_id,unk_token_id,tokenizer_version_id,
            parameter_count_estimate,memory_estimate_bytes,configuration_json,
            config_checksum_sha256,status,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                str(uuid4()), "micro", "v1", 64, 16, 16, 32, 1, 2, 2, 8, 10000, 1e-6, 0, 0, 0,
                0.02, 1, 0, 0, 2, 3, 1, tokenizer_id, 1000, 1000000, "{}", "d" * 64, "validated",
                ADMIN_ID,
            ),
        )
        config_id = connection.execute(
            "SELECT id FROM core_model_configs WHERE tokenizer_version_id=?", (tokenizer_id,)
        ).fetchone()[0]
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO core_model_versions(public_id,core_model_family_id,version,
            lifecycle_status,config_id,tokenizer_version_id,architecture_name,
            estimated_parameter_count,actual_parameter_count,estimated_inference_memory_bytes,
            estimated_training_memory_bytes,initialization_seed,weights_checksum_sha256,
            config_checksum_sha256,architecture_summary_json,metrics_summary_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id, core_family_id, "v0.1", "staging", config_id, tokenizer_id,
                "brud_decoder_transformer", 1064, 1064, 1000000, 2000000, 123, "e" * 64,
                "d" * 64, "{}", "{}",
            ),
        )
        connection.commit()
    return public_id


# -- RAG promotion request -----------------------------------------------------------------


def test_create_and_get_rag_promotion_request(
    repository: ProductionReadinessRepository, settings: Settings
) -> None:
    built = _accepted_rag_experiment(settings)
    space_id = _insert_knowledge_space(settings.resolved_database_path)
    report = built["experiment"]
    with sqlite3.connect(settings.resolved_database_path) as connection:
        report_public_id = connection.execute(
            "SELECT public_id FROM rag_sandbox_reports WHERE experiment_id=("
            "SELECT id FROM rag_sandbox_experiments WHERE public_id=?)",
            (report["public_id"],),
        ).fetchone()[0]
    request = repository.create_rag_promotion_request(
        {
            "promotion_code": "PRP-0001",
            "rag_sandbox_experiment_public_id": report["public_id"],
            "rag_sandbox_report_public_id": report_public_id,
            "knowledge_space_public_id": space_id,
            "selected_record_checksum_set_hash": "chk-1",
            "target_fingerprint": "fp-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    assert request["status"] == "draft"
    fetched = repository.get_rag_promotion_request(request["public_id"])
    assert fetched["promotion_code"] == "PRP-0001"

    updated = repository.update_rag_promotion_request(
        request["public_id"], {"status": "awaiting_review"}
    )
    assert updated["status"] == "awaiting_review"

    listed = repository.list_rag_promotion_requests(status="awaiting_review")
    assert any(item["public_id"] == request["public_id"] for item in listed)


def test_get_rag_promotion_request_missing_raises(
    repository: ProductionReadinessRepository,
) -> None:
    with pytest.raises(NotFoundError):
        repository.get_rag_promotion_request("does-not-exist")


# -- RAG promotion approval (immutable once approved) ----------------------------------------


def _create_promotion_request(
    settings: Settings, repository: ProductionReadinessRepository
) -> dict:
    built = _accepted_rag_experiment(settings)
    space_id = _insert_knowledge_space(settings.resolved_database_path)
    with sqlite3.connect(settings.resolved_database_path) as connection:
        report_public_id = connection.execute(
            "SELECT public_id FROM rag_sandbox_reports WHERE experiment_id=("
            "SELECT id FROM rag_sandbox_experiments WHERE public_id=?)",
            (built["experiment"]["public_id"],),
        ).fetchone()[0]
    return repository.create_rag_promotion_request(
        {
            "promotion_code": f"PRP-{uuid4().hex[:8]}",
            "rag_sandbox_experiment_public_id": built["experiment"]["public_id"],
            "rag_sandbox_report_public_id": report_public_id,
            "knowledge_space_public_id": space_id,
            "selected_record_checksum_set_hash": "chk-1",
            "target_fingerprint": "fp-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )


def test_rag_promotion_approval_lifecycle_and_immutability(
    repository: ProductionReadinessRepository, settings: Settings
) -> None:
    request = _create_promotion_request(settings, repository)
    approval = repository.create_rag_promotion_approval(
        request["public_id"],
        {"target_fingerprint": "fp-1", "requested_by_admin_public_id": ADMIN_ID},
    )
    assert approval["status"] == "pending"

    approved = repository.approve_rag_promotion_approval(
        approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
    )
    assert approved["status"] == "approved"

    with pytest.raises(ValidationError):
        repository.approve_rag_promotion_approval(
            approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
        )

    with sqlite3.connect(settings.resolved_database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE production_rag_promotion_approvals SET status='rejected' "
                "WHERE public_id=?",
                (approval["public_id"],),
            )

    expired = repository.mark_rag_promotion_approval_expired(approval["public_id"])
    assert expired["status"] == "expired"


# -- RAG release candidate / validation / activation -----------------------------------------


def test_rag_release_candidate_validation_and_activation_events(
    repository: ProductionReadinessRepository, settings: Settings
) -> None:
    request = _create_promotion_request(settings, repository)
    candidate = repository.create_rag_release_candidate(
        request["public_id"],
        {"record_checksum_set_hash": "chk-1", "created_by_admin_public_id": ADMIN_ID},
    )
    assert candidate["status"] == "building"
    assert candidate["production_visible"] is False

    updated = repository.update_rag_release_candidate(
        candidate["public_id"], {"status": "validated"}
    )
    assert updated["status"] == "validated"

    result = repository.add_rag_validation_result(
        candidate["public_id"],
        {
            "validation_type": "retrieval_smoke_test", "result_status": "passed",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    assert result["result_status"] == "passed"
    assert len(repository.list_rag_validation_results(candidate["public_id"])) == 1

    with sqlite3.connect(settings.resolved_database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE production_rag_validation_results SET result_status='failed' "
                "WHERE public_id=?",
                (result["public_id"],),
            )

    event = repository.record_rag_activation_event(
        candidate["public_id"],
        {"event_type": "activated", "performed_by_admin_public_id": ADMIN_ID},
    )
    assert event["event_type"] == "activated"
    assert len(repository.list_rag_activation_events(candidate["public_id"])) == 1


# -- model release request / approval -------------------------------------------------------


def test_model_release_request_lifecycle(
    repository: ProductionReadinessRepository, settings: Settings
) -> None:
    model_candidate_public_id = _insert_minimal_model_candidate(settings.resolved_database_path)
    request = repository.create_model_release_request(
        {
            "request_code": "PMR-0001",
            "model_candidate_public_id": model_candidate_public_id,
            "target_fingerprint": "fp-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    assert request["status"] == "draft"
    assert request["model_candidate_public_id"] == model_candidate_public_id

    updated = repository.update_model_release_request(request["public_id"], {"status": "validated"})
    assert updated["status"] == "validated"

    listed = repository.list_model_release_requests(status="validated")
    assert any(item["public_id"] == request["public_id"] for item in listed)


def test_model_release_approval_lifecycle_and_immutability(
    repository: ProductionReadinessRepository, settings: Settings
) -> None:
    model_candidate_public_id = _insert_minimal_model_candidate(settings.resolved_database_path)
    request = repository.create_model_release_request(
        {
            "request_code": "PMR-0002",
            "model_candidate_public_id": model_candidate_public_id,
            "target_fingerprint": "fp-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    approval = repository.create_model_release_approval(
        request["public_id"],
        {"target_fingerprint": "fp-1", "requested_by_admin_public_id": ADMIN_ID},
    )
    approved = repository.approve_model_release_approval(
        approval["public_id"], approved_by_admin_id=ADMIN_ID, expires_at=None
    )
    assert approved["status"] == "approved"

    with sqlite3.connect(settings.resolved_database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE production_model_release_approvals SET status='rejected' "
                "WHERE public_id=?",
                (approval["public_id"],),
            )

    latest = repository.get_latest_model_release_approval(request["public_id"])
    assert latest["public_id"] == approval["public_id"]


def test_model_activation_events_and_post_activation_checks(
    repository: ProductionReadinessRepository, settings: Settings
) -> None:
    model_candidate_public_id = _insert_minimal_model_candidate(settings.resolved_database_path)
    request = repository.create_model_release_request(
        {
            "request_code": "PMR-0003",
            "model_candidate_public_id": model_candidate_public_id,
            "target_fingerprint": "fp-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    event = repository.record_model_activation_event(
        request["public_id"],
        {"event_type": "activated", "performed_by_admin_public_id": ADMIN_ID},
    )
    assert event["event_type"] == "activated"

    check = repository.add_model_post_activation_check(
        request["public_id"],
        {
            "check_type": "runtime_health", "result_status": "passed",
            "created_by_admin_public_id": ADMIN_ID,
        },
    )
    assert check["result_status"] == "passed"
    assert len(repository.list_model_post_activation_checks(request["public_id"])) == 1


# -- rollback plans/events ---------------------------------------------------------------------


def test_rollback_plan_lifecycle_and_events(repository: ProductionReadinessRepository) -> None:
    plan = repository.create_rollback_plan(
        {"target_type": "model", "created_by_admin_public_id": ADMIN_ID}
    )
    assert plan["status"] == "draft"

    verified = repository.update_rollback_plan_status(plan["public_id"], "verified")
    assert verified["status"] == "verified"

    event = repository.record_rollback_event(
        plan["public_id"],
        {"event_type": "validated", "performed_by_admin_public_id": ADMIN_ID},
    )
    assert event["event_type"] == "validated"
    assert len(repository.list_rollback_events(plan["public_id"])) == 1

    listed = repository.list_rollback_plans(target_type="model")
    assert any(item["public_id"] == plan["public_id"] for item in listed)


# -- artifact security / backup / deployment readiness (append-only) -------------------------


def test_artifact_security_check_is_append_only(
    repository: ProductionReadinessRepository, settings: Settings
) -> None:
    check = repository.add_artifact_security_check(
        {
            "artifact_type": "checkpoint", "artifact_reference": "ckpt-1",
            "result_status": "passed", "created_by_admin_public_id": ADMIN_ID,
        }
    )
    assert check["result_status"] == "passed"
    with sqlite3.connect(settings.resolved_database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE production_artifact_security_checks SET result_status='failed' "
                "WHERE public_id=?",
                (check["public_id"],),
            )


def test_backup_readiness_check_and_latest_lookup(
    repository: ProductionReadinessRepository,
) -> None:
    repository.add_backup_readiness_check(
        {
            "check_type": "backup", "result_status": "passed",
            "latest_backup_filename": "brud_ai_before_v38_x.db",
            "created_by_admin_public_id": ADMIN_ID,
        }
    )
    second = repository.add_backup_readiness_check(
        {
            "check_type": "backup", "result_status": "passed_with_warning",
            "created_by_admin_public_id": ADMIN_ID,
        }
    )
    latest = repository.get_latest_backup_readiness_check("backup")
    assert latest["public_id"] == second["public_id"]


def test_deployment_readiness_check(repository: ProductionReadinessRepository) -> None:
    check = repository.add_deployment_readiness_check(
        {
            "result_status": "ready_with_conditions", "blocking_reasons": [],
            "created_by_admin_public_id": ADMIN_ID,
        }
    )
    assert check["result_status"] == "ready_with_conditions"
    latest = repository.get_latest_deployment_readiness_check()
    assert latest["public_id"] == check["public_id"]


# -- regression runs/results -------------------------------------------------------------------


def test_regression_run_and_results(repository: ProductionReadinessRepository) -> None:
    run = repository.create_regression_run(
        {"run_code": "REG-0001", "created_by_admin_public_id": ADMIN_ID}
    )
    assert run["status"] == "in_progress"

    result = repository.add_regression_result(
        run["public_id"],
        {
            "batch_name": "phase15_backend", "command": "pytest tests/backend -q",
            "status": "passed", "passed_count": 10, "failed_count": 0,
        },
    )
    assert result["status"] == "passed"

    finalized = repository.update_regression_run_status(run["public_id"], "completed")
    assert finalized["status"] == "completed"
    assert finalized["finalized_at"] is not None
    assert len(repository.list_regression_results(run["public_id"])) == 1


# -- readiness reports / acceptance reviews / events ------------------------------------------


def test_readiness_report_versioning_and_acceptance(
    repository: ProductionReadinessRepository,
) -> None:
    report = repository.add_readiness_report(
        {
            "report": {"summary": "test"}, "report_checksum_sha256": "chk-report-1",
            "recommendation": "ready_with_conditions",
            "finalized_by_admin_public_id": ADMIN_ID,
        }
    )
    assert report["report_version"] == 1

    second = repository.add_readiness_report(
        {
            "report": {"summary": "test 2"}, "report_checksum_sha256": "chk-report-2",
            "recommendation": "not_ready",
            "finalized_by_admin_public_id": ADMIN_ID,
        }
    )
    assert second["report_version"] == 2
    assert repository.get_latest_readiness_report()["public_id"] == second["public_id"]

    review = repository.add_acceptance_review(
        report["public_id"],
        {
            "decision": "accepted_with_conditions", "reason": "meets bar",
            "reviewer_admin_public_id": ADMIN_ID, "report_checksum": "chk-report-1",
            "target_fingerprint": "fp-1",
        },
    )
    assert review["decision"] == "accepted_with_conditions"
    with sqlite3.connect(repository.database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE production_acceptance_reviews SET decision='rejected' WHERE public_id=?",
                (review["public_id"],),
            )


def test_readiness_events_are_append_only(
    repository: ProductionReadinessRepository, settings: Settings
) -> None:
    event = repository.record_readiness_event(
        {
            "event_type": "check_run", "resource_type": "artifact_security_check",
            "resource_public_id": "x", "performed_by_admin_public_id": ADMIN_ID,
        }
    )
    with sqlite3.connect(settings.resolved_database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE production_readiness_events SET event_type='other' WHERE public_id=?",
                (event["public_id"],),
            )
    assert len(repository.list_readiness_events()) == 1


def test_overview_counts_reflect_real_state(repository: ProductionReadinessRepository) -> None:
    counts = repository.overview_counts()
    assert counts["rag_promotions_awaiting_approval"] == 0
    assert set(counts) == {
        "rag_promotions_awaiting_approval", "rag_candidates_awaiting_validation",
        "rag_activations_pending", "model_releases_awaiting_validation",
        "model_releases_awaiting_approval", "canaries_running", "activation_failures",
        "rollback_readiness_failures", "artifact_security_failures", "backups_out_of_date",
        "regression_batches_failing", "readiness_reports_awaiting_acceptance",
        "backups_not_encrypted",
    }
