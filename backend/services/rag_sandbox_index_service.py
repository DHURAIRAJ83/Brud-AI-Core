"""Phase 13 Step 8/9 chunking and isolated index building.

Reuses `RagIngestionService.create_chunk_set/create_embedding_model/
create_embedding_run/execute_embedding_run/create_vector_index/
build_vector_index/create_keyword_index/build_keyword_index` and
`RagRetrievalService.create_profile` verbatim -- no chunking, BM25, or
vector-scoring code is reimplemented here. Every index this service
builds is scoped to the sandbox's own dedicated `rag_knowledge_spaces`
row, never the production space. See
docs/rag_sandbox/phase13_isolated_rag_sandbox_plan.md.
"""

from __future__ import annotations

import hashlib
import logging
import sqlite3
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories import AuditLogRepository
from backend.database.repositories.rag import RagRepository
from backend.database.repositories.rag_sandbox import RagSandboxRepository
from backend.models.domain import AuditEventCreate, AuditOutcome
from backend.models.rag import (
    ChunkSetCreate,
    EmbeddingModelCreate,
    EmbeddingRunCreate,
    KeywordIndexCreate,
    RetrievalProfileCreate,
    VectorIndexCreate,
)
from backend.services.rag_ingestion_service import RagIngestionService
from backend.services.rag_retrieval_service import RagRetrievalService
from backend.services.rag_sandbox_eligibility_service import RagSandboxError

logger = logging.getLogger(__name__)

_WEIGHTS_BY_KIND = {
    "vector": (1.0, 0.0),
    "bm25": (0.0, 1.0),
    "hybrid": (0.6, 0.4),
}


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
                event_type=f"rag_sandbox_{action}",
                actor_type="admin",
                actor_reference=actor_reference,
                action=action,
                resource_type="rag_sandbox_experiment",
                resource_public_id=resource_public_id,
                outcome=outcome,
                metadata=metadata or {},
            )
        )
    except Exception:
        logger.exception("rag_sandbox_audit_write_failed", extra={"action": action})


class RagSandboxIndexService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._sandbox = RagSandboxRepository(settings.resolved_database_path)
        self._rag_repository = RagRepository(settings.resolved_database_path)
        self._ingestion = RagIngestionService(self._rag_repository, settings)
        self._retrieval = RagRetrievalService(self._rag_repository, settings)
        self._audit = (
            AuditLogRepository(settings.resolved_database_path) if settings.audit_enabled else None
        )

    def _source_version_public_id(self, rag_source_version_id: int) -> str:
        with sqlite3.connect(self.settings.resolved_database_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT public_id FROM rag_source_versions WHERE id=?",
                (rag_source_version_id,),
            ).fetchone()
        if not row:
            raise RagSandboxError("no rag source version is linked to this sandbox corpus")
        return row["public_id"]

    def build_index(
        self,
        experiment_public_id: str,
        *,
        index_kind: str,
        admin_id: str,
        chunking_config: dict[str, Any] | None = None,
        embedding_model_public_id: str | None = None,
        top_k: int = 5,
        minimum_score: float = 0.15,
    ) -> dict[str, Any]:
        if index_kind not in _WEIGHTS_BY_KIND:
            raise RagSandboxError(f"unknown index_kind: {index_kind!r}")

        experiment = self._sandbox.get_experiment(experiment_public_id)
        corpus = self._sandbox.get_corpus_for_experiment(experiment_public_id)
        if corpus is None or corpus["status"] != "ready":
            raise RagSandboxError("the sandbox corpus must be prepared and ready before indexing")

        records = self._sandbox.list_records(experiment_public_id, limit=1, offset=0)
        if not records:
            raise RagSandboxError("no promoted sandbox records exist to index")
        source_version_public_id = self._source_version_public_id(
            records[0]["rag_source_version_id"]
        )

        self._sandbox.update_experiment(
            experiment_public_id, {"status": "building_index", "current_stage": "index_build"}
        )
        index_row = self._sandbox.create_index(
            experiment_public_id,
            {
                "corpus_public_id": corpus["public_id"],
                "index_kind": index_kind,
                "build_config": {
                    "chunking_config": chunking_config or {},
                    "top_k": top_k,
                    "minimum_score": minimum_score,
                },
                "created_by_admin_public_id": admin_id,
            },
        )

        try:
            chunk_config = chunking_config or {}
            chunk_set = self._ingestion.create_chunk_set(
                source_version_public_id, ChunkSetCreate(**chunk_config), admin_id
            )

            vector_index = None
            keyword_index = None
            embedding_model_id_used = None
            if index_kind in ("vector", "hybrid"):
                if embedding_model_public_id:
                    embedding_model = {"public_id": embedding_model_public_id}
                else:
                    embedding_model = self._ingestion.create_embedding_model(
                        EmbeddingModelCreate(
                            name=f"sandbox-{experiment['experiment_code']}",
                            version="v1",
                            provider_type="local_custom_embedding",
                            dimensions=256,
                            maximum_input_tokens=2048,
                        ),
                        admin_id,
                    )
                embedding_model_id_used = embedding_model["public_id"]
                embedding_run = self._ingestion.create_embedding_run(
                    chunk_set["public_id"],
                    EmbeddingRunCreate(embedding_model_public_id=embedding_model["public_id"]),
                    admin_id,
                )
                embedding_run = self._ingestion.execute_embedding_run(
                    embedding_run["public_id"], admin_id
                )
                vector_index = self._ingestion.create_vector_index(
                    embedding_run["public_id"], VectorIndexCreate(), admin_id
                )
                vector_index = self._ingestion.build_vector_index(
                    vector_index["public_id"], admin_id
                )
                self._ingestion.validate_vector_index(vector_index["public_id"], admin_id)
                vector_index = self._ingestion.activate_vector_index(
                    vector_index["public_id"], admin_id
                )

            if index_kind in ("bm25", "hybrid"):
                keyword_index = self._ingestion.create_keyword_index(
                    chunk_set["public_id"], KeywordIndexCreate(), admin_id
                )
                keyword_index = self._ingestion.build_keyword_index(
                    keyword_index["public_id"], admin_id
                )
                self._ingestion.validate_keyword_index(keyword_index["public_id"], admin_id)
                keyword_index = self._ingestion.activate_keyword_index(
                    keyword_index["public_id"], admin_id
                )

            vector_weight, keyword_weight = _WEIGHTS_BY_KIND[index_kind]
            profile = self._retrieval.create_profile(
                corpus["knowledge_space_public_id"],
                RetrievalProfileCreate(
                    name=f"sandbox-{index_row['public_id'][:8]}",
                    final_top_k=top_k,
                    vector_weight=vector_weight,
                    keyword_weight=keyword_weight,
                    minimum_score=minimum_score,
                ),
                admin_id,
            )
            self._retrieval.validate_profile(profile["public_id"], admin_id)
            profile = self._retrieval.activate_profile(profile["public_id"], admin_id)

            with self._rag_repository.transaction() as connection:
                vector_index_id = (
                    self._rag_repository.vector_index(connection, vector_index["public_id"])["id"]
                    if vector_index
                    else None
                )
                keyword_index_id = (
                    self._rag_repository.keyword_index(connection, keyword_index["public_id"])["id"]
                    if keyword_index
                    else None
                )
                retrieval_profile_id = self._rag_repository.retrieval_profile(
                    connection, profile["public_id"]
                )["id"]
                chunk_set_row = self._rag_repository.chunk_set(connection, chunk_set["public_id"])

            build_checksum = hashlib.sha256(
                dumps_json(
                    {
                        "chunk_set": chunk_set["public_id"],
                        "vector_index": vector_index["public_id"] if vector_index else None,
                        "keyword_index": keyword_index["public_id"] if keyword_index else None,
                        "retrieval_profile": profile["public_id"],
                    }
                ).encode("utf-8")
            ).hexdigest()

            index_row = self._sandbox.update_index(
                index_row["public_id"],
                {
                    "chunk_set_id": chunk_set_row["id"],
                    "embedding_model_id": None,
                    "rag_vector_index_id": vector_index_id,
                    "rag_keyword_index_id": keyword_index_id,
                    "retrieval_profile_id": retrieval_profile_id,
                    "chunk_count": chunk_set_row["total_chunks"],
                    "record_count": corpus["record_count"],
                    "build_checksum": build_checksum,
                    "status": "active",
                },
            )
        except Exception:
            self._sandbox.update_index(index_row["public_id"], {"status": "failed"})
            self._sandbox.update_experiment(experiment_public_id, {"status": "failed"})
            self._sandbox.record_event(
                experiment_public_id,
                {
                    "event_type": "index_build_failed",
                    "summary": f"{index_kind} index build failed",
                    "performed_by_admin_public_id": admin_id,
                },
            )
            raise

        self._sandbox.update_experiment(experiment_public_id, {"status": "ready"})
        self._sandbox.record_event(
            experiment_public_id,
            {
                "event_type": "index_build_completed",
                "summary": f"{index_kind} index built and activated",
                "metadata": {
                    "index_public_id": index_row["public_id"],
                    "chunk_count": index_row["chunk_count"],
                },
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="build_index",
            actor_reference=admin_id,
            resource_public_id=experiment_public_id,
            outcome=AuditOutcome.SUCCESS,
            metadata={"index_kind": index_kind, "embedding_model": embedding_model_id_used},
        )
        return index_row

    def delete_index(self, index_public_id: str, *, admin_id: str) -> dict[str, Any]:
        index_row = self._sandbox.get_index(index_public_id)
        updated = self._sandbox.update_index(index_public_id, {"status": "deleted"})
        self._sandbox.record_event(
            index_row["experiment_public_id"],
            {
                "event_type": "index_deleted",
                "summary": f"index {index_public_id} deleted",
                "performed_by_admin_public_id": admin_id,
            },
        )
        _audit(
            self._audit,
            action="delete_index",
            actor_reference=admin_id,
            resource_public_id=index_row["experiment_public_id"],
            outcome=AuditOutcome.SUCCESS,
        )
        return updated


__all__ = ["RagSandboxIndexService"]
