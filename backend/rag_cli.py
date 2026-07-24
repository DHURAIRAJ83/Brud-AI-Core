"""Operator CLI for Phase 16 RAG knowledge ingestion, hybrid retrieval,
grounded generation, and evaluation.

Every command operates on public IDs only. Commands that change a
production-facing pointer (activating an index) require a typed
confirmation before proceeding, matching the Phase 14/15 CLI convention.
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.rag import RagRepository
from backend.models.rag import (
    ChunkSetCreate,
    EmbeddingModelCreate,
    EmbeddingRunCreate,
    EvaluationFixtureCreate,
    EvaluationRunCreate,
    EvaluationSuiteCreate,
    GroundedAnswerRequest,
    KeywordIndexCreate,
    KnowledgeSourceCreate,
    KnowledgeSourcePatch,
    KnowledgeSpaceCreate,
    RetrievalFiltersPayload,
    RetrievalProfileCreate,
    RetrieveRequest,
    VectorIndexCreate,
)
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService
from backend.services.rag_evaluation_service import RagEvaluationService
from backend.services.rag_generation_service import RagGenerationService
from backend.services.rag_ingestion_service import RagIngestionService
from backend.services.rag_retrieval_service import RagRetrievalService

CLI_ADMIN_ID = "00000000-0000-0000-0000-0000000000fa"


def _ingestion() -> RagIngestionService:
    settings = get_settings()
    return RagIngestionService(RagRepository(settings.resolved_database_path), settings)


def _retrieval() -> RagRetrievalService:
    settings = get_settings()
    return RagRetrievalService(RagRepository(settings.resolved_database_path), settings)


def _generation() -> RagGenerationService:
    settings = get_settings()
    inference_repository = InferenceRuntimeRepository(settings.resolved_database_path)
    release_repository = ModelReleaseRepository(settings.resolved_database_path)
    runtime_service = InferenceRuntimeService(inference_repository, release_repository, settings)
    assignment_service = ModelAssignmentService(
        inference_repository, release_repository, runtime_service, settings
    )
    return RagGenerationService(
        RagRepository(settings.resolved_database_path),
        inference_repository,
        runtime_service,
        assignment_service,
        _retrieval(),
        settings,
    )


def _evaluation() -> RagEvaluationService:
    settings = get_settings()
    return RagEvaluationService(
        RagRepository(settings.resolved_database_path), _retrieval(), _generation(), settings
    )


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def _confirm(prompt: str, word: str) -> bool:
    return input(f"{prompt} Type '{word}' to confirm: ").strip().lower() == word


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI RAG (grounded retrieval) CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("spaces")
    create_space_parser = subparsers.add_parser("create-space")
    create_space_parser.add_argument("--name", required=True)
    create_space_parser.add_argument("--slug", required=True)

    create_source_parser = subparsers.add_parser("create-source")
    create_source_parser.add_argument("space_public_id")
    create_source_parser.add_argument("--type", dest="source_type", required=True)
    create_source_parser.add_argument("--title", required=True)
    create_source_parser.add_argument("--language", default="unknown")
    create_source_parser.add_argument("--licence-status", default="unknown")
    create_source_parser.add_argument("--content-file", default=None)
    create_source_parser.add_argument("--source-entity", default=None)

    patch_source_parser = subparsers.add_parser("patch-source")
    patch_source_parser.add_argument("source_public_id")
    patch_source_parser.add_argument("--approval-status", default=None)
    patch_source_parser.add_argument("--licence-status", default=None)

    create_version_parser = subparsers.add_parser("create-version")
    create_version_parser.add_argument("source_public_id")

    create_chunk_set_parser = subparsers.add_parser("create-chunk-set")
    create_chunk_set_parser.add_argument("source_version_public_id")
    create_chunk_set_parser.add_argument("--strategy", default="heading_aware")

    create_embedding_model_parser = subparsers.add_parser("create-embedding-model")
    create_embedding_model_parser.add_argument("--name", required=True)
    create_embedding_model_parser.add_argument("--version", required=True)
    create_embedding_model_parser.add_argument("--provider", required=True)
    create_embedding_model_parser.add_argument("--dimensions", type=int, required=True)
    create_embedding_model_parser.add_argument("--max-input-tokens", type=int, default=512)

    run_embeddings_parser = subparsers.add_parser("run-embeddings")
    run_embeddings_parser.add_argument("chunk_set_public_id")
    run_embeddings_parser.add_argument("--model", dest="embedding_model_public_id", required=True)

    build_indexes_parser = subparsers.add_parser("build-indexes")
    build_indexes_parser.add_argument("--embedding-run", required=True)
    build_indexes_parser.add_argument("--chunk-set", required=True)

    create_profile_parser = subparsers.add_parser("create-retrieval-profile")
    create_profile_parser.add_argument("space_public_id")
    create_profile_parser.add_argument("--name", required=True)

    retrieve_parser = subparsers.add_parser("retrieve")
    retrieve_parser.add_argument("--profile", dest="retrieval_profile_public_id", required=True)
    retrieve_parser.add_argument("--query", required=True)

    grounded_answer_parser = subparsers.add_parser("grounded-answer")
    grounded_answer_parser.add_argument(
        "--profile", dest="retrieval_profile_public_id", required=True
    )
    grounded_answer_parser.add_argument("--assignment", dest="assignment_public_id", required=True)
    grounded_answer_parser.add_argument("--query", required=True)

    create_suite_parser = subparsers.add_parser("create-evaluation-suite")
    create_suite_parser.add_argument("space_public_id")
    create_suite_parser.add_argument("--name", required=True)
    create_suite_parser.add_argument("--version", required=True)
    create_suite_parser.add_argument("--type", dest="evaluation_type", default="retrieval")

    add_fixture_parser = subparsers.add_parser("add-fixture")
    add_fixture_parser.add_argument("suite_public_id")
    add_fixture_parser.add_argument("--query", required=True)
    add_fixture_parser.add_argument("--language", default="unknown")
    add_fixture_parser.add_argument("--relevant-chunks", default="")
    add_fixture_parser.add_argument("--expected-no-answer", action="store_true")

    run_evaluation_parser = subparsers.add_parser("run-evaluation")
    run_evaluation_parser.add_argument("suite_public_id")
    run_evaluation_parser.add_argument(
        "--profile", dest="retrieval_profile_public_id", default=None
    )
    run_evaluation_parser.add_argument("--assignment", dest="assignment_public_id", default=None)

    manifest_parser = subparsers.add_parser("generate-manifest")
    manifest_parser.add_argument("space_public_id")
    verify_manifest_parser = subparsers.add_parser("verify-manifest")
    verify_manifest_parser.add_argument("space_public_id")

    args = parser.parse_args(argv)

    try:
        if args.command == "spaces":
            _print(_ingestion().list_spaces())
        elif args.command == "create-space":
            _print(
                _ingestion().create_space(
                    KnowledgeSpaceCreate(name=args.name, slug=args.slug), CLI_ADMIN_ID
                )
            )
        elif args.command == "create-source":
            content = None
            if args.content_file:
                with open(args.content_file, encoding="utf-8") as handle:
                    content = handle.read()
            _print(
                _ingestion().create_source(
                    args.space_public_id,
                    KnowledgeSourceCreate(
                        source_type=args.source_type,
                        title=args.title,
                        language=args.language,
                        licence_status=args.licence_status,
                        content=content,
                        source_entity_public_id=args.source_entity,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "patch-source":
            _print(
                _ingestion().patch_source(
                    args.source_public_id,
                    KnowledgeSourcePatch(
                        approval_status=args.approval_status,
                        licence_status=args.licence_status,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-version":
            _print(_ingestion().create_source_version(args.source_public_id, CLI_ADMIN_ID))
        elif args.command == "create-chunk-set":
            _print(
                _ingestion().create_chunk_set(
                    args.source_version_public_id,
                    ChunkSetCreate(chunking_strategy=args.strategy),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-embedding-model":
            _print(
                _ingestion().create_embedding_model(
                    EmbeddingModelCreate(
                        name=args.name,
                        version=args.version,
                        provider_type=args.provider,
                        dimensions=args.dimensions,
                        maximum_input_tokens=args.max_input_tokens,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "run-embeddings":
            ingestion = _ingestion()
            run = ingestion.create_embedding_run(
                args.chunk_set_public_id,
                EmbeddingRunCreate(embedding_model_public_id=args.embedding_model_public_id),
                CLI_ADMIN_ID,
            )
            _print(ingestion.execute_embedding_run(run["public_id"], CLI_ADMIN_ID))
        elif args.command == "build-indexes":
            if not _confirm(
                "About to build and activate vector/keyword indexes, deprecating any prior "
                "active index for this knowledge space.",
                "build-indexes",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            ingestion = _ingestion()
            vector_index = ingestion.create_vector_index(
                args.embedding_run, VectorIndexCreate(), CLI_ADMIN_ID
            )
            vector_index = ingestion.build_vector_index(vector_index["public_id"], CLI_ADMIN_ID)
            vector_index = ingestion.validate_vector_index(
                vector_index["public_id"], CLI_ADMIN_ID
            )
            vector_index = ingestion.activate_vector_index(
                vector_index["public_id"], CLI_ADMIN_ID
            )
            keyword_index = ingestion.create_keyword_index(
                args.chunk_set, KeywordIndexCreate(), CLI_ADMIN_ID
            )
            keyword_index = ingestion.build_keyword_index(
                keyword_index["public_id"], CLI_ADMIN_ID
            )
            keyword_index = ingestion.validate_keyword_index(
                keyword_index["public_id"], CLI_ADMIN_ID
            )
            keyword_index = ingestion.activate_keyword_index(
                keyword_index["public_id"], CLI_ADMIN_ID
            )
            _print({"vector_index": vector_index, "keyword_index": keyword_index})
        elif args.command == "create-retrieval-profile":
            retrieval = _retrieval()
            profile = retrieval.create_profile(
                args.space_public_id, RetrievalProfileCreate(name=args.name), CLI_ADMIN_ID
            )
            profile = retrieval.validate_profile(profile["public_id"], CLI_ADMIN_ID)
            profile = retrieval.activate_profile(profile["public_id"], CLI_ADMIN_ID)
            _print(profile)
        elif args.command == "retrieve":
            _print(
                _retrieval().retrieve(
                    RetrieveRequest(
                        retrieval_profile_public_id=args.retrieval_profile_public_id,
                        query=args.query,
                        filters=RetrievalFiltersPayload(),
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "grounded-answer":
            _print(
                _generation().grounded_answer(
                    GroundedAnswerRequest(
                        retrieval_profile_public_id=args.retrieval_profile_public_id,
                        assignment_public_id=args.assignment_public_id,
                        query=args.query,
                        filters=RetrievalFiltersPayload(),
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-evaluation-suite":
            _print(
                _evaluation().create_suite(
                    args.space_public_id,
                    EvaluationSuiteCreate(
                        name=args.name, version=args.version, evaluation_type=args.evaluation_type
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "add-fixture":
            relevant_chunks = [
                chunk_id.strip() for chunk_id in args.relevant_chunks.split(",") if chunk_id.strip()
            ]
            _print(
                _evaluation().add_fixture(
                    args.suite_public_id,
                    EvaluationFixtureCreate(
                        query=args.query,
                        language=args.language,
                        expected_relevant_chunk_ids=relevant_chunks,
                        expected_no_answer=args.expected_no_answer,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "run-evaluation":
            evaluation = _evaluation()
            run = evaluation.create_run(
                args.suite_public_id,
                EvaluationRunCreate(
                    retrieval_profile_public_id=args.retrieval_profile_public_id,
                    assignment_public_id=args.assignment_public_id,
                ),
                CLI_ADMIN_ID,
            )
            _print(evaluation.execute_run(run["public_id"], CLI_ADMIN_ID))
        elif args.command == "generate-manifest":
            _print(_evaluation().generate_manifest(args.space_public_id, CLI_ADMIN_ID))
        elif args.command == "verify-manifest":
            result = _evaluation().verify_manifest(args.space_public_id)
            _print(result)
            return 0 if result["matches"] else 1
    except RepositoryError as exc:
        print(f"RAG command failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
