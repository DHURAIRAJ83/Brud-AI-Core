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
    BalancePreviewRequest,
    BuildCreate,
    CollectionCreate,
    ContaminationRunCreate,
    CorpusCompareRequest,
    CorpusPolicyCreate,
    DeduplicationRunCreate,
    ExportCreate,
    ExtractionRunCreate,
    IngestionJobCreate,
    LabelCorrection,
    LicenceReviewDecision,
    NormalizationProfileCreate,
    NormalizationRunCreate,
    PartitionPreviewRequest,
    ProtectedContentEntryCreate,
    ProtectedContentSetCreate,
    ReadinessEvaluationCreate,
    ReleaseApprovalCreate,
    ReleaseCreate,
    SegmentationProfileCreate,
    SegmentationRequest,
    SnapshotCreate,
    SourceLicenceCreate,
    SourceRegistryCreate,
    SourceReviewUpdate,
    TokenizerAnalysisCreate,
    VersionCreate,
)
from backend.services.corpus_build_service import CorpusBuildService
from backend.services.corpus_export_service import CorpusExportService
from backend.services.corpus_ingestion_service import CorpusIngestionService
from backend.services.corpus_processing_service import CorpusProcessingService
from backend.services.corpus_profile_service import CorpusProfileService
from backend.services.corpus_quality_service import CorpusQualityService
from backend.services.corpus_readiness_service import CorpusReadinessService
from backend.services.corpus_release_service import CorpusReleaseService
from backend.services.corpus_source_service import CorpusSourceService
from backend.services.corpus_tokenizer_analysis_service import CorpusTokenizerAnalysisService

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

    # --- Phase 20 -----------------------------------------------------

    review_meta_parser = subparsers.add_parser("set-review-metadata")
    review_meta_parser.add_argument("source_public_id")
    review_meta_parser.add_argument("--original-url")
    review_meta_parser.add_argument("--acquisition-date")

    lifecycle_parser = subparsers.add_parser("advance-production-lifecycle")
    lifecycle_parser.add_argument("source_public_id")
    lifecycle_parser.add_argument("target_status")
    lifecycle_parser.add_argument("--reason", default="")

    subparsers.add_parser("normalization-profiles")
    create_norm_profile_parser = subparsers.add_parser("create-normalization-profile")
    create_norm_profile_parser.add_argument("--name", required=True)
    create_norm_profile_parser.add_argument("--profile-key", required=True)
    activate_norm_profile_parser = subparsers.add_parser("activate-normalization-profile")
    activate_norm_profile_parser.add_argument("profile_public_id")
    archive_norm_profile_parser = subparsers.add_parser("archive-normalization-profile")
    archive_norm_profile_parser.add_argument("profile_public_id")

    subparsers.add_parser("segmentation-profiles")
    create_seg_profile_parser = subparsers.add_parser("create-segmentation-profile")
    create_seg_profile_parser.add_argument("--name", required=True)
    create_seg_profile_parser.add_argument("--content-type", required=True)
    create_seg_profile_parser.add_argument("--strategy", required=True)
    activate_seg_profile_parser = subparsers.add_parser("activate-segmentation-profile")
    activate_seg_profile_parser.add_argument("profile_public_id")
    archive_seg_profile_parser = subparsers.add_parser("archive-segmentation-profile")
    archive_seg_profile_parser.add_argument("profile_public_id")

    inspect_file_parser = subparsers.add_parser("inspect-file")
    inspect_file_parser.add_argument("--relative-path", required=True)
    inspect_file_parser.add_argument("--declared-format", required=True)

    create_job_parser = subparsers.add_parser("create-ingestion-job")
    create_job_parser.add_argument("source_public_id")
    create_job_parser.add_argument("--format", required=True)
    create_job_parser.add_argument("--relative-path", action="append", required=True)
    create_job_parser.add_argument("--idempotency-key")

    ingestion_jobs_parser = subparsers.add_parser("ingestion-jobs")
    ingestion_jobs_parser.add_argument("source_public_id")
    get_job_parser = subparsers.add_parser("get-ingestion-job")
    get_job_parser.add_argument("job_public_id")

    run_job_parser = subparsers.add_parser("run-ingestion-job")
    run_job_parser.add_argument("job_public_id")
    run_job_parser.add_argument("--relative-path", action="append", required=True)

    cancel_job_parser = subparsers.add_parser("cancel-ingestion-job")
    cancel_job_parser.add_argument("job_public_id")
    retry_job_parser = subparsers.add_parser("retry-ingestion-job")
    retry_job_parser.add_argument("job_public_id")

    segment_assessments_parser = subparsers.add_parser("segment-assessments")
    segment_assessments_parser.add_argument("segment_public_id")

    correct_label_parser = subparsers.add_parser("correct-label")
    correct_label_parser.add_argument("segment_public_id")
    correct_label_parser.add_argument("--label-type", required=True)
    correct_label_parser.add_argument("--value", required=True)

    subparsers.add_parser("protected-content-sets")
    create_pcs_parser = subparsers.add_parser("create-protected-content-set")
    create_pcs_parser.add_argument("--name", required=True)
    create_pcs_parser.add_argument("--set-type", required=True)
    get_pcs_parser = subparsers.add_parser("get-protected-content-set")
    get_pcs_parser.add_argument("set_public_id")
    activate_pcs_parser = subparsers.add_parser("activate-protected-content-set")
    activate_pcs_parser.add_argument("set_public_id")
    add_pcs_entries_parser = subparsers.add_parser("add-protected-content-entries")
    add_pcs_entries_parser.add_argument("set_public_id")
    add_pcs_entries_parser.add_argument("--text", action="append", required=True)

    preview_balance_parser = subparsers.add_parser("preview-balance")
    preview_balance_parser.add_argument("collection_public_id")
    preview_balance_parser.add_argument("--balance-policy", required=True)

    preview_partitions_parser = subparsers.add_parser("preview-partitions")
    preview_partitions_parser.add_argument("collection_public_id")
    preview_partitions_parser.add_argument("--seed", type=int, default=42)

    create_tok_analysis_parser = subparsers.add_parser("create-tokenizer-analysis")
    create_tok_analysis_parser.add_argument("--tokenizer-version", required=True)
    create_tok_analysis_parser.add_argument("--collection")
    create_tok_analysis_parser.add_argument("--build")
    get_tok_analysis_parser = subparsers.add_parser("get-tokenizer-analysis")
    get_tok_analysis_parser.add_argument("analysis_public_id")

    create_readiness_parser = subparsers.add_parser("create-readiness-evaluation")
    create_readiness_parser.add_argument("build_public_id")
    create_readiness_parser.add_argument("--tokenizer-analysis")
    get_readiness_parser = subparsers.add_parser("get-readiness-evaluation")
    get_readiness_parser.add_argument("evaluation_public_id")

    subparsers.add_parser("releases")
    create_release_parser = subparsers.add_parser("create-release")
    create_release_parser.add_argument("--version", required=True)
    create_release_parser.add_argument("--readiness-evaluation")
    create_release_parser.add_argument("--semantic-version", required=True)
    create_release_parser.add_argument("--release-name", required=True)
    get_release_parser = subparsers.add_parser("get-release")
    get_release_parser.add_argument("release_public_id")
    validate_release_parser = subparsers.add_parser("validate-release")
    validate_release_parser.add_argument("release_public_id")
    approve_release_parser = subparsers.add_parser("approve-release")
    approve_release_parser.add_argument("release_public_id")
    approve_release_parser.add_argument("--decision", required=True, choices=["approve", "reject"])
    approve_release_parser.add_argument("--comment", default="")
    finalize_release_parser = subparsers.add_parser("finalize-release")
    finalize_release_parser.add_argument("release_public_id")
    export_release_parser = subparsers.add_parser("export-release")
    export_release_parser.add_argument("release_public_id")
    export_release_parser.add_argument("--export", required=True)
    retire_release_parser = subparsers.add_parser("retire-release")
    retire_release_parser.add_argument("release_public_id")

    args = parser.parse_args(argv)

    settings = _settings()
    repo = _repository()
    source_svc = CorpusSourceService(repo, settings)
    proc_svc = CorpusProcessingService(repo, settings)
    quality_svc = CorpusQualityService(repo, settings)
    build_svc = CorpusBuildService(repo, settings)
    export_svc = CorpusExportService(repo, settings)
    profile_svc = CorpusProfileService(repo, settings)
    ingestion_svc = CorpusIngestionService(repo, settings)
    tokenizer_analysis_svc = CorpusTokenizerAnalysisService(repo, settings)
    readiness_svc = CorpusReadinessService(repo, settings)
    release_svc = CorpusReleaseService(repo, settings)

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
        elif args.command == "set-review-metadata":
            _print(
                source_svc.set_review_metadata(
                    args.source_public_id,
                    SourceReviewUpdate(
                        original_url=args.original_url, acquisition_date=args.acquisition_date
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "advance-production-lifecycle":
            _print(
                source_svc.advance_production_lifecycle(
                    args.source_public_id, args.target_status, CLI_ADMIN_ID, reason=args.reason
                )
            )
        elif args.command == "normalization-profiles":
            _print(profile_svc.list_normalization_profiles())
        elif args.command == "create-normalization-profile":
            _print(
                profile_svc.create_normalization_profile(
                    NormalizationProfileCreate(name=args.name, profile_key=args.profile_key),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "activate-normalization-profile":
            _print(
                profile_svc.activate_normalization_profile(args.profile_public_id, CLI_ADMIN_ID)
            )
        elif args.command == "archive-normalization-profile":
            _print(
                profile_svc.archive_normalization_profile(args.profile_public_id, CLI_ADMIN_ID)
            )
        elif args.command == "segmentation-profiles":
            _print(profile_svc.list_segmentation_profiles())
        elif args.command == "create-segmentation-profile":
            _print(
                profile_svc.create_segmentation_profile(
                    SegmentationProfileCreate(
                        name=args.name, content_type=args.content_type, strategy=args.strategy
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "activate-segmentation-profile":
            _print(profile_svc.activate_segmentation_profile(args.profile_public_id, CLI_ADMIN_ID))
        elif args.command == "archive-segmentation-profile":
            _print(profile_svc.archive_segmentation_profile(args.profile_public_id, CLI_ADMIN_ID))
        elif args.command == "inspect-file":
            _print(
                ingestion_svc.inspect_source_file(args.relative_path, args.declared_format)
            )
        elif args.command == "create-ingestion-job":
            _print(
                ingestion_svc.create_job(
                    args.source_public_id,
                    IngestionJobCreate(
                        format=args.format,
                        relative_paths=args.relative_path,
                        idempotency_key=args.idempotency_key,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "ingestion-jobs":
            _print(ingestion_svc.list_jobs(args.source_public_id))
        elif args.command == "get-ingestion-job":
            _print(ingestion_svc.get_job(args.job_public_id))
        elif args.command == "run-ingestion-job":
            if not _confirm(
                f"About to run ingestion job {args.job_public_id} "
                f"(snapshot -> extract -> normalize -> segment).",
                "run",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                ingestion_svc.run_job(args.job_public_id, args.relative_path, CLI_ADMIN_ID)
            )
        elif args.command == "cancel-ingestion-job":
            _print(ingestion_svc.cancel_job(args.job_public_id, CLI_ADMIN_ID))
        elif args.command == "retry-ingestion-job":
            _print(ingestion_svc.retry_job(args.job_public_id, CLI_ADMIN_ID))
        elif args.command == "segment-assessments":
            _print(quality_svc.assessments_for_segment(args.segment_public_id))
        elif args.command == "correct-label":
            _print(
                quality_svc.correct_label(
                    args.segment_public_id,
                    LabelCorrection(label_type=args.label_type, value=args.value),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "protected-content-sets":
            _print(quality_svc.list_protected_content_sets())
        elif args.command == "create-protected-content-set":
            _print(
                quality_svc.create_protected_content_set(
                    ProtectedContentSetCreate(name=args.name, set_type=args.set_type),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "get-protected-content-set":
            _print(quality_svc.get_protected_content_set(args.set_public_id))
        elif args.command == "activate-protected-content-set":
            _print(quality_svc.activate_protected_content_set(args.set_public_id, CLI_ADMIN_ID))
        elif args.command == "add-protected-content-entries":
            _print(
                quality_svc.add_protected_content_entries(
                    args.set_public_id,
                    ProtectedContentEntryCreate(texts=args.text),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "preview-balance":
            _print(
                build_svc.preview_balance(
                    args.collection_public_id,
                    BalancePreviewRequest(balance_policy_public_id=args.balance_policy),
                )
            )
        elif args.command == "preview-partitions":
            _print(
                build_svc.preview_partitions(
                    args.collection_public_id,
                    PartitionPreviewRequest(seed=args.seed),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "create-tokenizer-analysis":
            if not _confirm(
                f"About to run tokenizer compatibility analysis with "
                f"tokenizer version {args.tokenizer_version}.",
                "analyze",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(
                tokenizer_analysis_svc.create_analysis(
                    TokenizerAnalysisCreate(
                        tokenizer_version_public_id=args.tokenizer_version,
                        collection_public_id=args.collection,
                        build_public_id=args.build,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "get-tokenizer-analysis":
            _print(tokenizer_analysis_svc.get_analysis(args.analysis_public_id))
        elif args.command == "create-readiness-evaluation":
            _print(
                readiness_svc.evaluate(
                    ReadinessEvaluationCreate(
                        build_public_id=args.build_public_id,
                        tokenizer_analysis_public_id=args.tokenizer_analysis,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "get-readiness-evaluation":
            _print(readiness_svc.get_evaluation(args.evaluation_public_id))
        elif args.command == "releases":
            _print(release_svc.list_releases())
        elif args.command == "create-release":
            _print(
                release_svc.create_release(
                    ReleaseCreate(
                        corpus_version_public_id=args.version,
                        readiness_evaluation_public_id=args.readiness_evaluation,
                        semantic_version=args.semantic_version,
                        release_name=args.release_name,
                    ),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "get-release":
            _print(release_svc.get_release(args.release_public_id))
        elif args.command == "validate-release":
            _print(release_svc.validate_release(args.release_public_id, CLI_ADMIN_ID))
        elif args.command == "approve-release":
            _print(
                release_svc.record_approval(
                    args.release_public_id,
                    ReleaseApprovalCreate(decision=args.decision, comment=args.comment),
                    CLI_ADMIN_ID,
                )
            )
        elif args.command == "finalize-release":
            if not _confirm(
                f"About to finalize release {args.release_public_id}. This is immutable.",
                "finalize",
            ):
                print("Cancelled.", file=sys.stderr)
                return 1
            _print(release_svc.finalize_release(args.release_public_id, CLI_ADMIN_ID))
        elif args.command == "export-release":
            _print(
                release_svc.mark_exported(args.release_public_id, args.export, CLI_ADMIN_ID)
            )
        elif args.command == "retire-release":
            _print(release_svc.retire_release(args.release_public_id, CLI_ADMIN_ID))
    except RepositoryError as exc:
        print(f"Corpus command failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
