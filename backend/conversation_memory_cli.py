"""Operator CLI for Phase 17 conversation memory, sessions, consent,
memory items, memory retrieval, and evaluation.

Every command operates on public IDs only. Mutating commands require a
typed confirmation before proceeding.
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.conversation_memory import ConversationMemoryRepository
from backend.models.conversation_memory import (
    ConsentCreate,
    EvaluationRunCreate,
    MemoryItemCorrect,
    MemoryItemCreate,
    MemoryPolicyCreate,
    MemoryRetrieveRequest,
    MessageCreate,
    SessionCreate,
    SummaryCreate,
)
from backend.services.conversation_session_service import ConversationSessionService
from backend.services.memory_evaluation_service import MemoryEvaluationService
from backend.services.memory_service import MemoryService

CLI_ADMIN_ID = "00000000-0000-0000-0000-0000000000fb"


def _sessions() -> ConversationSessionService:
    settings = get_settings()
    return ConversationSessionService(
        ConversationMemoryRepository(settings.resolved_database_path), settings
    )


def _memory() -> MemoryService:
    settings = get_settings()
    return MemoryService(ConversationMemoryRepository(settings.resolved_database_path), settings)


def _evaluation() -> MemoryEvaluationService:
    settings = get_settings()
    return MemoryEvaluationService(
        ConversationMemoryRepository(settings.resolved_database_path), _memory(), settings
    )


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def _confirm(prompt: str, word: str) -> bool:
    return input(f"{prompt} Type '{word}' to confirm: ").strip().lower() == word


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI conversation memory CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("policies")

    create_policy_parser = subparsers.add_parser("create-policy")
    create_policy_parser.add_argument("--name", required=True)
    create_policy_parser.add_argument("--default-session-mode", default="private_no_persist")
    create_policy_parser.add_argument("--allow-long-term-memory", action="store_true")

    create_session_parser = subparsers.add_parser("create-session")
    create_session_parser.add_argument("--policy", dest="memory_policy_public_id", required=True)
    create_session_parser.add_argument("--mode", dest="session_mode", required=True)
    create_session_parser.add_argument("--participant", dest="participant_scope_key", required=True)

    inspect_session_parser = subparsers.add_parser("inspect-session")
    inspect_session_parser.add_argument("session_public_id")

    send_message_parser = subparsers.add_parser("send-message")
    send_message_parser.add_argument("session_public_id")
    send_message_parser.add_argument("--message", required=True)
    send_message_parser.add_argument(
        "--memory-profile", dest="memory_retrieval_profile_public_id", default=None
    )

    create_summary_parser = subparsers.add_parser("create-summary")
    create_summary_parser.add_argument("session_public_id")

    grant_consent_parser = subparsers.add_parser("grant-consent")
    grant_consent_parser.add_argument("--participant", dest="participant_scope_key", required=True)
    grant_consent_parser.add_argument("--policy", dest="memory_policy_public_id", required=True)
    grant_consent_parser.add_argument("--purpose", required=True)

    revoke_consent_parser = subparsers.add_parser("revoke-consent")
    revoke_consent_parser.add_argument("consent_public_id")

    propose_memory_parser = subparsers.add_parser("propose-memory")
    propose_memory_parser.add_argument("--participant", dest="participant_scope_key", required=True)
    propose_memory_parser.add_argument("--category", required=True)
    propose_memory_parser.add_argument("--purpose", required=True)
    propose_memory_parser.add_argument(
        "--source", dest="creation_source", default="explicit_user_request"
    )
    propose_memory_parser.add_argument(
        "--confidence", dest="confidence_type", default="user_confirmed"
    )
    propose_memory_parser.add_argument("--value", dest="display_value", required=True)
    propose_memory_parser.add_argument("--consent", dest="consent_public_id", default=None)

    confirm_memory_parser = subparsers.add_parser("confirm-memory")
    confirm_memory_parser.add_argument("memory_public_id")

    correct_memory_parser = subparsers.add_parser("correct-memory")
    correct_memory_parser.add_argument("memory_public_id")
    correct_memory_parser.add_argument("--value", dest="display_value", required=True)
    correct_memory_parser.add_argument("--reason", dest="change_reason", required=True)

    delete_memory_parser = subparsers.add_parser("delete-memory")
    delete_memory_parser.add_argument("memory_public_id")

    retrieve_memory_parser = subparsers.add_parser("retrieve-memory")
    retrieve_memory_parser.add_argument(
        "--profile", dest="retrieval_profile_public_id", required=True
    )
    retrieve_memory_parser.add_argument(
        "--participant", dest="participant_scope_key", required=True
    )
    retrieve_memory_parser.add_argument("--query", required=True)

    evaluate_parser = subparsers.add_parser("evaluate")
    evaluate_parser.add_argument("suite_public_id")
    evaluate_parser.add_argument("--profile", dest="retrieval_profile_public_id", default=None)

    verify_manifest_parser = subparsers.add_parser("verify-manifest")
    verify_manifest_parser.add_argument("policy_public_id")

    args = parser.parse_args(argv)

    try:
        if args.command == "policies":
            _print(_sessions().list_policies())
        elif args.command == "create-policy":
            if not _confirm(f"About to create memory policy '{args.name}'.", "create-policy"):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                _sessions().create_policy(
                    MemoryPolicyCreate(
                        name=args.name,
                        default_session_mode=args.default_session_mode,
                        allow_long_term_memory=args.allow_long_term_memory,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-session":
            _print(
                _sessions().create_session(
                    SessionCreate(
                        session_mode=args.session_mode,
                        memory_policy_public_id=args.memory_policy_public_id,
                        participant_scope_key=args.participant_scope_key,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "inspect-session":
            session = _sessions().get_session(args.session_public_id)
            turns = _sessions().list_turns(args.session_public_id)
            _print({"session": session, "turns": turns})
        elif args.command == "send-message":
            from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
            from backend.database.repositories.model_release import ModelReleaseRepository
            from backend.database.repositories.rag import RagRepository
            from backend.services.chat_orchestration_service import ChatOrchestrationService
            from backend.services.inference_runtime_service import InferenceRuntimeService
            from backend.services.model_assignment_service import ModelAssignmentService
            from backend.services.rag_retrieval_service import RagRetrievalService

            settings = get_settings()
            inference_repository = InferenceRuntimeRepository(settings.resolved_database_path)
            release_repository = ModelReleaseRepository(settings.resolved_database_path)
            runtime_service = InferenceRuntimeService(
                inference_repository, release_repository, settings
            )
            assignment_service = ModelAssignmentService(
                inference_repository, release_repository, runtime_service, settings
            )
            rag_retrieval = RagRetrievalService(
                RagRepository(settings.resolved_database_path), settings
            )
            orchestration = ChatOrchestrationService(
                ConversationMemoryRepository(settings.resolved_database_path),
                inference_repository, runtime_service, assignment_service,
                _sessions(), _memory(), rag_retrieval, settings,
            )
            _print(
                orchestration.send_message(
                    args.session_public_id,
                    MessageCreate(
                        message=args.message,
                        memory_retrieval_profile_public_id=args.memory_retrieval_profile_public_id,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-summary":
            _print(
                _sessions().create_summary(
                    args.session_public_id, SummaryCreate(), CLI_ADMIN_ID
                )
            )
        elif args.command == "grant-consent":
            _print(
                _memory().create_consent(
                    ConsentCreate(
                        participant_scope_key=args.participant_scope_key,
                        memory_policy_public_id=args.memory_policy_public_id,
                        purpose=args.purpose,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "revoke-consent":
            if not _confirm(
                f"About to revoke consent {args.consent_public_id}, "
                "blocking future memory retrieval.",
                "revoke",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(_memory().revoke_consent(args.consent_public_id, CLI_ADMIN_ID))
        elif args.command == "propose-memory":
            _print(
                _memory().propose_memory(
                    MemoryItemCreate(
                        participant_scope_key=args.participant_scope_key,
                        category=args.category,
                        purpose=args.purpose,
                        creation_source=args.creation_source,
                        confidence_type=args.confidence_type,
                        display_value=args.display_value,
                        consent_public_id=args.consent_public_id,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "confirm-memory":
            _print(_memory().confirm_memory(args.memory_public_id, CLI_ADMIN_ID))
        elif args.command == "correct-memory":
            _print(
                _memory().correct_memory(
                    args.memory_public_id,
                    MemoryItemCorrect(
                        display_value=args.display_value, change_reason=args.change_reason
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "delete-memory":
            if not _confirm(
                f"About to delete memory {args.memory_public_id}. This cannot be undone.", "delete"
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(_memory().delete_memory(args.memory_public_id, CLI_ADMIN_ID))
        elif args.command == "retrieve-memory":
            _print(
                _memory().retrieve(
                    MemoryRetrieveRequest(
                        retrieval_profile_public_id=args.retrieval_profile_public_id,
                        participant_scope_key=args.participant_scope_key,
                        query=args.query,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "evaluate":
            evaluation = _evaluation()
            run = evaluation.create_run(
                args.suite_public_id,
                EvaluationRunCreate(retrieval_profile_public_id=args.retrieval_profile_public_id),
                CLI_ADMIN_ID,
            )
            _print(evaluation.execute_run(run["public_id"], CLI_ADMIN_ID))
        elif args.command == "verify-manifest":
            result = _evaluation().verify_manifest(args.policy_public_id)
            _print(result)
            return 0 if result["matches"] else 1
    except RepositoryError as exc:
        print(f"Conversation memory command failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
