"""Phase 16 RAG ingestion: knowledge spaces, sources, immutable source
versions, deterministic chunking, registered embeddings, and versioned
vector/keyword indexes.

Composes existing dataset/document infrastructure (Phase 2/5) rather
than duplicating it — a ``dataset_version``-backed source reads real,
already-registered dataset records; a ``pdf_document``-backed source
reads real, already-extracted document pages. Never fetches a remote
URL and never accepts an arbitrary filesystem path.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.rag import RagRepository, public_row
from backend.models.rag import (
    ChunkSetCreate,
    EmbeddingModelCreate,
    EmbeddingRunCreate,
    KeywordIndexCreate,
    KnowledgeSourceCreate,
    KnowledgeSourcePatch,
    KnowledgeSpaceCreate,
    KnowledgeSpacePatch,
    VectorIndexCreate,
)
from core_model.rag import SOURCE_TYPES
from core_model.rag.chunk_validation import (
    ChunkQualityThresholds,
    assess_chunk_quality,
    detect_duplicate_and_near_duplicate,
)
from core_model.rag.chunking import ChunkingConfig, chunk_text
from core_model.rag.embedding import compute_embedding
from core_model.rag.injection_filter import classify_injection_status, detect_injection_signals
from core_model.rag.language_routing import classify_language
from core_model.rag.text_normalization import content_checksum, normalize_source_text
from core_model.rag.vector_index import build_mapping_manifest, mapping_checksum
from core_model.rag.vector_index import (
    validate_vector_index_inputs as validate_vector_index_inputs_fn,
)

_INLINE_SOURCE_TYPES = frozenset(
    {"plain_text", "markdown", "html_snapshot", "manual_admin_content", "course_material", "faq"}
)


class RagIngestionService:
    def __init__(self, repository: RagRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    # --- knowledge spaces -----------------------------------------------------

    def create_space(self, payload: KnowledgeSpaceCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_space(
                connection,
                {
                    "name": payload.name,
                    "slug": payload.slug,
                    "description": payload.description,
                    "supported_languages_json": dumps_json(payload.supported_languages),
                    "access_policy_json": dumps_json(payload.access_policy),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "rag_knowledge_space_created", admin_id, public_id)
            return public_row(self.repository.space(connection, public_id))

    def list_spaces(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return {"items": [public_row(row) for row in self.repository.list_spaces(connection)]}

    def get_space(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.space(connection, public_id))

    def patch_space(
        self, public_id: str, payload: KnowledgeSpacePatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            space = self.repository.space(connection, public_id)
            fields: dict[str, Any] = {}
            if payload.description is not None:
                fields["description"] = payload.description
            if payload.supported_languages is not None:
                fields["supported_languages_json"] = dumps_json(payload.supported_languages)
            if payload.access_policy is not None:
                fields["access_policy_json"] = dumps_json(payload.access_policy)
            if payload.default_retrieval_profile_public_id is not None:
                fields["default_retrieval_profile_public_id"] = (
                    payload.default_retrieval_profile_public_id
                )
            if payload.lifecycle_status is not None:
                if payload.lifecycle_status not in {
                    "draft", "active", "read_only", "deprecated", "archived",
                }:
                    raise ValidationError("invalid knowledge-space lifecycle status")
                fields["lifecycle_status"] = payload.lifecycle_status
                if payload.lifecycle_status == "archived":
                    connection.execute(
                        "UPDATE rag_knowledge_spaces SET archived_at=CURRENT_TIMESTAMP WHERE id=?",
                        (space["id"],),
                    )
            self.repository.update_space(connection, space["id"], fields)
            self._audit(connection, "rag_knowledge_space_updated", admin_id, public_id)
            return public_row(self.repository.space(connection, public_id))

    # --- knowledge sources -----------------------------------------------------

    def create_source(
        self, space_public_id: str, payload: KnowledgeSourceCreate, admin_id: str
    ) -> dict[str, Any]:
        if payload.source_type not in SOURCE_TYPES:
            raise ValidationError(f"source_type must be one of {SOURCE_TYPES}")
        with self.repository.transaction() as connection:
            space = self.repository.space(connection, space_public_id)
            if payload.source_type in _INLINE_SOURCE_TYPES:
                if not payload.content or not payload.content.strip():
                    raise ValidationError("inline source types require non-empty content")
                if len(payload.content) > self.settings.rag_max_source_characters:
                    raise ValidationError("source content exceeds the configured maximum size")
            else:
                if not payload.source_entity_public_id:
                    raise ValidationError(
                        f"source_type '{payload.source_type}' requires source_entity_public_id"
                    )
                self._verify_entity_exists(
                    connection, payload.source_type, payload.source_entity_public_id
                )

            public_id = self.repository.create_source(
                connection,
                {
                    "knowledge_space_id": space["id"],
                    "source_type": payload.source_type,
                    "source_entity_public_id": payload.source_entity_public_id,
                    "title": payload.title,
                    "language": payload.language,
                    "licence_status": payload.licence_status,
                    "metadata_json": dumps_json(payload.metadata),
                    "created_by_admin_public_id": admin_id,
                },
            )
            if payload.source_type in _INLINE_SOURCE_TYPES:
                connection.execute(
                    "UPDATE rag_knowledge_sources SET metadata_json=? WHERE public_id=?",
                    (
                        dumps_json({**payload.metadata, "_staged_content": payload.content}),
                        public_id,
                    ),
                )
            self._audit(connection, "rag_source_registered", admin_id, public_id)
            return public_row(self.repository.source(connection, public_id))

    def _verify_entity_exists(self, connection, source_type: str, entity_public_id: str) -> None:
        if source_type == "dataset_version":
            row = connection.execute(
                "SELECT 1 FROM dataset_versions WHERE public_id=?", (entity_public_id,)
            ).fetchone()
        elif source_type == "pdf_document":
            row = connection.execute(
                "SELECT 1 FROM document_sources WHERE public_id=?", (entity_public_id,)
            ).fetchone()
        else:
            row = True
        if not row:
            raise ValidationError(f"{source_type} entity not found: {entity_public_id}")

    def list_sources(self, space_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            space = self.repository.space(connection, space_public_id)
            rows = self.repository.sources_for_space(connection, space["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_source(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.source(connection, public_id))

    def patch_source(
        self, public_id: str, payload: KnowledgeSourcePatch, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, public_id)
            fields: dict[str, Any] = {}
            if payload.title is not None:
                fields["title"] = payload.title
            if payload.licence_status is not None:
                fields["licence_status"] = payload.licence_status
            if payload.approval_status is not None:
                if payload.approval_status not in {
                    "draft", "review_required", "approved", "rejected", "quarantined", "archived",
                }:
                    raise ValidationError("invalid source approval status")
                fields["approval_status"] = payload.approval_status
            if payload.metadata is not None:
                existing = loads_json(source["metadata_json"])
                staged = existing.get("_staged_content")
                merged = dict(payload.metadata)
                if staged is not None and "_staged_content" not in merged:
                    merged["_staged_content"] = staged
                fields["metadata_json"] = dumps_json(merged)
            self.repository.update_source(connection, source["id"], fields)
            event = (
                "rag_source_approved"
                if payload.approval_status == "approved"
                else "rag_source_rejected"
                if payload.approval_status in {"rejected", "quarantined"}
                else "rag_source_updated"
            )
            self._audit(connection, event, admin_id, public_id)
            return public_row(self.repository.source(connection, public_id))

    # --- source content resolution -----------------------------------------------------

    def _resolve_source_content(self, connection, source) -> dict[str, Any]:
        source_type = source["source_type"]
        if source_type in _INLINE_SOURCE_TYPES:
            staged = loads_json(source["metadata_json"]).get("_staged_content")
            if not staged:
                raise ValidationError("no staged content available for this source")
            return {"raw_content": staged, "extraction_method": "direct"}

        if source_type == "dataset_version":
            dataset = connection.execute(
                "SELECT id FROM dataset_versions WHERE public_id=?",
                (source["source_entity_public_id"],),
            ).fetchone()
            if not dataset:
                raise ValidationError("linked dataset version not found")
            records = connection.execute(
                """SELECT r.content FROM dataset_version_items i
                JOIN dataset_records r ON r.id=i.dataset_record_id
                WHERE i.dataset_version_id=? AND i.split='train'
                ORDER BY i.sequence_number""",
                (dataset["id"],),
            ).fetchall()
            content = "\n\n---\n\n".join(row["content"] for row in records if row["content"])
            if not content:
                raise ValidationError("dataset version has no train-split records to ingest")
            return {"raw_content": content, "extraction_method": "dataset_version_train_split"}

        if source_type == "pdf_document":
            document = connection.execute(
                "SELECT id FROM document_sources WHERE public_id=?",
                (source["source_entity_public_id"],),
            ).fetchone()
            if not document:
                raise ValidationError("linked PDF document not found")
            pages = connection.execute(
                """SELECT page_number, cleaned_text, raw_text FROM document_pages
                WHERE document_source_id=? ORDER BY page_number""",
                (document["id"],),
            ).fetchall()
            parts = []
            for page in pages:
                text = page["cleaned_text"] or page["raw_text"] or ""
                if text.strip():
                    parts.append(f"## Page {page['page_number']}\n\n{text}")
            content = "\n\n".join(parts)
            if not content:
                raise ValidationError("PDF document has no extracted page text to ingest")
            return {"raw_content": content, "extraction_method": "pdf_page_extraction"}

        raise ValidationError(f"unsupported source_type: {source_type}")

    def create_source_version(
        self, source_public_id: str, admin_id: str, *, content_override: str | None = None
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, source_public_id)
            if content_override is not None:
                raw_content = content_override
                extraction_method = "direct"
            else:
                resolved = self._resolve_source_content(connection, source)
                raw_content = resolved["raw_content"]
                extraction_method = resolved["extraction_method"]

            checksum = content_checksum(raw_content)
            latest = self.repository.latest_source_version(connection, source["id"])
            if latest and latest["content_checksum_sha256"] == checksum:
                raise ValidationError(
                    "content is unchanged since the latest source version; "
                    "a new version requires a new content checksum"
                )

            normalized = normalize_source_text(raw_content)
            language_info = classify_language(normalized["normalized_text"][:5000])

            public_id = self.repository.create_source_version(
                connection,
                {
                    "knowledge_source_id": source["id"],
                    "content_checksum_sha256": checksum,
                    "extraction_method": extraction_method,
                    "normalized_content_checksum_sha256": normalized["checksum_sha256"],
                    "character_count": normalized["character_count"],
                    "token_estimate": normalized["character_count"] // 4,
                    "language_distribution_json": dumps_json(
                        {
                            "language_category": language_info["language_category"],
                            "tamil_script_ratio": language_info["tamil_script_ratio"],
                            "latin_script_ratio": language_info["latin_script_ratio"],
                        }
                    ),
                    "status": "ready",
                    "raw_content": raw_content,
                    "normalized_content": normalized["normalized_text"],
                },
            )
            if latest and latest["status"] == "ready":
                self.repository.update_source_version(
                    connection, latest["id"], {"status": "superseded"}
                )
            self._audit(connection, "rag_source_version_created", admin_id, public_id)
            return public_row(self.repository.source_version(connection, public_id))

    def list_source_versions(self, source_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            source = self.repository.source(connection, source_public_id)
            rows = self.repository.versions_for_source(connection, source["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_source_version(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.source_version(connection, public_id))

    def validate_source_version(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.source_version(connection, public_id)
            new_status = "ready" if version["character_count"] > 0 else "failed"
            self.repository.update_source_version(connection, version["id"], {"status": new_status})
            self._audit(connection, "rag_source_version_validated", admin_id, public_id)
            return public_row(self.repository.source_version(connection, public_id))

    # --- chunk sets -----------------------------------------------------

    def create_chunk_set(
        self, source_version_public_id: str, payload: ChunkSetCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.source_version(connection, source_version_public_id)
            if version["status"] != "ready":
                raise ValidationError("source version must be ready before chunking")

            config = ChunkingConfig(
                strategy=payload.chunking_strategy,
                target_tokens=payload.target_tokens,
                maximum_tokens=payload.maximum_tokens,
                minimum_characters=payload.minimum_characters,
                overlap_tokens=payload.overlap_tokens,
                sentence_window_sentences=payload.sentence_window_sentences,
            )
            raw_chunks = chunk_text(
                version["normalized_content"] or "",
                config=config,
                language=version["source_language"],
            )
            if len(raw_chunks) > self.settings.rag_max_chunks_per_source:
                raise ValidationError(
                    f"chunking produced {len(raw_chunks)} chunks, exceeding the configured "
                    f"maximum of {self.settings.rag_max_chunks_per_source}"
                )

            duplicate_info = detect_duplicate_and_near_duplicate(
                raw_chunks, near_duplicate_threshold=0.92
            )
            duplicate_indices = duplicate_info["exact_duplicate_indices"]

            chunk_set_public_id = self.repository.create_chunk_set(
                connection,
                {
                    "source_version_id": version["id"],
                    "chunking_strategy": payload.chunking_strategy,
                    "configuration_json": dumps_json(
                        {
                            "target_tokens": payload.target_tokens,
                            "maximum_tokens": payload.maximum_tokens,
                            "minimum_characters": payload.minimum_characters,
                            "overlap_tokens": payload.overlap_tokens,
                        }
                    ),
                    "created_by_admin_public_id": admin_id,
                },
            )
            chunk_set = self.repository.chunk_set(connection, chunk_set_public_id)

            thresholds = ChunkQualityThresholds(
                minimum_characters=payload.minimum_characters,
                maximum_tokens=payload.maximum_tokens,
            )
            counts = {"accepted": 0, "accepted_with_warning": 0, "rejected": 0, "quarantined": 0}
            source_approved = (
                connection.execute(
                    "SELECT approval_status FROM rag_knowledge_sources WHERE id=?",
                    (version["knowledge_source_id"],),
                ).fetchone()["approval_status"]
                == "approved"
            )
            licence_blocked = version["source_licence_status"] == "blocked"
            supported_languages = ("ta", "en", "tgl", "mixed", "unknown")

            for index, raw_chunk in enumerate(raw_chunks):
                is_duplicate = index in duplicate_indices
                quality = assess_chunk_quality(
                    text=raw_chunk["normalized_text"],
                    language=raw_chunk["language"],
                    supported_languages=supported_languages,
                    thresholds=thresholds,
                    source_approved=source_approved,
                    licence_blocked=licence_blocked,
                    is_duplicate=is_duplicate,
                    estimated_token_count=raw_chunk["estimated_token_count"],
                )
                signals = detect_injection_signals(raw_chunk["normalized_text"])
                injection_status = classify_injection_status(
                    signals["matched_categories"],
                    policy="block" if self.settings.rag_block_injection_risk else "quarantine",
                )
                quality_status = quality["quality_status"]
                issues = quality["issues"]
                if injection_status in {"blocked", "quarantined"} and quality_status == "accepted":
                    quality_status = (
                        "quarantined" if injection_status == "quarantined" else "rejected"
                    )
                    issues = [*issues, "prompt_injection_risk"]
                counts[quality_status] = counts.get(quality_status, 0) + 1

                self.repository.record_chunk(
                    connection,
                    {
                        "chunk_set_id": chunk_set["id"],
                        "source_version_id": version["id"],
                        "sequence_number": raw_chunk["sequence_number"],
                        "heading_path_json": dumps_json(raw_chunk["heading_path"]),
                        "source_location_json": dumps_json(raw_chunk["source_location"]),
                        "language": raw_chunk["language"],
                        "normalized_text": raw_chunk["normalized_text"],
                        "character_count": raw_chunk["character_count"],
                        "estimated_token_count": raw_chunk["estimated_token_count"],
                        "overlap_before_tokens": raw_chunk["overlap_before_tokens"],
                        "overlap_after_tokens": raw_chunk["overlap_after_tokens"],
                        "content_checksum_sha256": raw_chunk["content_checksum_sha256"],
                        "quality_status": quality_status,
                        "quality_issues_json": dumps_json(issues),
                        "injection_status": injection_status,
                        "injection_reasons_json": dumps_json(signals["matched_categories"]),
                    },
                )

            manifest = {"total": len(raw_chunks), "counts": counts}
            manifest_checksum = hashlib.sha256(
                dumps_json(manifest).encode("utf-8")
            ).hexdigest()
            self.repository.update_chunk_set(
                connection,
                chunk_set["id"],
                {
                    "status": "validated",
                    "total_chunks": len(raw_chunks),
                    "accepted_chunks": counts["accepted"],
                    "warning_chunks": counts["accepted_with_warning"],
                    "rejected_chunks": counts["rejected"],
                    "quarantined_chunks": counts["quarantined"],
                    "chunk_manifest_checksum_sha256": manifest_checksum,
                },
            )
            self._audit(
                connection, "rag_chunk_set_created", admin_id, chunk_set_public_id, **counts
            )
            return public_row(self.repository.chunk_set(connection, chunk_set_public_id))

    def list_chunk_sets(self, source_version_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            version = self.repository.source_version(connection, source_version_public_id)
            rows = self.repository.chunk_sets_for_version(connection, version["id"])
            return {"items": [public_row(row) for row in rows]}

    def get_chunk_set(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.chunk_set(connection, public_id))

    def list_chunks(self, chunk_set_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk_set = self.repository.chunk_set(connection, chunk_set_public_id)
            rows = self.repository.chunks_for_set(connection, chunk_set["id"])
            return {"items": [public_row(row) for row in rows]}

    def validate_chunk_set(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk_set = self.repository.chunk_set(connection, public_id)
            self.repository.update_chunk_set(connection, chunk_set["id"], {"status": "validated"})
            self._audit(connection, "rag_chunk_set_validated", admin_id, public_id)
            return public_row(self.repository.chunk_set(connection, public_id))

    # --- embedding models -----------------------------------------------------

    def create_embedding_model(
        self, payload: EmbeddingModelCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            config_checksum = hashlib.sha256(
                dumps_json(
                    {
                        "provider_type": payload.provider_type,
                        "dimensions": payload.dimensions,
                        "architecture": payload.architecture,
                    }
                ).encode("utf-8")
            ).hexdigest()
            public_id = self.repository.create_embedding_model(
                connection,
                {
                    "name": payload.name,
                    "version": payload.version,
                    "provider_type": payload.provider_type,
                    "architecture": payload.architecture,
                    "dimensions": payload.dimensions,
                    "maximum_input_tokens": payload.maximum_input_tokens,
                    "supported_languages_json": dumps_json(payload.supported_languages),
                    "configuration_checksum": config_checksum,
                    "lifecycle_status": "validated",
                },
            )
            self._audit(connection, "rag_embedding_model_registered", admin_id, public_id)
            return public_row(self.repository.embedding_model(connection, public_id))

    def list_embedding_models(self) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_embedding_models(connection)
            return {"items": [public_row(row) for row in rows]}

    # --- embedding runs -----------------------------------------------------

    def create_embedding_run(
        self, chunk_set_public_id: str, payload: EmbeddingRunCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk_set = self.repository.chunk_set(connection, chunk_set_public_id)
            model = self.repository.embedding_model(
                connection, payload.embedding_model_public_id
            )
            eligible_chunks = self._eligible_chunk_ids(connection, chunk_set["id"])
            public_id = self.repository.create_embedding_run(
                connection,
                {
                    "chunk_set_id": chunk_set["id"],
                    "embedding_model_id": model["id"],
                    "configuration_json": dumps_json({"batch_size": payload.batch_size}),
                    "total_chunks": len(eligible_chunks),
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "rag_embedding_run_created", admin_id, public_id)
            return public_row(self.repository.embedding_run(connection, public_id))

    def _eligible_chunk_ids(self, connection, chunk_set_id: int) -> list[int]:
        allowed_statuses = {"accepted"}
        if self.settings.rag_allow_warning_chunks:
            allowed_statuses.add("accepted_with_warning")
        rows = connection.execute(
            "SELECT id FROM rag_chunks WHERE chunk_set_id=? AND quality_status IN "
            f"({','.join('?' for _ in allowed_statuses)}) AND injection_status='clean'",
            (chunk_set_id, *allowed_statuses),
        ).fetchall()
        return [row["id"] for row in rows]

    def get_embedding_run(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.embedding_run(connection, public_id))

    def execute_embedding_run(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.embedding_run(connection, public_id)
            if run["status"] not in {"draft", "failed"}:
                raise ValidationError("embedding run must be draft (or failed) to execute")
            chunk_ids = self._eligible_chunk_ids(connection, run["chunk_set_id"])
            chunks = [
                connection.execute("SELECT * FROM rag_chunks WHERE id=?", (chunk_id,)).fetchone()
                for chunk_id in chunk_ids
            ]
            self.repository.update_embedding_run(connection, run["id"], {"status": "running"})

            embedded = 0
            failed = 0
            started = time.perf_counter()
            input_checksum_parts = []
            for chunk in chunks:
                try:
                    result = compute_embedding(
                        chunk["normalized_text"],
                        provider_type=run["model_provider_type"],
                        dimensions=run["model_dimensions"],
                    )
                except (ValueError, NotImplementedError):
                    failed += 1
                    continue
                self.repository.record_chunk_embedding(
                    connection,
                    {
                        "embedding_run_id": run["id"],
                        "chunk_id": chunk["id"],
                        "dimensions": result["dimensions"],
                        "vector_norm": result["norm"],
                        "vector_checksum_sha256": result["checksum_sha256"],
                        "vector_blob": result["vector_bytes"],
                    },
                )
                input_checksum_parts.append(chunk["content_checksum_sha256"])
                embedded += 1

            runtime_ms = int((time.perf_counter() - started) * 1000)
            input_checksum = hashlib.sha256(
                "".join(sorted(input_checksum_parts)).encode("utf-8")
            ).hexdigest()
            manifest = {
                "embedding_run_public_id": public_id,
                "embedded_chunks": embedded,
                "failed_chunks": failed,
                "dimensions": run["model_dimensions"],
            }
            output_checksum = hashlib.sha256(dumps_json(manifest).encode("utf-8")).hexdigest()
            status = "completed" if failed == 0 else "completed_with_warnings"
            if embedded == 0 and failed > 0:
                status = "failed"
            self.repository.update_embedding_run(
                connection,
                run["id"],
                {
                    "embedded_chunks": embedded,
                    "failed_chunks": failed,
                    "dimensions": run["model_dimensions"],
                    "runtime_milliseconds": runtime_ms,
                    "input_checksum_sha256": input_checksum,
                    "output_manifest_checksum_sha256": output_checksum,
                    "status": status,
                },
            )
            connection.execute(
                "UPDATE rag_embedding_runs SET completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (run["id"],),
            )
            self._audit(
                connection, "rag_embedding_run_executed", admin_id, public_id,
                embedded=embedded, failed=failed,
            )
            return public_row(self.repository.embedding_run(connection, public_id))

    def verify_embedding_run(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.embedding_run(connection, public_id)
            embeddings = self.repository.embeddings_for_run(connection, run["id"])
            manifest = {
                "embedding_run_public_id": public_id,
                "embedded_chunks": run["embedded_chunks"],
                "failed_chunks": run["failed_chunks"],
                "dimensions": run["dimensions"],
            }
            recomputed = hashlib.sha256(dumps_json(manifest).encode("utf-8")).hexdigest()
            return {
                "matches": recomputed == run["output_manifest_checksum_sha256"],
                "recorded_vector_count": len(embeddings),
                "expected_vector_count": run["embedded_chunks"],
            }

    # --- vector indexes -----------------------------------------------------

    def create_vector_index(
        self, embedding_run_public_id: str, payload: VectorIndexCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            run = self.repository.embedding_run(connection, embedding_run_public_id)
            space_id = self._space_id_for_chunk_set(connection, run["chunk_set_id"])
            public_id = self.repository.create_vector_index(
                connection,
                {
                    "knowledge_space_id": space_id,
                    "chunk_set_id": run["chunk_set_id"],
                    "embedding_run_id": run["id"],
                    "distance_metric": payload.distance_metric,
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "rag_vector_index_created", admin_id, public_id)
            return public_row(self.repository.vector_index(connection, public_id))

    def _space_id_for_chunk_set(self, connection, chunk_set_id: int) -> int:
        row = connection.execute(
            """SELECT s.knowledge_space_id FROM rag_chunk_sets cs
            JOIN rag_source_versions v ON v.id=cs.source_version_id
            JOIN rag_knowledge_sources s ON s.id=v.knowledge_source_id
            WHERE cs.id=?""",
            (chunk_set_id,),
        ).fetchone()
        return row["knowledge_space_id"]

    def get_vector_index(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.vector_index(connection, public_id))

    def build_vector_index(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            index = self.repository.vector_index(connection, public_id)
            if index["status"] == "active":
                raise ValidationError("an active vector index is immutable and cannot be rebuilt")
            embeddings = self.repository.embeddings_for_run(connection, index["embedding_run_id"])
            chunks_by_id = {}
            entries = []
            quarantined_or_rejected = 0
            for embedding in embeddings:
                chunk = connection.execute(
                    "SELECT * FROM rag_chunks WHERE id=?", (embedding["chunk_id"],)
                ).fetchone()
                chunks_by_id[embedding["chunk_id"]] = chunk
                if chunk["quality_status"] in {"rejected", "quarantined"}:
                    quarantined_or_rejected += 1
                entries.append(
                    {
                        "chunk_public_id": chunk["public_id"],
                        "vector_checksum_sha256": embedding["vector_checksum_sha256"],
                    }
                )
            manifest = build_mapping_manifest(entries)
            errors = validate_vector_index_inputs_fn(
                vector_count=len(embeddings),
                mapping_count=manifest["count"],
                dimensions=index["dimensions"] or embeddings[0]["dimensions"] if embeddings else 0,
                embedding_dimensions=embeddings[0]["dimensions"] if embeddings else 0,
                quarantined_or_rejected_count=quarantined_or_rejected,
            )
            if not embeddings:
                errors.append("no embeddings available to build an index from")
            if errors:
                self.repository.update_vector_index(connection, index["id"], {"status": "failed"})
                raise ValidationError("; ".join(errors))

            checksum = mapping_checksum(manifest)
            self.repository.update_vector_index(
                connection,
                index["id"],
                {
                    "dimensions": embeddings[0]["dimensions"],
                    "vector_count": len(embeddings),
                    "index_artifact_checksum_sha256": checksum,
                    "mapping_manifest_checksum_sha256": checksum,
                    "storage_key": "sqlite:rag_chunk_embeddings",
                    "status": "validated",
                },
            )
            self._audit(connection, "rag_vector_index_built", admin_id, public_id)
            return public_row(self.repository.vector_index(connection, public_id))

    def validate_vector_index(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            index = self.repository.vector_index(connection, public_id)
            embeddings = self.repository.embeddings_for_run(connection, index["embedding_run_id"])
            entries = []
            for embedding in embeddings:
                chunk = connection.execute(
                    "SELECT public_id FROM rag_chunks WHERE id=?", (embedding["chunk_id"],)
                ).fetchone()
                entries.append(
                    {
                        "chunk_public_id": chunk["public_id"],
                        "vector_checksum_sha256": embedding["vector_checksum_sha256"],
                    }
                )
            recomputed = mapping_checksum(build_mapping_manifest(entries))
            if recomputed != index["mapping_manifest_checksum_sha256"]:
                raise ValidationError("vector index mapping checksum is no longer stable")
            self._audit(connection, "rag_vector_index_validated", admin_id, public_id)
            return public_row(self.repository.vector_index(connection, public_id))

    def activate_vector_index(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            index = self.repository.vector_index(connection, public_id)
            if index["status"] not in {"validated"}:
                raise ValidationError("vector index must be validated before activation")
            connection.execute(
                "UPDATE rag_vector_indexes SET status='deprecated' "
                "WHERE knowledge_space_id=? AND status='active'",
                (index["knowledge_space_id"],),
            )
            self.repository.update_vector_index(connection, index["id"], {"status": "active"})
            connection.execute(
                "UPDATE rag_vector_indexes SET activated_at=CURRENT_TIMESTAMP WHERE id=?",
                (index["id"],),
            )
            self._audit(connection, "rag_vector_index_activated", admin_id, public_id)
            return public_row(self.repository.vector_index(connection, public_id))

    # --- keyword indexes -----------------------------------------------------

    def create_keyword_index(
        self, chunk_set_public_id: str, payload: KeywordIndexCreate, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            chunk_set = self.repository.chunk_set(connection, chunk_set_public_id)
            space_id = self._space_id_for_chunk_set(connection, chunk_set["id"])
            public_id = self.repository.create_keyword_index(
                connection,
                {
                    "knowledge_space_id": space_id,
                    "chunk_set_id": chunk_set["id"],
                    "created_by_admin_public_id": admin_id,
                },
            )
            self._audit(connection, "rag_keyword_index_created", admin_id, public_id)
            return public_row(self.repository.keyword_index(connection, public_id))

    def get_keyword_index(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_row(self.repository.keyword_index(connection, public_id))

    def build_keyword_index(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            index = self.repository.keyword_index(connection, public_id)
            if index["status"] == "active":
                raise ValidationError("an active keyword index is immutable and cannot be rebuilt")
            chunks = self.repository.chunks_for_set(connection, index["chunk_set_id"])
            eligible = [
                chunk
                for chunk in chunks
                if chunk["quality_status"] in (
                    {"accepted", "accepted_with_warning"}
                    if self.settings.rag_allow_warning_chunks
                    else {"accepted"}
                )
                and chunk["injection_status"] == "clean"
            ]
            table_name = f"rag_fts_{index['public_id'].replace('-', '_')}"
            connection.execute(f'DROP TABLE IF EXISTS "{table_name}"')
            connection.execute(
                f'CREATE VIRTUAL TABLE "{table_name}" USING fts5(chunk_public_id UNINDEXED, body)'
            )
            for chunk in eligible:
                connection.execute(
                    f'INSERT INTO "{table_name}"(chunk_public_id, body) VALUES (?, ?)',
                    (chunk["public_id"], chunk["normalized_text"]),
                )
            manifest = {"table": table_name, "document_count": len(eligible)}
            checksum = hashlib.sha256(dumps_json(manifest).encode("utf-8")).hexdigest()
            self.repository.update_keyword_index(
                connection,
                index["id"],
                {
                    "document_count": len(eligible),
                    "index_artifact_checksum_sha256": checksum,
                    "storage_key": table_name,
                    "status": "validated",
                },
            )
            self._audit(connection, "rag_keyword_index_built", admin_id, public_id)
            return public_row(self.repository.keyword_index(connection, public_id))

    def validate_keyword_index(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            index = self.repository.keyword_index(connection, public_id)
            table_exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (index["storage_key"],),
            ).fetchone()
            if not table_exists:
                raise ValidationError("keyword index artifact table is missing")
            self._audit(connection, "rag_keyword_index_validated", admin_id, public_id)
            return public_row(self.repository.keyword_index(connection, public_id))

    def activate_keyword_index(self, public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            index = self.repository.keyword_index(connection, public_id)
            if index["status"] != "validated":
                raise ValidationError("keyword index must be validated before activation")
            connection.execute(
                "UPDATE rag_keyword_indexes SET status='deprecated' "
                "WHERE knowledge_space_id=? AND status='active'",
                (index["knowledge_space_id"],),
            )
            self.repository.update_keyword_index(connection, index["id"], {"status": "active"})
            connection.execute(
                "UPDATE rag_keyword_indexes SET activated_at=CURRENT_TIMESTAMP WHERE id=?",
                (index["id"],),
            )
            self._audit(connection, "rag_keyword_index_activated", admin_id, public_id)
            return public_row(self.repository.keyword_index(connection, public_id))

    # --- audit -----------------------------------------------------

    def _audit(
        self, connection, event: str, admin_id: str, resource_id: str, **metadata: Any
    ) -> None:
        if not self.settings.audit_enabled:
            return
        connection.execute(
            """INSERT INTO audit_logs(action,actor,details,public_id,event_type,actor_type,
            actor_reference,resource_type,resource_public_id,outcome,metadata_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event, "admin", "{}", str(uuid4()), event, "admin", admin_id,
                "rag", resource_id, "success", dumps_json(metadata),
            ),
        )
