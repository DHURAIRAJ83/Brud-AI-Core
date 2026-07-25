"""Phase 21A production tokenizer corpus builder.

Consumes only an approved, finalized/exported Phase 20 corpus release
-- eligibility (provenance/licence/privacy/safety/quality/dedup/
contamination) was already enforced by that release's own build and
readiness gate, so this service never re-implements those checks; it
only materializes the release's already-included segments into a real
Phase 6 dataset version (via `pretraining_bridge.materialize_corpus_release`)
and reports honest sufficiency statistics on top.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.corpus import CorpusRepository
from backend.database.repositories.pretraining_readiness import (
    PretrainingReadinessRepository,
    public_row,
)
from backend.models.pretraining_readiness import TokenizerCorpusBuildCreate
from backend.services.pretraining_bridge import materialize_corpus_release
from core_model.pretraining_readiness.sufficiency import build_sufficiency_report


class TokenizerCorpusService:
    def __init__(
        self,
        corpus_repository: CorpusRepository,
        readiness_repository: PretrainingReadinessRepository,
        settings: Settings,
    ) -> None:
        self.corpus_repository = corpus_repository
        self.readiness_repository = readiness_repository
        self.settings = settings

    def build_corpus(self, payload: TokenizerCorpusBuildCreate, admin_id: str) -> dict[str, Any]:
        with self.corpus_repository.transaction() as connection:
            release_row = self.corpus_repository.release(
                connection, payload.corpus_release_public_id
            )
            build_public_id = self.readiness_repository.create_tokenizer_corpus_build(
                connection,
                {
                    "corpus_release_id": release_row["id"],
                    "created_by_admin_public_id": admin_id,
                },
            )
            build_row = self.readiness_repository.tokenizer_corpus_build(
                connection, build_public_id
            )
            self.readiness_repository.update_tokenizer_corpus_build(
                connection, build_row["id"], {"status": "building"}
            )

            materialized = materialize_corpus_release(
                connection, release_row, name_prefix="Phase21A Tokenizer Corpus"
            )

            build_id = materialized["build_row"]["id"]
            members = connection.execute(
                """SELECT m.segment_id, m.final_licence_decision, s.text FROM
                corpus_build_members m JOIN corpus_segments s ON s.id = m.segment_id
                WHERE m.build_id=? AND m.included=1""",
                (build_id,),
            ).fetchall()
            excluded = connection.execute(
                """SELECT exclusion_reason, COUNT(*) AS c FROM corpus_build_members
                WHERE build_id=? AND included=0 GROUP BY exclusion_reason""",
                (build_id,),
            ).fetchall()
            exclusion_reasons = {row["exclusion_reason"] or "unknown": row["c"] for row in excluded}

            duplicate_exclusions = 0
            dedup_run_id = materialized["build_row"]["deduplication_run_id"]
            if dedup_run_id is not None:
                duplicate_exclusions = connection.execute(
                    """SELECT COUNT(*) FROM corpus_duplicate_members m
                    JOIN corpus_duplicate_clusters c ON c.id = m.cluster_id
                    WHERE c.deduplication_run_id=? AND m.is_representative=0""",
                    (dedup_run_id,),
                ).fetchone()[0]
            contamination_exclusions = 0
            contamination_run_id = materialized["build_row"]["contamination_run_id"]
            if contamination_run_id is not None:
                contamination_exclusions = connection.execute(
                    """SELECT COUNT(*) FROM corpus_contamination_findings
                    WHERE contamination_run_id=? AND blocks_training=1""",
                    (contamination_run_id,),
                ).fetchone()[0]

            records = []
            for member in members:
                language_row = connection.execute(
                    "SELECT language_category FROM corpus_language_assessments "
                    "WHERE segment_id=? ORDER BY id DESC LIMIT 1",
                    (member["segment_id"],),
                ).fetchone()
                domain_row = connection.execute(
                    "SELECT primary_domain FROM corpus_domain_assessments WHERE segment_id=? "
                    "ORDER BY id DESC LIMIT 1",
                    (member["segment_id"],),
                ).fetchone()
                style_row = connection.execute(
                    "SELECT style FROM corpus_style_assessments WHERE segment_id=? "
                    "ORDER BY id DESC LIMIT 1",
                    (member["segment_id"],),
                ).fetchone()
                records.append(
                    {
                        "text": member["text"],
                        "language_category": language_row["language_category"]
                        if language_row
                        else "unknown",
                        "domain": domain_row["primary_domain"] if domain_row else "general",
                        "style": style_row["style"] if style_row else "formal",
                        "source": "corpus_release",
                        "licence_family": member["final_licence_decision"],
                    }
                )

            report = build_sufficiency_report(records)
            self.readiness_repository.update_tokenizer_corpus_build(
                connection,
                build_row["id"],
                {
                    "dataset_version_id": materialized["dataset_version_id"],
                    "status": "completed",
                    "eligible_segment_count": report["total_records"],
                    "excluded_segment_count": sum(exclusion_reasons.values()),
                    "exclusion_reasons_json": dumps_json(exclusion_reasons),
                    "total_records": report["total_records"],
                    "total_characters": report["total_characters"],
                    "total_utf8_bytes": report["total_utf8_bytes"],
                    "total_words": report["total_words"],
                    "unique_character_count": report["unique_character_count"],
                    "tamil_character_count": report["tamil_character_count"],
                    "english_character_count": report["english_character_count"],
                    "digit_count": report["digit_count"],
                    "punctuation_count": report["punctuation_count"],
                    "tamil_only_record_count": report["tamil_only_record_count"],
                    "english_only_record_count": report["english_only_record_count"],
                    "tanglish_record_count": report["tanglish_record_count"],
                    "mixed_record_count": report["mixed_record_count"],
                    "domain_distribution_json": dumps_json(report["domain_distribution"]),
                    "style_distribution_json": dumps_json(report["style_distribution"]),
                    "source_distribution_json": dumps_json(report["source_distribution"]),
                    "licence_distribution_json": dumps_json(report["licence_distribution"]),
                    "duplicate_exclusion_count": duplicate_exclusions,
                    "contamination_exclusion_count": contamination_exclusions,
                    "sufficiency_state": report["sufficiency_state"],
                },
            )
            self._audit(connection, "tokenizer_corpus_build_completed", admin_id, build_public_id)
            return self._detail(connection, build_public_id)

    def _detail(self, connection, public_id: str) -> dict[str, Any]:
        row = self.readiness_repository.tokenizer_corpus_build(connection, public_id)
        detail = public_row(row)
        detail["dataset_version_public_id"] = None
        if row["dataset_version_id"] is not None:
            version_row = connection.execute(
                "SELECT public_id FROM dataset_versions WHERE id=?", (row["dataset_version_id"],)
            ).fetchone()
            detail["dataset_version_public_id"] = version_row["public_id"]
        return detail

    def get_build(self, public_id: str) -> dict[str, Any]:
        with self.corpus_repository.transaction() as connection:
            return self._detail(connection, public_id)

    def list_builds(self) -> dict[str, Any]:
        with self.corpus_repository.transaction() as connection:
            return {
                "items": [
                    self._detail(connection, row["public_id"])
                    for row in self.readiness_repository.list_tokenizer_corpus_builds(connection)
                ]
            }

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
                "pretraining_readiness", resource_id, "success", dumps_json(metadata),
            ),
        )
