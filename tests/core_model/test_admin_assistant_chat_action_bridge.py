"""MB-39: pure tests for core_model.admin_assistant.chat_action_bridge."""

from __future__ import annotations

from core_model.admin_assistant.chat_action_bridge import (
    CHAT_ACTION_SCOPES,
    match_actionable_intent,
)


def test_import_dataset_matches_external_provider_scope() -> None:
    match = match_actionable_intent("Please import dataset from a new source")
    assert match is not None
    assert match.scope == "dataset.import.external"
    assert match.action_type == "register_external_data_provider"


def test_external_provider_keyword_matches_same_scope() -> None:
    match = match_actionable_intent("I want to use an external provider")
    assert match is not None
    assert match.scope == "dataset.import.external"


def test_clean_dataset_matches_dataset_clean_scope() -> None:
    match = match_actionable_intent("Can you clean dataset records for this import?")
    assert match is not None
    assert match.scope == "dataset.clean"
    assert match.action_type == "run_sample_quality_checks"


def test_build_rag_matches_rag_build_scope() -> None:
    match = match_actionable_intent("Let's build rag for this sandbox")
    assert match is not None
    assert match.scope == "rag.build"
    assert match.action_type == "build_rag_sandbox_index"


def test_rag_test_matches_rag_evaluate_scope() -> None:
    match = match_actionable_intent("Run a rag test against the index")
    assert match is not None
    assert match.scope == "rag.evaluate"
    assert match.action_type == "run_rag_sandbox_evaluation"


def test_ambiguous_message_matches_nothing() -> None:
    assert match_actionable_intent("What's the weather like today?") is None
    assert match_actionable_intent("Tell me about this dashboard") is None


def test_training_language_never_matches_even_with_a_scope_keyword() -> None:
    # "clean dataset" would otherwise match dataset.clean -- the presence
    # of "train" anywhere in the message must still block it.
    assert match_actionable_intent("clean dataset then start training") is None
    assert match_actionable_intent("pretrain the model and build rag") is None


def test_every_scope_action_type_matches_the_public_mapping() -> None:
    for scope, action_type in CHAT_ACTION_SCOPES.items():
        message = {
            "dataset.import.external": "import dataset now",
            "dataset.clean": "clean dataset please",
            "rag.build": "build rag index",
            "rag.evaluate": "rag test please",
        }[scope]
        match = match_actionable_intent(message)
        assert match is not None
        assert match.action_type == action_type
