"""Operator CLI for Phase 21A: tokenizer corpus builds, tokenizer
candidate training/evaluation/comparison/activation, base-model
resource estimates, pretraining dataset snapshots, training
configuration validation, tiny bounded smoke runs, and the base-model
readiness gate.

Every command operates on public IDs only. Commands that trigger real
processing (tokenizer training, smoke runs) require a typed
confirmation before proceeding.
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.core_models import CoreModelRepository
from backend.database.repositories.corpus import CorpusRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.pretraining_readiness import PretrainingReadinessRepository
from backend.models.pretraining_readiness import (
    BaseModelReadinessEvaluationCreate,
    PretrainingSnapshotCreate,
    ResourceEstimateCreate,
    SmokeRunCreate,
    TokenizerApprovalRequest,
    TokenizerCandidateComparisonCreate,
    TokenizerCorpusBuildCreate,
    TrainingConfigValidateRequest,
)
from backend.services.base_model_readiness_service import BaseModelReadinessService
from backend.services.base_model_resource_service import BaseModelResourceService
from backend.services.pretraining_smoke_service import PretrainingSmokeService
from backend.services.pretraining_snapshot_service import PretrainingSnapshotService
from backend.services.tokenizer_candidate_service import TokenizerCandidateService
from backend.services.tokenizer_corpus_service import TokenizerCorpusService

CLI_ADMIN_ID = "00000000-0000-0000-0000-0000000000fb"


def _settings():
    return get_settings()


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def _confirm(prompt: str, word: str) -> bool:
    return input(f"{prompt} Type '{word}' to confirm: ").strip().lower() == word


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Brud AI Phase 21A tokenizer/pretraining readiness CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_tc_parser = subparsers.add_parser("build-tokenizer-corpus")
    build_tc_parser.add_argument("corpus_release_public_id")

    subparsers.add_parser("analyze-tokenizer-corpus").add_argument("build_public_id")

    candidate_parser = subparsers.add_parser("create-tokenizer-candidate")
    candidate_parser.add_argument("tokenizer_corpus_build_public_id")
    candidate_parser.add_argument("--vocab-size", type=int, action="append", required=True)

    subparsers.add_parser("get-tokenizer-comparison").add_argument("comparison_public_id")

    approve_parser = subparsers.add_parser("approve-tokenizer")
    approve_parser.add_argument("comparison_public_id")
    approve_parser.add_argument("tokenizer_version_public_id")

    activate_parser = subparsers.add_parser("activate-tokenizer")
    activate_parser.add_argument("tokenizer_version_public_id")

    estimate_parser = subparsers.add_parser("estimate-model-resources")
    estimate_parser.add_argument(
        "--profile", required=True,
        choices=["micro_smoke_test", "small_experimental", "maximum_safe_local"],
    )
    estimate_parser.add_argument("--vocab-size", type=int, required=True)

    snapshot_parser = subparsers.add_parser("create-pretraining-snapshot")
    snapshot_parser.add_argument("corpus_release_public_id")
    snapshot_parser.add_argument("tokenizer_version_public_id")
    snapshot_parser.add_argument("--max-sequence-length", type=int, default=512)

    subparsers.add_parser("verify-pretraining-snapshot").add_argument("snapshot_public_id")

    validate_parser = subparsers.add_parser("validate-pretraining-config")
    validate_parser.add_argument("snapshot_public_id")
    validate_parser.add_argument("estimate_public_id")
    validate_parser.add_argument("--total-steps", type=int, default=20)

    smoke_parser = subparsers.add_parser("run-pretraining-smoke")
    smoke_parser.add_argument("snapshot_public_id")
    smoke_parser.add_argument("estimate_public_id")
    smoke_parser.add_argument("--total-steps", type=int, default=20)

    subparsers.add_parser("get-pretraining-smoke").add_argument("smoke_run_public_id")

    verify_ckpt_parser = subparsers.add_parser("verify-checkpoint")
    verify_ckpt_parser.add_argument("checkpoint_public_id")

    readiness_parser = subparsers.add_parser("evaluate-base-model-readiness")
    readiness_parser.add_argument("snapshot_public_id")
    readiness_parser.add_argument("--comparison")
    readiness_parser.add_argument("--estimate")
    readiness_parser.add_argument("--smoke-run")

    args = parser.parse_args(argv)

    settings = _settings()
    readiness_repo = PretrainingReadinessRepository(settings.resolved_database_path)
    corpus_repo = CorpusRepository(settings.resolved_database_path)
    core_model_repo = CoreModelRepository(settings.resolved_database_path)
    pretraining_repo = PretrainingRepository(settings.resolved_database_path)

    tokenizer_corpus_svc = TokenizerCorpusService(corpus_repo, readiness_repo, settings)
    tokenizer_candidate_svc = TokenizerCandidateService(readiness_repo, settings)
    resource_svc = BaseModelResourceService(readiness_repo, settings)
    snapshot_svc = PretrainingSnapshotService(corpus_repo, readiness_repo, settings)
    smoke_svc = PretrainingSmokeService(readiness_repo, core_model_repo, pretraining_repo, settings)
    readiness_svc = BaseModelReadinessService(
        readiness_repo, corpus_repo, pretraining_repo, settings
    )

    try:
        if args.command == "build-tokenizer-corpus":
            _print(
                tokenizer_corpus_svc.build_corpus(
                    TokenizerCorpusBuildCreate(
                        corpus_release_public_id=args.corpus_release_public_id
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "analyze-tokenizer-corpus":
            _print(tokenizer_corpus_svc.get_build(args.build_public_id))
        elif args.command == "create-tokenizer-candidate":
            if not _confirm(
                f"About to train {len(args.vocab_size)} tokenizer candidate(s) from "
                f"corpus build {args.tokenizer_corpus_build_public_id}.",
                "train",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                tokenizer_candidate_svc.create_comparison(
                    TokenizerCandidateComparisonCreate(
                        tokenizer_corpus_build_public_id=args.tokenizer_corpus_build_public_id,
                        vocabulary_sizes=args.vocab_size,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "get-tokenizer-comparison":
            _print(tokenizer_candidate_svc.get_comparison(args.comparison_public_id))
        elif args.command == "approve-tokenizer":
            _print(
                tokenizer_candidate_svc.approve(
                    args.comparison_public_id,
                    TokenizerApprovalRequest(
                        tokenizer_version_public_id=args.tokenizer_version_public_id
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "activate-tokenizer":
            if not _confirm(
                f"About to activate tokenizer {args.tokenizer_version_public_id}.", "activate"
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                tokenizer_candidate_svc.activate(args.tokenizer_version_public_id, CLI_ADMIN_ID)
            )
        elif args.command == "estimate-model-resources":
            _print(
                resource_svc.create_estimate(
                    ResourceEstimateCreate(
                        profile_name=args.profile, vocabulary_size=args.vocab_size
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-pretraining-snapshot":
            _print(
                snapshot_svc.create_snapshot(
                    PretrainingSnapshotCreate(
                        corpus_release_public_id=args.corpus_release_public_id,
                        tokenizer_version_public_id=args.tokenizer_version_public_id,
                        maximum_sequence_length=args.max_sequence_length,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "verify-pretraining-snapshot":
            _print(snapshot_svc.get_snapshot(args.snapshot_public_id))
        elif args.command == "validate-pretraining-config":
            _print(
                smoke_svc.validate_training_config(
                    TrainingConfigValidateRequest(
                        pretraining_dataset_snapshot_public_id=args.snapshot_public_id,
                        base_model_resource_estimate_public_id=args.estimate_public_id,
                        configuration={"total_steps": args.total_steps},
                    )
                )
            )
        elif args.command == "run-pretraining-smoke":
            if not _confirm(
                f"About to run a {args.total_steps}-step bounded pretraining smoke test.", "smoke"
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                smoke_svc.create_smoke_run(
                    SmokeRunCreate(
                        pretraining_dataset_snapshot_public_id=args.snapshot_public_id,
                        base_model_resource_estimate_public_id=args.estimate_public_id,
                        total_steps=args.total_steps,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "get-pretraining-smoke":
            _print(smoke_svc.get_smoke_run(args.smoke_run_public_id))
        elif args.command == "verify-checkpoint":
            from backend.services.pretraining_service import PretrainingService

            _print(
                PretrainingService(pretraining_repo, settings).verify_checkpoint(
                    args.checkpoint_public_id, CLI_ADMIN_ID
                )
            )
        elif args.command == "evaluate-base-model-readiness":
            _print(
                readiness_svc.evaluate(
                    BaseModelReadinessEvaluationCreate(
                        pretraining_dataset_snapshot_public_id=args.snapshot_public_id,
                        tokenizer_candidate_comparison_public_id=args.comparison,
                        base_model_resource_estimate_public_id=args.estimate,
                        pretraining_smoke_run_public_id=args.smoke_run,
                    ),
                    CLI_ADMIN_ID,
                )
            )
    except RepositoryError as exc:
        print(f"Pretraining readiness command failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
