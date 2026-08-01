"""Governed RAG handoff (Phase 7, Steps 11-13).

Reuses the *existing* `RagIngestionService.create_source(source_type=
'dataset_version', ...)` integration point verbatim (already accepts a
dataset_version directly, confirmed by direct inspection -- see plan
doc section 1.2) -- this service never re-implements chunking,
embedding, or indexing, and never activates anything. Its only new
responsibility is the governed selection/preflight (delegated to
`GovernedBuildService`) and the duplicate-ingestion-safe bridge from a
completed governed build into a real `rag_knowledge_sources` row.

Building the chunk set / embedding run / vector-keyword index / and
activating a retrieval profile remain the existing, separate, fully
manual RAG workflow (RagPage) -- deliberately out of scope here (see
plan doc section 7): those steps require admin choices (chunking
strategy, embedding model) this service has no basis to make for them.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.governed_builds import GovernedBuildRepository, public_row
from backend.database.repositories.rag import RagRepository
from backend.models.rag import KnowledgeSourceCreate, RetrieveRequest
from backend.services.governed_build_service import GovernedBuildService
from backend.services.rag_ingestion_service import RagIngestionService
from backend.services.rag_retrieval_service import RagRetrievalService


def _audit(connection, event: str, admin_id: str, resource_id: str, **metadata: Any) -> None:
    connection.execute(
        """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
        actor_reference,resource_type,resource_public_id,outcome,metadata_json)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (
            event,
            "admin",
            "{}",
            str(uuid4()),
            event,
            "admin",
            admin_id,
            "governed_rag_handoff",
            resource_id,
            "success",
            dumps_json(metadata),
        ),
    )


class GovernedRagHandoffService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = GovernedBuildRepository(settings.resolved_database_path)
        self.rag_repository = RagRepository(settings.resolved_database_path)
        self.builds = GovernedBuildService(settings)
        self.ingestion = RagIngestionService(self.rag_repository, settings)
        self.retrieval = RagRetrievalService(self.rag_repository, settings)

    def ingest(
        self,
        build_request_public_id: str,
        *,
        knowledge_space_public_id: str,
        title: str,
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request_row = self.repository.build_request(connection, build_request_public_id)
            request = public_row(request_row)
            if request["target_pipeline"] != "rag":
                raise ValidationError("this build request was not created for the rag pipeline")
            is_completed_version = (
                request["status"] == "completed"
                and request["result_entity_type"] == "dataset_version"
            )
            if not is_completed_version:
                raise ValidationError(
                    "the governed build must be completed (a dataset version created) before "
                    "RAG ingestion"
                )
            version_public_id = request["result_entity_public_id"]

            # Duplicate-ingestion prevention (Step 13): a dataset_version
            # already linked to a rag_source is never re-ingested.
            existing_edges = self.repository.edges_downstream_of(
                connection, "dataset_version", version_public_id
            )
            if any(edge["relationship_type"] == "indexed_into" for edge in existing_edges):
                raise ConflictError(
                    "this dataset version has already been ingested into a RAG source"
                )
            existing_links = self.repository.find_links_by_artifact(
                connection, "rag_source", version_public_id
            )
            if existing_links:
                raise ConflictError(
                    "this build request has already produced a RAG source"
                )

        source = self.ingestion.create_source(
            knowledge_space_public_id,
            KnowledgeSourceCreate(
                source_type="dataset_version",
                source_entity_public_id=version_public_id,
                title=title,
                language=request["configuration"].get("language", "unknown"),
                licence_status="unknown",
                metadata={"governed_build_request_public_id": build_request_public_id},
            ),
            admin_id,
        )

        with self.repository.transaction() as connection:
            self.repository.create_artifact_link(
                connection,
                {
                    "build_request_id": request_row["id"],
                    "artifact_type": "rag_source",
                    "artifact_public_id": source["public_id"],
                    "created_by_admin_public_id": admin_id,
                },
            )
            self.repository.create_lineage_edge(
                connection,
                {
                    "upstream_entity_type": "dataset_version",
                    "upstream_entity_id": version_public_id,
                    "downstream_entity_type": "rag_source",
                    "downstream_entity_id": source["public_id"],
                    "relationship_type": "indexed_into",
                    "created_by_admin_public_id": admin_id,
                },
            )
            self.repository.create_lineage_event(
                connection,
                {
                    "build_request_id": request_row["id"],
                    "event_type": "rag_source_created",
                    "performed_by_admin_public_id": admin_id,
                    "notes": f"rag_source={source['public_id']}",
                },
            )
            _audit(
                connection,
                "governed_rag_ingestion",
                admin_id,
                build_request_public_id,
                rag_source_public_id=source["public_id"],
                dataset_version_public_id=version_public_id,
            )
        return source

    def smoke_test(
        self, *, retrieval_profile_public_id: str, query: str, admin_id: str
    ) -> dict[str, Any]:
        """A thin pass-through to the existing `/retrieve` call -- this
        only succeeds once the admin has separately built and activated
        a retrieval profile through the existing RAG workflow; it never
        activates anything itself."""

        return self.retrieval.retrieve(
            RetrieveRequest(retrieval_profile_public_id=retrieval_profile_public_id, query=query),
            admin_id,
        )


__all__ = ["GovernedRagHandoffService"]
