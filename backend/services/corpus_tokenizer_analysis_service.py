"""Phase 20 tokenizer compatibility analysis service.

Never trains a new tokenizer -- always analyzes an existing,
registered ``tokenizer_versions`` row via Phase 7's own
``TokenizerService.processor_for_version`` (checksum-verified,
unchanged). Segments are streamed and processed one at a time in
bounded batches rather than ever materializing the whole corpus in
memory at once.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.corpus import CorpusRepository, public_row
from backend.database.repositories.tokenizers import TokenizerRepository
from backend.models.corpus import TokenizerAnalysisCreate
from backend.services.tokenizer_registry import TokenizerService
from core_model.corpus.tokenizer_analysis import (
    aggregate_metrics,
    analyze_token_ids,
    compute_script_token_ratios,
    round_trip_integrity_rate,
)

MAX_ROUND_TRIP_SAMPLE = 200
BATCH_SIZE = 500


class CorpusTokenizerAnalysisService:
    def __init__(self, repository: CorpusRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings
        self.tokenizer_service = TokenizerService(
            TokenizerRepository(settings.resolved_database_path), settings
        )

    def _segments_for_scope(
        self, connection, *, collection_id: int | None, build_id: int | None
    ) -> list[dict[str, Any]]:
        if build_id is not None:
            rows = connection.execute(
                """SELECT s.id, s.public_id, s.text FROM corpus_build_members m
                JOIN corpus_segments s ON s.id = m.segment_id
                WHERE m.build_id=? AND m.included=1""",
                (build_id,),
            ).fetchall()
        elif collection_id is not None:
            rows = connection.execute(
                """SELECT s.id, s.public_id, s.text FROM corpus_collection_members m
                JOIN corpus_segments s ON s.id = m.segment_id
                WHERE m.collection_id=? AND m.eligibility_status='eligible'""",
                (collection_id,),
            ).fetchall()
        else:
            rows = connection.execute("SELECT id, public_id, text FROM corpus_segments").fetchall()
        return [dict(row) for row in rows]

    def create_analysis(self, payload: TokenizerAnalysisCreate, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            tokenizer_row = self.tokenizer_service.repository.version(
                connection, payload.tokenizer_version_public_id
            )
            collection_id = None
            build_id = None
            if payload.collection_public_id:
                collection_id = self.repository.collection(
                    connection, payload.collection_public_id
                )["id"]
            if payload.build_public_id:
                build_id = self.repository.build(connection, payload.build_public_id)["id"]

            values = {
                "tokenizer_version_id": tokenizer_row["id"],
                "collection_id": collection_id,
                "build_id": build_id,
                "created_by_admin_public_id": admin_id,
            }
            analysis_public_id = self.repository.create_tokenizer_analysis(connection, values)
            analysis_row = self.repository.tokenizer_analysis(connection, analysis_public_id)
            self.repository.update_tokenizer_analysis(
                connection, analysis_row["id"], {"status": "running"}
            )
            segments = self._segments_for_scope(
                connection, collection_id=collection_id, build_id=build_id
            )

        if not segments:
            raise ValidationError("no eligible segments found for tokenizer analysis")

        processor = self.tokenizer_service.processor_for_version(
            payload.tokenizer_version_public_id
        )
        unk_id = processor.unk_id()

        overall_rows: list[dict[str, Any]] = []
        by_language: dict[str, list[dict[str, Any]]] = {}
        by_domain: dict[str, list[dict[str, Any]]] = {}
        by_style: dict[str, list[dict[str, Any]]] = {}
        round_trip_pairs: list[tuple[str, str]] = []

        with self.repository.transaction() as connection:
            for start in range(0, len(segments), BATCH_SIZE):
                batch = segments[start : start + BATCH_SIZE]
                for segment in batch:
                    ids = processor.encode(segment["text"], out_type=int)
                    metrics = analyze_token_ids(
                        segment["text"], ids, unk_id=unk_id,
                        max_sequence_length=payload.max_sequence_length,
                    )
                    overall_rows.append(metrics)

                    if len(round_trip_pairs) < MAX_ROUND_TRIP_SAMPLE:
                        round_trip_pairs.append((segment["text"], processor.decode(ids)))

                    language_row = connection.execute(
                        "SELECT language_category FROM corpus_language_assessments "
                        "WHERE segment_id=? ORDER BY id DESC LIMIT 1",
                        (segment["id"],),
                    ).fetchone()
                    language = language_row["language_category"] if language_row else "unknown"
                    by_language.setdefault(language, []).append(metrics)

                    domain_row = connection.execute(
                        "SELECT primary_domain FROM corpus_domain_assessments "
                        "WHERE segment_id=? ORDER BY id DESC LIMIT 1",
                        (segment["id"],),
                    ).fetchone()
                    domain = domain_row["primary_domain"] if domain_row else "general"
                    by_domain.setdefault(domain, []).append(metrics)

                    style_row = connection.execute(
                        "SELECT style FROM corpus_style_assessments WHERE segment_id=? "
                        "ORDER BY id DESC LIMIT 1",
                        (segment["id"],),
                    ).fetchone()
                    style = style_row["style"] if style_row else "formal"
                    by_style.setdefault(style, []).append(metrics)

            overall = aggregate_metrics(overall_rows)
            round_trip_rate = round_trip_integrity_rate(round_trip_pairs)

            self.repository.update_tokenizer_analysis(
                connection,
                analysis_row["id"],
                {
                    "status": "completed",
                    "total_characters": overall["total_characters"],
                    "total_tokens": overall["total_tokens"],
                    "total_segments": len(segments),
                    "characters_per_token": overall["characters_per_token"],
                    "unknown_token_rate": overall["unknown_token_rate"],
                    "long_sequence_rate": overall["long_sequence_rate"],
                    "round_trip_integrity_rate": round_trip_rate,
                },
            )
            self.repository.record_tokenizer_analysis_metric(
                connection,
                {
                    "analysis_id": analysis_row["id"], "breakdown_type": "overall",
                    "breakdown_value": "overall", **_metric_fields(overall),
                },
            )
            for language, rows in by_language.items():
                metrics = aggregate_metrics(rows)
                self.repository.record_tokenizer_analysis_metric(
                    connection,
                    {
                        "analysis_id": analysis_row["id"], "breakdown_type": "language",
                        "breakdown_value": language, **_metric_fields(metrics),
                    },
                )
            for domain, rows in by_domain.items():
                metrics = aggregate_metrics(rows)
                self.repository.record_tokenizer_analysis_metric(
                    connection,
                    {
                        "analysis_id": analysis_row["id"], "breakdown_type": "domain",
                        "breakdown_value": domain, **_metric_fields(metrics),
                    },
                )
            for style, rows in by_style.items():
                metrics = aggregate_metrics(rows)
                self.repository.record_tokenizer_analysis_metric(
                    connection,
                    {
                        "analysis_id": analysis_row["id"], "breakdown_type": "style",
                        "breakdown_value": style, **_metric_fields(metrics),
                    },
                )

            script_ratios = compute_script_token_ratios(
                {language: aggregate_metrics(rows) for language, rows in by_language.items()}
            )
            self._audit(
                connection, "corpus_tokenizer_analysis_completed", admin_id, analysis_public_id,
                script_ratios=script_ratios,
            )
            result = self.get_analysis(analysis_public_id, connection=connection)
            result["script_token_ratios"] = script_ratios
            return result

    def get_analysis(self, public_id: str, *, connection=None) -> dict[str, Any]:
        if connection is not None:
            row = self.repository.tokenizer_analysis(connection, public_id)
            result = public_row(row)
            result["metrics"] = [
                public_row(metric)
                for metric in self.repository.metrics_for_tokenizer_analysis(connection, row["id"])
            ]
            return result
        with self.repository.transaction() as connection:
            return self.get_analysis(public_id, connection=connection)

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
                "corpus", resource_id, "success", dumps_json(metadata),
            ),
        )


def _metric_fields(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_characters": metrics["total_characters"],
        "total_tokens": metrics["total_tokens"],
        "characters_per_token": metrics["characters_per_token"],
        "unknown_token_rate": metrics["unknown_token_rate"],
        "long_sequence_rate": metrics["long_sequence_rate"],
        "truncation_risk_rate": metrics["truncation_risk_rate"],
    }
