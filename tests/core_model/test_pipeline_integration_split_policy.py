from __future__ import annotations

from core_model.pipeline_integration.split_policy import (
    excluded_by_prior_evaluation_build,
    missing_grouping_metadata_warning,
    split_configuration_for_target,
)


def test_rag_and_dataset_version_targets_force_full_train_split():
    expected = {"train_percent": 100, "validation_percent": 0, "test_percent": 0, "seed": None}
    for target in ("dataset_version", "rag", "tokenizer", "commercial_release", "public_export"):
        assert split_configuration_for_target(target) == expected


def test_evaluation_target_forces_full_test_split():
    config = split_configuration_for_target("evaluation")
    expected = {"train_percent": 0, "validation_percent": 0, "test_percent": 100, "seed": None}
    assert config == expected


def test_pretraining_target_honors_requested_split():
    requested = {"train_percent": 80, "validation_percent": 10, "test_percent": 10, "seed": 7}
    config = split_configuration_for_target("pretraining", requested=requested)
    assert config == requested


def test_pretraining_target_defaults_when_no_split_requested():
    config = split_configuration_for_target("instruction_tuning")
    assert config["train_percent"] == 90
    assert config["validation_percent"] == 5
    assert config["test_percent"] == 5


def test_rag_target_ignores_a_requested_split_and_forces_full_train():
    requested = {"train_percent": 50, "validation_percent": 25, "test_percent": 25, "seed": 1}
    config = split_configuration_for_target("rag", requested=requested)
    assert config["train_percent"] == 100


def test_excluded_by_prior_evaluation_build():
    prior = frozenset({"rec-1", "rec-2"})
    assert excluded_by_prior_evaluation_build("rec-1", prior_evaluation_entity_ids=prior) is True
    assert excluded_by_prior_evaluation_build("rec-3", prior_evaluation_entity_ids=prior) is False


def test_missing_grouping_metadata_warning_present_when_no_grouping_signal():
    warning = missing_grouping_metadata_warning(
        has_document_group=False, has_semantic_family_group=False, has_translation_group=False
    )
    assert warning is not None
    assert "grouping" in warning


def test_missing_grouping_metadata_warning_absent_when_any_signal_present():
    assert missing_grouping_metadata_warning(
        has_document_group=True, has_semantic_family_group=False, has_translation_group=False
    ) is None
    assert missing_grouping_metadata_warning(
        has_document_group=False, has_semantic_family_group=True, has_translation_group=False
    ) is None
    assert missing_grouping_metadata_warning(
        has_document_group=False, has_semantic_family_group=False, has_translation_group=True
    ) is None
