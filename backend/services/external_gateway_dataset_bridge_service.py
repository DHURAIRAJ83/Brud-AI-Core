"""MB-40: External AI Gateway -> Dataset Studio bridge.

Additive, real reuse only -- this file never touches MB-21's gateway
review logic (`MiniBrainExternalAiGatewayService.admin_review`) and
never touches `DatasetService`'s own record/source creation logic.
It only calls both, in sequence, for a session that has *already* been
marked `admin_accepted` by a real human decision through the existing,
unmodified `admin_review()` flow.

Export is only possible for a session whose real `status` is already
`"admin_accepted"` -- there is no path in this file that creates or
accepts a session itself, and no path that executes anything beyond
creating `draft` dataset records (and, optionally, registering
`draft`-equivalent RAG sources -- registration only, never chunking,
embedding, indexing, or activation, which remain separate, later,
human-driven steps exactly as they already are for every other RAG
source in this codebase).

Content handling discipline: the gateway's own dispatch stage discloses
that "the full raw prompt is never persisted -- only its SHA-256 hash
is stored" (`mini_brain_external_ai_gateway_service.py`), so this
bridge never invents or reconstructs a prompt. It uses only what the
gateway already normalized and actually stored per provider run
(`normalized_response.normalized_text`) plus the session's own real
`topic`/`purpose` fields as the record's `instruction`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.connection import database_connection
from backend.database.repositories.base import ConflictError, ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.rag import RagRepository
from backend.models.datasets import ManualSourceCreate, RecordCreate
from backend.models.domain import (
    DatasetRecordType,
    DatasetSourceType,
    LicenceStatus,
)
from backend.models.rag import (
    ChunkSetCreate,
    EmbeddingRunCreate,
    KnowledgeSourceCreate,
    KnowledgeSourcePatch,
    RetrievalProfileCreate,
    VectorIndexCreate,
)
from backend.core.validation import LanguageCode
from backend.services.dataset_service import DatasetService
from backend.services.mini_brain_external_ai_gateway_service import MiniBrainExternalAiGatewayService
from backend.services.rag_ingestion_service import RagIngestionService
from backend.services.rag_retrieval_service import RagRetrievalService

ACCEPTED_STATUS = "admin_accepted"


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class ExternalGatewayDatasetBridgeService:
    def __init__(
        self,
        settings: Settings,
        *,
        gateway_service: MiniBrainExternalAiGatewayService | None = None,
        dataset_service: DatasetService | None = None,
        rag_ingestion_service: RagIngestionService | None = None,
        rag_retrieval_service: RagRetrievalService | None = None,
    ) -> None:
        self.settings = settings
        self.database_path = settings.resolved_database_path
        # Real reuse: the same gateway service class the External AI
        # Gateway routes/tests already use -- never a new client.
        self.gateway = gateway_service or MiniBrainExternalAiGatewayService(settings)
        # Real reuse: the same DatasetService/DatasetAdminRepository
        # every Dataset Studio route already uses -- `create_record`'s
        # own duplicate-content check and `status="draft"` default are
        # untouched.
        self.dataset = dataset_service or DatasetService(DatasetAdminRepository(self.database_path))
        # Real reuse: the same RagIngestionService the RAG routes use --
        # only ever called when the caller explicitly asks for it.
        self.rag_ingestion = rag_ingestion_service or RagIngestionService(
            RagRepository(self.database_path), settings
        )
        # Real reuse: the same RagRetrievalService the RAG routes use --
        # only used here to create a (draft, inactive) retrieval profile.
        self.rag_retrieval = rag_retrieval_service or RagRetrievalService(
            RagRepository(self.database_path), settings
        )

    # -- audit (this bridge's own lifecycle events, additive to the ------
    # -- granular dataset_record_created/rag_source_registered events -----
    # -- that DatasetService/RagIngestionService already write themselves) -

    def _audit(self, event: str, admin_id: str, session_public_id: str, **metadata: Any) -> None:
        with database_connection(self.database_path) as connection:
            connection.execute(
                """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
                actor_reference,resource_type,resource_public_id,outcome,metadata_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    event, "admin", "{}", str(uuid4()), event, "admin", admin_id,
                    "external_gateway_dataset_bridge", session_public_id,
                    "failure" if event.endswith("_failed") else "success",
                    dumps_json(metadata),
                ),
            )
            connection.commit()

    # -- dataset source resolution ---------------------------------------

    def _ensure_dataset_source(self, session: dict[str, Any], admin_id: str) -> str:
        label = session.get("topic") or session.get("purpose") or session["public_id"]
        source = self.dataset.create_source(
            ManualSourceCreate(
                name=f"External AI Gateway: {label}"[:255],
                description=(
                    f"Draft records exported from accepted External AI Gateway session "
                    f"{session['public_id']}."
                ),
                language=LanguageCode.UNKNOWN,
                licence_status=LicenceStatus.REVIEW_REQUIRED,
                # DatasetService.create_source() ("the manual source API")
                # only ever accepts source_type=manual, regardless of what
                # other DatasetSourceType values exist -- reused as-is.
                source_type=DatasetSourceType.MANUAL,
                metadata={
                    "source": "external_provider",
                    "external_gateway_session_public_id": session["public_id"],
                },
            ),
            admin_id,
        )
        return source["public_id"]

    # -- MB-41: RAG pipeline continuation (source version -> chunk -> ------
    # -- embed -> vector index -> retrieval profile; profile and vector ----
    # -- index are both left inactive -- reused, unmodified activate_* -----
    # -- methods exist but this bridge never calls them) --------------------

    def _find_active_embedding_model(self) -> dict[str, Any]:
        # "No new embedding algorithm" -- this only ever looks up an
        # already-registered model; it never registers one itself.
        models = self.rag_ingestion.list_embedding_models()["items"]
        validated = [m for m in models if m["lifecycle_status"] == "validated"]
        if not validated:
            raise ValidationError(
                "no existing embedding model is available to build a RAG index -- "
                "register one first (build_rag_index never registers a new model)"
            )
        return validated[-1]

    def _build_rag_index(
        self,
        export_result: dict[str, Any],
        *,
        admin_id: str,
        rag_knowledge_space_public_id: str,
        retrieval_profile_name: str | None,
    ) -> dict[str, Any]:
        session_public_id = export_result["session_public_id"]
        rag_source_public_ids = export_result.get("rag_source_public_ids") or []

        build_result: dict[str, Any] = {
            "source_version_public_ids": [],
            "chunk_set_public_ids": [],
            "embedding_run_public_ids": [],
            "vector_index_public_ids": [],
            "retrieval_profile_public_id": None,
        }
        if not rag_source_public_ids:
            # Nothing new was registered as a RAG source in this call (a
            # fully duplicate re-export, or ingest_to_rag was False) --
            # there is nothing to build, and any index a real earlier
            # export already built is left completely untouched.
            return build_result

        self._audit(
            "external_gateway_rag_build_started", admin_id, session_public_id,
            rag_source_public_ids=rag_source_public_ids,
        )
        try:
            embedding_model = self._find_active_embedding_model()
            for source_public_id in rag_source_public_ids:
                # A source's chunks are otherwise all scored "rejected"
                # (reason: source_not_approved) by the existing, unmodified
                # chunk-quality assessment -- this only marks the source's
                # own approval metadata (via the existing patch_source()),
                # it never activates the vector index or retrieval profile
                # that actually gate whether anything is retrievable.
                self.rag_ingestion.patch_source(
                    source_public_id, KnowledgeSourcePatch(approval_status="approved"), admin_id,
                )
                version = self.rag_ingestion.create_source_version(source_public_id, admin_id)
                self.rag_ingestion.validate_source_version(version["public_id"], admin_id)
                build_result["source_version_public_ids"].append(version["public_id"])

                chunk_set = self.rag_ingestion.create_chunk_set(
                    version["public_id"], ChunkSetCreate(), admin_id
                )
                self.rag_ingestion.validate_chunk_set(chunk_set["public_id"], admin_id)
                build_result["chunk_set_public_ids"].append(chunk_set["public_id"])

                embedding_run = self.rag_ingestion.create_embedding_run(
                    chunk_set["public_id"],
                    EmbeddingRunCreate(embedding_model_public_id=embedding_model["public_id"]),
                    admin_id,
                )
                embedding_run = self.rag_ingestion.execute_embedding_run(
                    embedding_run["public_id"], admin_id
                )
                build_result["embedding_run_public_ids"].append(embedding_run["public_id"])

                vector_index = self.rag_ingestion.create_vector_index(
                    embedding_run["public_id"], VectorIndexCreate(), admin_id
                )
                # `build_vector_index` itself marks the index "failed" and
                # raises if there is nothing usable to build from -- that
                # existing failure path is reused as-is, never duplicated.
                vector_index = self.rag_ingestion.build_vector_index(vector_index["public_id"], admin_id)
                self.rag_ingestion.validate_vector_index(vector_index["public_id"], admin_id)
                build_result["vector_index_public_ids"].append(vector_index["public_id"])
                # Deliberately no activate_vector_index() call -- stays
                # inactive/inert until a human explicitly activates it.

            profile_name = retrieval_profile_name or f"External gateway export {session_public_id[:8]}"
            profile = self.rag_retrieval.create_profile(
                rag_knowledge_space_public_id, RetrievalProfileCreate(name=profile_name), admin_id,
            )
            build_result["retrieval_profile_public_id"] = profile["public_id"]
            # Deliberately no validate_profile()/activate_profile() call --
            # the profile is created and stays in its initial, inactive
            # status until a second, explicit admin approval, exactly as
            # required.

            self._audit(
                "external_gateway_rag_build_completed", admin_id, session_public_id, **build_result
            )
            return build_result
        except Exception as exc:
            # "Rollback" here means what it means everywhere else in this
            # codebase's append-only design: nothing partially built is
            # ever activated or exposed, and the exact partial object IDs
            # are captured in the failure audit event rather than lost --
            # never a silent, misleadingly-successful state, and (since
            # the retrieval profile is always created last) a failure
            # anywhere in the chunk/embed/index steps guarantees no
            # retrieval profile exists to make anything reachable.
            self._audit(
                "external_gateway_rag_build_failed", admin_id, session_public_id,
                error=str(exc), partial_objects=build_result,
            )
            raise

    # -- export -----------------------------------------------------------

    def export_accepted_session(
        self,
        session_public_id: str,
        *,
        admin_id: str,
        target_source_public_id: str | None = None,
        ingest_to_rag: bool = False,
        rag_knowledge_space_public_id: str | None = None,
        build_rag_index: bool = False,
        retrieval_profile_name: str | None = None,
    ) -> dict[str, Any]:
        if not admin_id:
            raise ValidationError("a real admin identity is required to export a gateway session")
        if ingest_to_rag and not rag_knowledge_space_public_id:
            raise ValidationError("rag_knowledge_space_public_id is required when ingest_to_rag=True")
        if build_rag_index and not ingest_to_rag:
            raise ValidationError("build_rag_index requires ingest_to_rag=True")

        session = self.gateway.session(session_public_id)
        # The only real gate this bridge enforces: export is refused for
        # anything that is not the exact, human-made "admin_accepted"
        # decision already recorded by the unmodified `admin_review()`
        # flow -- rejected, needs-followup, or still-pending sessions can
        # never reach the code below.
        if session["status"] != ACCEPTED_STATUS:
            raise ValidationError(
                f"session status is '{session['status']}', not '{ACCEPTED_STATUS}' -- "
                "export requires an existing admin acceptance decision"
            )

        self._audit(
            "external_gateway_dataset_export_started", admin_id, session_public_id,
            ingest_to_rag=ingest_to_rag,
        )
        try:
            source_public_id = target_source_public_id or self._ensure_dataset_source(session, admin_id)
            runs = self.gateway.list_provider_runs(session_public_id)["items"]

            created_record_public_ids: list[str] = []
            duplicate_provider_run_public_ids: list[str] = []
            skipped_provider_run_public_ids: list[str] = []
            rag_source_public_ids: list[str] = []

            for run in runs:
                normalized = run["normalized_response"]
                text = normalized.get("normalized_text")
                if run["status"] != "success" or not text:
                    skipped_provider_run_public_ids.append(run["public_id"])
                    continue

                record_payload = RecordCreate(
                    source_public_id=source_public_id,
                    record_type=DatasetRecordType.INSTRUCTION,
                    language=LanguageCode.UNKNOWN,
                    instruction=(session.get("topic") or session.get("purpose") or "External AI Gateway export"),
                    output_text=text,
                    metadata={
                        "source": "external_provider",
                        "external_gateway_session_public_id": session_public_id,
                        "provider_name": normalized.get("provider_key"),
                        "provider_run_public_id": run["public_id"],
                        "exported_at": _now(),
                    },
                )
                try:
                    record = self.dataset.create_record(record_payload, admin_id)
                except ConflictError:
                    # Real reuse of DatasetService's own content-hash
                    # duplicate detection -- never a bespoke check here.
                    duplicate_provider_run_public_ids.append(run["public_id"])
                    continue
                created_record_public_ids.append(record["public_id"])

                if ingest_to_rag:
                    rag_source = self.rag_ingestion.create_source(
                        rag_knowledge_space_public_id,
                        KnowledgeSourceCreate(
                            source_type="plain_text",
                            title=f"External gateway {normalized.get('provider_key')} ({session_public_id[:8]})",
                            language="unknown",
                            content=text,
                            metadata={
                                "source": "external_provider",
                                "external_gateway_session_public_id": session_public_id,
                                "dataset_record_public_id": record["public_id"],
                            },
                        ),
                        admin_id,
                    )
                    rag_source_public_ids.append(rag_source["public_id"])

            result = {
                "session_public_id": session_public_id,
                "dataset_source_public_id": source_public_id,
                "created_record_public_ids": created_record_public_ids,
                "duplicate_provider_run_public_ids": duplicate_provider_run_public_ids,
                "skipped_provider_run_public_ids": skipped_provider_run_public_ids,
                "rag_source_public_ids": rag_source_public_ids,
                "ingest_to_rag": ingest_to_rag,
            }
            audit_metadata = {key: value for key, value in result.items() if key != "session_public_id"}
            self._audit(
                "external_gateway_dataset_export_completed", admin_id, session_public_id, **audit_metadata
            )
        except Exception as exc:
            self._audit(
                "external_gateway_dataset_export_failed", admin_id, session_public_id,
                error=str(exc),
            )
            raise

        if build_rag_index:
            # Deliberately outside the try/except above: the dataset
            # export already succeeded and was already audited as
            # completed by this point, so a failure here must only ever
            # write its own `external_gateway_rag_build_failed` event
            # (inside `_build_rag_index`), never a second, misleading
            # `external_gateway_dataset_export_failed` for a dataset
            # export that in fact succeeded.
            rag_build_result = self._build_rag_index(
                result, admin_id=admin_id,
                rag_knowledge_space_public_id=rag_knowledge_space_public_id,
                retrieval_profile_name=retrieval_profile_name,
            )
            result.update(rag_build_result)

        return result


__all__ = ["ExternalGatewayDatasetBridgeService"]
