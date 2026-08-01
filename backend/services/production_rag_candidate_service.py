"""Phase 15 Steps 5-6: production RAG release candidate build and
validation.

Reuses the *existing, unmodified* `RagIngestionService` (source ->
source version -> chunk set -> embedding run -> vector/keyword index)
end to end -- this service never re-implements chunking, embedding,
or indexing. The build never touches the currently-active retrieval
profile: a brand-new, `production_visible=false` candidate row is
created and only ever wired to `RagRetrievalService.activate_profile()`
from behind `ProductionRagActivationService` (Step 8), never here. See
docs/production/phase15_text_nlp_production_readiness_plan.md.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.core.config import Settings
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.base import ValidationError
from backend.database.repositories.production_readiness import ProductionReadinessRepository
from backend.database.repositories.rag import RagRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.rag import (
    ChunkSetCreate,
    EmbeddingRunCreate,
    KeywordIndexCreate,
    KnowledgeSourceCreate,
    RetrievalProfileCreate,
    VectorIndexCreate,
)
from backend.services.rag_ingestion_service import RagIngestionService
from backend.services.rag_retrieval_service import RagRetrievalService

logger = logging.getLogger(__name__)


def _audit(
    audit_repository: AuditLogRepository | None,
    *,
    action: str,
    actor_reference: str,
    resource_public_id: str,
    outcome: AuditOutcome,
    metadata: dict[str, Any] | None = None,
) -> None:
    if audit_repository is None:
        return
    try:
        audit_repository.append(
            AuditEventCreate(
                event_type=f"production_rag_candidate_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="production_rag_release_candidate",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("production_rag_candidate_audit_write_failed", extra={"action": action})


class ProductionRagCandidateService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = ProductionReadinessRepository(settings.resolved_database_path)
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._ingestion = RagIngestionService(
            RagRepository(settings.resolved_database_path), settings
        )
        self._retrieval = RagRetrievalService(
            RagRepository(settings.resolved_database_path), settings
        )
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def build_candidate(self, promotion_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        request = self.repository.get_rag_promotion_request(promotion_request_public_id)
        if request["status"] != "approved":
            raise ValidationError(
                "the promotion request must be approved before a candidate can be built"
            )
        if not request["embedding_assignment_key"]:
            raise ValidationError(
                "an existing embedding_model_public_id (embedding_assignment_key) is required "
                "-- this phase never registers a new embedding provider"
            )

        candidate = self.repository.create_rag_release_candidate(
            promotion_request_public_id,
            {
                "record_checksum_set_hash": request["selected_record_checksum_set_hash"],
                "created_by_admin_public_id": admin_id,
            },
        )
        self.repository.update_rag_promotion_request(
            promotion_request_public_id, {"status": "building_candidate"}
        )

        try:
            record_ids = request["selected_record_ids"]
            texts = []
            for record_public_id in record_ids:
                record = self._sandbox.get_record(record_public_id)
                if record["content"]:
                    texts.append(record["content"])
            content = "\n\n".join(texts)

            source = self._ingestion.create_source(
                request["knowledge_space_public_id"],
                KnowledgeSourceCreate(
                    source_type="plain_text",
                    title=f"Production RAG candidate {candidate['public_id'][:8]}",
                    content=content,
                    metadata={"production_rag_promotion_request_public_id": request["public_id"]},
                ),
                admin_id,
            )
            source_version = self._ingestion.create_source_version(
                source["public_id"], admin_id, content_override=content
            )
            self._ingestion.validate_source_version(source_version["public_id"], admin_id)
            chunking = request.get("chunking_configuration") or {}
            chunk_set = self._ingestion.create_chunk_set(
                source_version["public_id"], ChunkSetCreate(**chunking), admin_id
            )
            self._ingestion.validate_chunk_set(chunk_set["public_id"], admin_id)
            embedding_run = self._ingestion.create_embedding_run(
                chunk_set["public_id"],
                EmbeddingRunCreate(embedding_model_public_id=request["embedding_assignment_key"]),
                admin_id,
            )
            vector_index = self._ingestion.create_vector_index(
                embedding_run["public_id"], VectorIndexCreate(), admin_id
            )
            keyword_index = self._ingestion.create_keyword_index(
                chunk_set["public_id"], KeywordIndexCreate(), admin_id
            )
            retrieval_configuration = request.get("retrieval_configuration") or {}
            profile = self._retrieval.create_profile(
                request["knowledge_space_public_id"],
                RetrievalProfileCreate(
                    name=f"production-candidate-{candidate['public_id'][:8]}",
                    **retrieval_configuration,
                ),
                admin_id,
            )
            self._retrieval.validate_profile(profile["public_id"], admin_id)
        except Exception as exc:
            self.repository.update_rag_release_candidate(
                candidate["public_id"], {"status": "failed"}
            )
            self.repository.update_rag_promotion_request(
                promotion_request_public_id, {"status": "validation_failed"}
            )
            _audit(
                self._audit, action="build_failed", actor_reference=admin_id,
                resource_public_id=candidate["public_id"], outcome=AuditOutcome.FAILURE,
                metadata={"error": str(exc)},
            )
            raise

        index_checksum = (
            f"{vector_index.get('mapping_manifest_checksum_sha256', '')}:"
            f"{keyword_index.get('index_artifact_checksum_sha256', '')}"
        )
        self.repository.update_rag_release_candidate(
            candidate["public_id"],
            {
                "status": "built",
                "index_checksum_sha256": index_checksum,
                "chunk_checksum_set_hash": chunk_set.get("chunk_manifest_checksum_sha256"),
                "embedding_model_reference": request["embedding_assignment_key"],
            },
        )
        with self.repository.transaction() as connection:
            source_id = connection.execute(
                "SELECT id FROM rag_knowledge_sources WHERE public_id=?", (source["public_id"],)
            ).fetchone()[0]
            profile_id = connection.execute(
                "SELECT id FROM rag_retrieval_profiles WHERE public_id=?", (profile["public_id"],)
            ).fetchone()[0]
            connection.execute(
                "UPDATE production_rag_release_candidates SET knowledge_source_id=?, "
                "retrieval_profile_id=?, updated_at=CURRENT_TIMESTAMP WHERE public_id=?",
                (source_id, profile_id, candidate["public_id"]),
            )
        self.repository.update_rag_promotion_request(
            promotion_request_public_id, {"status": "candidate_ready"}
        )
        _audit(
            self._audit, action="build_completed", actor_reference=admin_id,
            resource_public_id=candidate["public_id"], outcome=AuditOutcome.SUCCESS,
        )
        return self.repository.get_rag_release_candidate(candidate["public_id"])


__all__ = ["ProductionRagCandidateService"]
