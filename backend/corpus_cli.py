"""Operator CLI for Phase 19 Tamil corpus builder: source registry,
licence governance, extraction/normalization/segmentation, quality/
privacy/safety/deduplication/contamination, collections, builds,
versions, exports, manifests, and comparisons.

Every command operates on public IDs only. Commands that trigger real
processing (extraction, normalization, deduplication, builds, exports)
require a typed confirmation before proceeding.
"""

from __future__ import annotations

import argparse
import json
import sys

from backend.core.config import get_settings
from backend.database.repositories.base import RepositoryError
from backend.database.repositories.corpus import CorpusRepository
from backend.models.corpus import (
    BalancePolicyCreate,
    BuildCreate,
    CollectionCreate,
    ContaminationRunCreate,
    CorpusCompareRequest,
    CorpusPolicyCreate,
    DeduplicationRunCreate,
    ExportCreate,
    ExtractionRunCreate,
    LicenceReviewDecision,
    NormalizationRunCreate,
    SegmentationRequest,
    SnapshotCreate,
    SourceLicenceCreate,
    SourceRegistryCreate,
    VersionCreate,
)
from backend.services.corpus_build_service import CorpusBuildService
from backend.services.corpus_export_service import CorpusExportService
from backend.services.corpus_processing_service import CorpusProcessingService
from backend.services.corpus_quality_service import CorpusQualityService
from backend.services.corpus_source_service import CorpusSourceService

CLI_ADMIN_ID = "00000000-0000-0000-0000-0000000000fa"


def _repository() -> CorpusRepository:
    settings = get_settings()
    return CorpusRepository(settings.resolved_database_path)


def _settings():
    return get_settings()


def _print(data: object) -> None:
    print(json.dumps(data, indent=2, default=str, ensure_ascii=False))


def _confirm(prompt: str, word: str) -> bool:
    return input(f"{prompt} Type '{word}' to confirm: ").strip().lower() == word


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Brud AI Tamil corpus builder CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("policies")
    create_policy_parser = subparsers.add_parser("create-policy")
    create_policy_parser.add_argument("--name", required=True)
    validate_policy_parser = subparsers.add_parser("validate-policy")
    validate_policy_parser.add_argument("policy_public_id")
    activate_policy_parser = subparsers.add_parser("activate-policy")
    activate_policy_parser.add_argument("policy_public_id")

    subparsers.add_parser("sources")
    create_source_parser = subparsers.add_parser("create-source")
    create_source_parser.add_argument("--policy", required=True)
    create_source_parser.add_argument("--title", required=True)
    create_source_parser.add_argument("--source-type", required=True)

    transition_parser = subparsers.add_parser("transition-source")
    transition_parser.add_argument("source_public_id")
    transition_parser.add_argument("target_status")

    verify_origin_parser = subparsers.add_parser("verify-origin")
    verify_origin_parser.add_argument("source_public_id")
    verify_origin_parser.add_argument("--evidence", required=True)

    eligibility_parser = subparsers.add_parser("training-eligibility")
    eligibility_parser.add_argument("source_public_id")

    create_licence_parser = subparsers.add_parser("create-licence")
    create_licence_parser.add_argument("source_public_id")
    create_licence_parser.add_argument("--licence-family", required=True)
    create_licence_parser.add_argument("--ai-training-permitted", action="store_true")

    review_licence_parser = subparsers.add_parser("review-licence")
    review_licence_parser.add_argument("licence_public_id")
    review_licence_parser.add_argument("--review-status", required=True)

    create_snapshot_parser = subparsers.add_parser("create-snapshot")
    create_snapshot_parser.add_argument("source_public_id")
    create_snapshot_parser.add_argument("--relative-path", action="append", required=True)

    create_extraction_parser = subparsers.add_parser("create-extraction-run")
    create_extraction_parser.add_argument("snapshot_public_id")
    create_extraction_parser.add_argument("--extraction-method", required=True)

    create_normalization_parser = subparsers.add_parser("create-normalization-run")
    create_normalization_parser.add_argument("extraction_run_public_id")

    segment_parser = subparsers.add_parser("segment-document")
    segment_parser.add_argument("normalized_document_public_id")
    segment_parser.add_argument("--strategy", default="heading_section")

    assess_parser = subparsers.add_parser("assess-segment")
    assess_parser.add_argument("segment_public_id")

    dedup_parser = subparsers.add_parser("run-deduplication")
    dedup_parser.add_argument("--threshold", type=float, default=0.85)

    subparsers.add_parser("run-contamination")

    create_collection_parser = subparsers.add_parser("create-collection")
    create_collection_parser.add_argument("--name", required=True)

    add_member_parser = subparsers.add_parser("add-collection-member")
    add_member_parser.add_argument("collection_public_id")
    add_member_parser.add_argument("segment_public_id")

    create_balance_parser = subparsers.add_parser("create-balance-policy")
    create_balance_parser.add_argument("--name", required=True)

    create_build_parser = subparsers.add_parser("create-build")
    create_build_parser.add_argument("--policy", required=True)
    create_build_parser.add_argument("--balance-policy", required=True)
    create_build_parser.add_argument("--collection", action="append", required=True)

    build_parser = subparsers.add_parser("get-build")
    build_parser.add_argument("build_public_id")

    create_version_parser = subparsers.add_parser("create-version")
    create_version_parser.add_argument("build_public_id")
    create_version_parser.add_argument("--semantic-version", required=True)

    create_export_parser = subparsers.add_parser("create-export")
    create_export_parser.add_argument("version_public_id")

    manifest_parser = subparsers.add_parser("generate-manifest")
    manifest_parser.add_argument("version_public_id")

    compare_parser = subparsers.add_parser("compare-versions")
    compare_parser.add_argument("left_version_public_id")
    compare_parser.add_argument("right_version_public_id")

    args = parser.parse_args(argv)

    settings = _settings()
    repo = _repository()
    source_svc = CorpusSourceService(repo, settings)
    proc_svc = CorpusProcessingService(repo, settings)
    quality_svc = CorpusQualityService(repo, settings)
    build_svc = CorpusBuildService(repo, settings)
    export_svc = CorpusExportService(repo, settings)

    try:
        if args.command == "policies":
            _print(source_svc.list_policies())
        elif args.command == "create-policy":
            _print(source_svc.create_policy(CorpusPolicyCreate(name=args.name), CLI_ADMIN_ID))
        elif args.command == "validate-policy":
            _print(source_svc.validate_policy(args.policy_public_id, CLI_ADMIN_ID))
        elif args.command == "activate-policy":
            _print(source_svc.activate_policy(args.policy_public_id, CLI_ADMIN_ID))
        elif args.command == "sources":
            _print(source_svc.list_sources())
        elif args.command == "create-source":
            _print(
                source_svc.create_source(
                    SourceRegistryCreate(
                        corpus_policy_public_id=args.policy,
                        title=args.title,
                        source_type=args.source_type,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "transition-source":
            _print(
                source_svc.transition_source_status(
                    args.source_public_id, args.target_status, CLI_ADMIN_ID
                )
            )
        elif args.command == "verify-origin":
            _print(
                source_svc.verify_origin(
                    args.source_public_id, CLI_ADMIN_ID, evidence=args.evidence
                )
            )
        elif args.command == "training-eligibility":
            _print(source_svc.training_eligibility(args.source_public_id))
        elif args.command == "create-licence":
            _print(
                source_svc.create_licence(
                    args.source_public_id,
                    SourceLicenceCreate(
                        licence_family=args.licence_family,
                        ai_training_permitted=args.ai_training_permitted,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "review-licence":
            _print(
                source_svc.review_licence(
                    args.licence_public_id,
                    LicenceReviewDecision(review_status=args.review_status),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-snapshot":
            if not _confirm(
                f"About to snapshot {len(args.relative_path)} file(s) for "
                f"{args.source_public_id}.",
                "snapshot",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                source_svc.create_snapshot(
                    args.source_public_id,
                    SnapshotCreate(
                        files=[{"relative_path": path} for path in args.relative_path]
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-extraction-run":
            if not _confirm(
                f"About to extract text from snapshot {args.snapshot_public_id} using "
                f"{args.extraction_method}.",
                "extract",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                proc_svc.create_extraction_run(
                    args.snapshot_public_id,
                    ExtractionRunCreate(extraction_method=args.extraction_method),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-normalization-run":
            if not _confirm(
                f"About to normalize extraction run {args.extraction_run_public_id}.",
                "normalize",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                proc_svc.create_normalization_run(
                    args.extraction_run_public_id, NormalizationRunCreate(), CLI_ADMIN_ID
                )
            )
        elif args.command == "segment-document":
            _print(
                proc_svc.segment_normalized_document(
                    args.normalized_document_public_id,
                    SegmentationRequest(strategy=args.strategy),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "assess-segment":
            _print(quality_svc.assess_segment(args.segment_public_id, CLI_ADMIN_ID))
        elif args.command == "run-deduplication":
            if not _confirm("About to run corpus-wide deduplication.", "dedupe"):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                quality_svc.run_deduplication(
                    DeduplicationRunCreate(near_duplicate_threshold=args.threshold), CLI_ADMIN_ID
                )
            )
        elif args.command == "run-contamination":
            if not _confirm("About to run corpus-wide contamination checking.", "scan"):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                quality_svc.run_contamination_check(ContaminationRunCreate(), CLI_ADMIN_ID)
            )
        elif args.command == "create-collection":
            _print(build_svc.create_collection(CollectionCreate(name=args.name), CLI_ADMIN_ID))
        elif args.command == "add-collection-member":
            _print(
                build_svc.add_member(
                    args.collection_public_id, args.segment_public_id, CLI_ADMIN_ID
                )
            )
        elif args.command == "create-balance-policy":
            _print(
                build_svc.create_balance_policy(
                    BalancePolicyCreate(name=args.name), CLI_ADMIN_ID
                )
            )
        elif args.command == "create-build":
            if not _confirm("About to build a corpus build from the given collections.", "build"):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                build_svc.create_build(
                    BuildCreate(
                        corpus_policy_public_id=args.policy,
                        balance_policy_public_id=args.balance_policy,
                        collection_public_ids=args.collection,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "get-build":
            _print(build_svc.get_build(args.build_public_id))
        elif args.command == "create-version":
            _print(
                build_svc.create_version(
                    args.build_public_id,
                    VersionCreate(semantic_version=args.semantic_version),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-export":
            if not _confirm(
                f"About to export corpus version {args.version_public_id} to disk.", "export"
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                export_svc.create_export(args.version_public_id, ExportCreate(), CLI_ADMIN_ID)
            )
        elif args.command == "generate-manifest":
            _print(export_svc.generate_manifest(args.version_public_id, CLI_ADMIN_ID))
        elif args.command == "compare-versions":
            _print(
                export_svc.compare(
                    CorpusCompareRequest(
                        left_version_public_id=args.left_version_public_id,
                        right_version_public_id=args.right_version_public_id,
                    ),
                    CLI_ADMIN_ID,
                )
            )
    except RepositoryError as exc:
        print(f"Corpus command failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
