"""Phase 15A browser-automation fixture seeder.

Invoked once by `e2e/global-setup.js`, before the isolated backend
process starts. Builds every fixture Playwright's browser tests need
through the *same* real repository/service APIs the Python test suite
already uses (`_build_accepted_experiment`, `_accepted_checkpoint`,
`ProductionRagPromotionService`, `ProductionModelActivationService`,
etc.) -- never a fragile raw SQL insert invented fresh for this script.

Never touches the real development database
(`data/database/brud_ai.db`); the caller passes an isolated, brand-new
`--database-path`. Prints one JSON object to stdout on success: admin
credentials plus every seeded fixture's public_id, so the Node-side
Playwright tests can address them directly.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))

from backend.core.config import Settings  # noqa: E402
from backend.database.migrations import initialize_database  # noqa: E402
from backend.database.repositories.admin import AdminRepository  # noqa: E402
from backend.database.repositories.data_sources import DataSourceRepository  # noqa: E402
from backend.database.repositories.model_release import ModelReleaseRepository  # noqa: E402
from backend.models.auth import AdminCreate  # noqa: E402
from backend.models.data_sources import DataSourceCreate, SourceRightsUpsert  # noqa: E402
from backend.models.documents import ProcessRequest  # noqa: E402
from backend.models.model_release import (  # noqa: E402
    ApprovalCreate,
    ModelReleaseCreate,
    ModelReleaseFamilyCreate,
)
from backend.services.model_release_service import ModelReleaseService  # noqa: E402
from backend.services.production_backup_restore_readiness_service import (  # noqa: E402
    ProductionBackupReadinessService,
)
from backend.services.production_model_release_request_service import (  # noqa: E402
    ProductionModelReleaseRequestService,
)
from backend.services.production_rag_candidate_service import (  # noqa: E402
    ProductionRagCandidateService,
)
from backend.services.production_rag_promotion_service import (  # noqa: E402
    ProductionRagPromotionService,
)
from backend.services.production_regression_service import ProductionRegressionService  # noqa: E402
from backend.services.production_rollback_service import ProductionRollbackPlanService  # noqa: E402

E2E_ADMIN_USERNAME = "e2e-verifier"
E2E_ADMIN_PASSWORD = "Phase15A-E2E-Verifier-Password-77"  # noqa: S105 -- test-only fixture credential
ADMIN_ID = "00000000-0000-0000-0000-000000000001"


class _FakeUploadFile:
    """Matches the small subset of FastAPI's UploadFile interface
    `DocumentService.upload()` actually reads -- the same shape used by
    every document-service unit test in tests/backend/."""

    def __init__(self, filename: str, content: bytes, content_type: str = "application/pdf"):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._offset = 0

    async def read(self, size: int) -> bytes:
        chunk = self._content[self._offset : self._offset + size]
        self._offset += size
        return chunk


def _make_pdf_bytes(text: str) -> bytes:
    import fitz

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    value = pdf.tobytes()
    pdf.close()
    return value


async def _seed_document_sft_fixtures(settings: Settings) -> dict[str, str]:
    """Prerequisite state for the Production Closure Playwright spec
    (09-document-sft-production-closure.spec.js) that would be
    unreasonable to build through the Sources & Rights / Chunk & Record
    Studio UIs inside a single browser test: an uploaded, extracted,
    rights-verified, approved-chunk document ready for SFT generation.
    Every step below reuses the exact same service classes (and the same
    call shapes) already proven by
    tests/backend/test_admin_assistant_document_navigation.py and
    tests/backend/test_document_sft_production_integration_api.py --
    nothing here is a new, unverified code path. The spec's own core
    production path (generate -> review -> export -> validate -> handoff
    -> propose -> split preview -> confirm build -> open dataset version)
    still runs through the real browser UI against this seeded state."""

    from backend.services.data_source_service import SourceRegistryService, SourceRightsService
    from backend.services.document_service import DocumentService
    from backend.services.document_workspace_service import (
        DocumentPageReviewService,
        PDFResearchWorkspaceService,
    )
    from backend.services.semantic_chunk_service import (
        SemanticChunkReviewService,
        SemanticChunkService,
    )

    documents = DocumentService(settings)
    workspace = PDFResearchWorkspaceService(settings)
    review = DocumentPageReviewService(settings)
    chunks = SemanticChunkService(settings)
    chunk_review = SemanticChunkReviewService(settings)
    source_registry = SourceRegistryService(
        DataSourceRepository(settings.resolved_database_path), settings
    )
    rights = SourceRightsService(DataSourceRepository(settings.resolved_database_path), settings)

    upload_file = _FakeUploadFile(
        "e2e-sample.pdf",
        _make_pdf_bytes("Brud AI is a Tamil-first assistant. This paragraph explains what it is."),
    )
    document = await documents.upload(upload_file, "embedded_text", "en", ADMIN_ID)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID)

    source = source_registry.create(
        DataSourceCreate(
            source_code="SRC-E2E-CLOSURE-0001", title="E2E closure source",
            source_type="document_derived",
        ),
        ADMIN_ID,
    )
    rights.upsert(
        source["public_id"],
        SourceRightsUpsert(rights_status="public_domain", training_use_allowed=True),
        ADMIN_ID,
    )
    workspace.link_source(document["public_id"], source["public_id"], ADMIN_ID)
    review.approve(document["public_id"], 1, ADMIN_ID)

    generated = chunks.generate(document["public_id"], ADMIN_ID)
    chunk_public_id = generated["chunk_public_ids"][0]
    chunks.classify(chunk_public_id, ADMIN_ID, chunk_type="definition")
    chunk_review.submit_review(chunk_public_id, ADMIN_ID)
    chunk_review.approve(chunk_public_id, ADMIN_ID)

    return {
        "document_public_id": document["public_id"],
        "document_source_public_id": source["public_id"],
        "document_chunk_public_id": chunk_public_id,
    }


async def _seed_vision_required_document_fixtures(settings: Settings) -> dict[str, str]:
    """A second, separate document whose only page is marked
    vision_required -- proves the negative path (blocked from text-only
    SFT generation) without disturbing the first document's golden-path
    state. Never calls SftCandidateGenerationRequest here -- the spec
    itself exercises that call through the real UI to observe the
    real blocking behavior."""

    from uuid import uuid4

    from backend.database.repositories.documents import DocumentRepository
    from backend.services.data_source_service import SourceRegistryService, SourceRightsService
    from backend.services.document_service import DocumentService
    from backend.services.document_workspace_service import (
        DocumentPageReviewService,
        PDFResearchWorkspaceService,
    )
    from backend.services.semantic_chunk_service import (
        SemanticChunkReviewService,
        SemanticChunkService,
    )

    documents = DocumentService(settings)
    workspace = PDFResearchWorkspaceService(settings)
    review = DocumentPageReviewService(settings)
    chunks = SemanticChunkService(settings)
    chunk_review = SemanticChunkReviewService(settings)
    source_registry = SourceRegistryService(
        DataSourceRepository(settings.resolved_database_path), settings
    )
    rights = SourceRightsService(DataSourceRepository(settings.resolved_database_path), settings)

    upload_file = _FakeUploadFile(
        "e2e-vision-sample.pdf", _make_pdf_bytes("A diagram-only page with no usable caption.")
    )
    document = await documents.upload(upload_file, "embedded_text", "en", ADMIN_ID)
    documents.process(document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID)
    source = source_registry.create(
        DataSourceCreate(
            source_code="SRC-E2E-VISION-0001", title="E2E vision-required source",
            source_type="document_derived",
        ),
        ADMIN_ID,
    )
    rights.upsert(
        source["public_id"],
        SourceRightsUpsert(rights_status="public_domain", training_use_allowed=True),
        ADMIN_ID,
    )
    workspace.link_source(document["public_id"], source["public_id"], ADMIN_ID)
    review.approve(document["public_id"], 1, ADMIN_ID)
    generated = chunks.generate(document["public_id"], ADMIN_ID)
    chunk_public_id = generated["chunk_public_ids"][0]
    chunks.classify(chunk_public_id, ADMIN_ID, chunk_type="definition")
    chunk_review.submit_review(chunk_public_id, ADMIN_ID)
    chunk_review.approve(chunk_public_id, ADMIN_ID)

    repository = DocumentRepository(settings.resolved_database_path)
    with repository.transaction() as connection:
        document_row = repository.document(connection, document["public_id"])
        connection.execute(
            """INSERT INTO document_content_classifications(
                public_id,document_source_id,page_number,content_type,caption_text,
                vision_required
            ) VALUES (?,?,?,?,?,1)""",
            (str(uuid4()), document_row["id"], 1, "image_without_usable_text", ""),
        )

    return {"vision_required_document_public_id": document["public_id"]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-path", required=True)
    parser.add_argument("--backup-dir", required=True)
    parser.add_argument("--pretraining-dir", required=True)
    parser.add_argument("--tokenizer-corpus-dir", required=True)
    parser.add_argument("--tokenizer-dir", required=True)
    parser.add_argument("--core-model-dir", required=True)
    parser.add_argument("--core-checkpoint-dir", required=True)
    parser.add_argument("--release-artifact-dir", required=True)
    parser.add_argument("--release-bundle-dir", required=True)
    parser.add_argument("--allowed-data-dir", required=True)
    args = parser.parse_args()

    settings = Settings(
        database_path=Path(args.database_path),
        database_backup_dir=Path(args.backup_dir),
        allowed_data_dir=Path(args.allowed_data_dir),
        pretraining_dir=Path(args.pretraining_dir),
        tokenizer_corpus_dir=Path(args.tokenizer_corpus_dir),
        tokenizer_dir=Path(args.tokenizer_dir),
        core_model_dir=Path(args.core_model_dir),
        core_checkpoint_dir=Path(args.core_checkpoint_dir),
        release_artifact_dir=Path(args.release_artifact_dir),
        release_bundle_dir=Path(args.release_bundle_dir),
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)

    AdminRepository(settings.resolved_database_path).create_admin(
        AdminCreate(
            username=E2E_ADMIN_USERNAME, display_name="Phase 15A E2E Verifier",
            password=E2E_ADMIN_PASSWORD,
        )
    )

    # Deferred imports: these live under tests/, only importable once the
    # repo root is on sys.path (done above) -- reusing the exact same
    # fixture-builder functions the Python regression suite already relies
    # on, never a fresh raw-SQL fixture invented for this script.
    from tests.backend.test_production_model_release_validation_activation import (
        _accepted_checkpoint,
        _approved_admin_diagnostic_assignment,
        _assignment_service,
        _profile,
        _validated_release_request,
    )
    from tests.backend.test_production_rag_eligibility_and_promotion import (
        _insert_knowledge_space,
        _mark_eligible_for_production_rag,
    )
    from tests.backend.test_production_rag_validation_activation_rollback import (
        _register_deterministic_embedding_model,
    )
    from tests.backend.test_training_suitability_and_transformation import (
        _build_accepted_experiment,
    )

    result: dict[str, object] = {
        "admin_username": E2E_ADMIN_USERNAME,
        "admin_password": E2E_ADMIN_PASSWORD,
    }

    # -- accepted Phase 13 RAG report + production RAG promotion candidate --
    # code_suffix="9" avoids colliding with the "0"/"1"/"2" suffixes the
    # Phase 14 checkpoint fixture chain below uses internally for its own
    # 3-candidate dataset promotion.
    built = _build_accepted_experiment(settings, code_suffix="9")
    result["rag_sandbox_experiment_public_id"] = built["experiment"]["public_id"]
    _mark_eligible_for_production_rag(settings, built["experiment"]["public_id"])
    knowledge_space_id = _insert_knowledge_space(settings)
    embedding_model_id = _register_deterministic_embedding_model(settings)
    result["knowledge_space_public_id"] = knowledge_space_id

    promotion_service = ProductionRagPromotionService(settings)
    promotion = promotion_service.create_request(
        {
            "rag_sandbox_experiment_public_id": built["experiment"]["public_id"],
            "knowledge_space_public_id": knowledge_space_id,
            "selected_record_ids": [r["public_id"] for r in built["records"]],
            "embedding_assignment_key": embedding_model_id,
        },
        admin_id=ADMIN_ID,
    )
    result["rag_promotion_request_public_id"] = promotion["public_id"]
    promotion_service.submit_for_review(promotion["public_id"], admin_id=ADMIN_ID)
    rag_approval = promotion_service.request_approval(promotion["public_id"], admin_id=ADMIN_ID)
    promotion_service.approve(rag_approval["public_id"], admin_id=ADMIN_ID)

    rag_candidate = ProductionRagCandidateService(settings).build_candidate(
        promotion["public_id"], admin_id=ADMIN_ID
    )
    result["rag_release_candidate_public_id"] = rag_candidate["public_id"]

    # -- accepted Phase 14 checkpoint + production model release request --
    checkpoint = _accepted_checkpoint(settings)
    result["incremental_training_checkpoint_public_id"] = checkpoint["public_id"]

    validated_release = _validated_release_request(settings, checkpoint=checkpoint)
    result["model_release_request_public_id"] = validated_release["public_id"]
    result["model_release_candidate_public_id"] = validated_release[
        "model_release_candidate_public_id"
    ]

    release_service = ModelReleaseService(
        ModelReleaseRepository(settings.resolved_database_path), settings
    )
    release_service.submit_approval(
        validated_release["model_release_candidate_public_id"],
        ApprovalCreate(role="release", decision="approve", comment="e2e fixture"),
        ADMIN_ID,
    )
    created_release = release_service.create_release(
        ModelReleaseCreate(
            candidate_public_id=validated_release["model_release_candidate_public_id"],
            version="0.1.0-e2e",
        ),
        ADMIN_ID,
    )
    result["model_release_public_id"] = created_release["public_id"]

    # -- canary/rollback-ready assignment + rollback plan --
    assignment_service = _assignment_service(settings)
    profile_public_id = _profile(settings)
    assignment_public_id = _approved_admin_diagnostic_assignment(
        settings, assignment_service, created_release["public_id"], profile_public_id,
    )
    result["inference_model_assignment_public_id"] = assignment_public_id

    rollback_plan = ProductionRollbackPlanService(settings).create_plan(
        {"target_type": "model", "rollback_steps": ["rollback_execute"]}, admin_id=ADMIN_ID,
    )
    ProductionRollbackPlanService(settings).validate_plan(
        rollback_plan["public_id"], admin_id=ADMIN_ID
    )
    result["model_rollback_plan_public_id"] = rollback_plan["public_id"]

    # -- a second governance request against the *same* accepted checkpoint
    # that is only ever "created" (never validated/approved) -- exercises
    # the "blocked without approval" states the UI must render honestly,
    # without needing a second, expensive, colliding checkpoint fixture.
    request_service = ProductionModelReleaseRequestService(settings)
    unapproved_family = release_service.create_family(
        ModelReleaseFamilyCreate(name="E2E Unapproved Family", slug="e2e-unapproved-family"),
        ADMIN_ID,
    )
    unapproved_request = request_service.create_request(
        {
            "incremental_training_checkpoint_public_id": checkpoint["public_id"],
            "model_release_family_public_id": unapproved_family["public_id"],
        },
        admin_id=ADMIN_ID,
    )
    result["unapproved_model_release_request_public_id"] = unapproved_request["public_id"]

    # -- backup readiness record --
    backup_check = ProductionBackupReadinessService(settings).check_backup_readiness(
        admin_id=ADMIN_ID
    )
    result["backup_readiness_check_public_id"] = backup_check["public_id"]

    # -- Document SFT Production Closure fixtures (upload/extract/rights/
    # chunk-approval, built through the real service layer since doing
    # this through the Sources & Rights / Chunk & Record Studio UIs is
    # unreasonable fixture setup for a single spec) --
    document_fixtures = asyncio.run(_seed_document_sft_fixtures(settings))
    result.update(document_fixtures)
    vision_fixtures = asyncio.run(_seed_vision_required_document_fixtures(settings))
    result.update(vision_fixtures)

    # -- a real canonical-manifest regression run with one real batch
    # executed (deliberately left un-finalized/partial -- the UI must
    # render honest in-progress state, not a fabricated completion) --
    regression_service = ProductionRegressionService(settings)
    regression_run = regression_service.create_manifest_run(admin_id=ADMIN_ID)
    regression_service.execute_registered_batch(
        regression_run["public_id"], "secret_scan_01", admin_id=ADMIN_ID,
    )
    result["regression_run_public_id"] = regression_run["public_id"]

    print(json.dumps(result))


if __name__ == "__main__":
    main()
