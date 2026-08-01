"""Phase 14 Step 6 contamination/leakage recheck.

Addresses Phase 12/13's deferred checksum gap: this service sources
real checksum sets from (a) the validation/test splits of every
existing ready/archived dataset version, (b) the Phase 9/10 model
evaluation suite fixtures, (c) the RAG evaluation suite fixtures, and
(d) the Phase 13 RAG sandbox query sets -- and compares every
promotion-candidate example against all of them. A candidate is never
silently treated as `clear`: every candidate always receives one of
the four explicit `core_model.training_incremental.CONTAMINATION_RESULTS`
values, and `confirmed_overlap` always blocks promotion (enforced by
`TrainingDatasetPromotionService`, not here -- this service only
reports). See docs/training/phase14_incremental_language_training_plan.md.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.training_incremental import TrainingIncrementalRepository

_REFERENCE_ROW_LIMIT = 5000
_MIN_SUBSTRING_LENGTH = 40


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _digest(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode()).hexdigest()


class TrainingContaminationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._training = TrainingIncrementalRepository(settings.resolved_database_path)

    def _held_out_split_texts(self, connection) -> list[str]:
        rows = connection.execute(
            """SELECT r.instruction, r.input_text, r.output_text FROM dataset_version_items i
            JOIN dataset_records r ON r.id = i.dataset_record_id
            JOIN dataset_versions dv ON dv.id = i.dataset_version_id
            WHERE i.split IN ('validation','test') AND dv.status IN ('ready','archived')
            LIMIT ?""",
            (_REFERENCE_ROW_LIMIT,),
        ).fetchall()
        return [
            " ".join(filter(None, (row["instruction"], row["input_text"], row["output_text"])))
            for row in rows
        ]

    def _evaluation_texts(self, connection) -> list[str]:
        texts: list[str] = []
        for row in connection.execute(
            "SELECT prompt, reference_answer FROM model_evaluation_fixtures LIMIT ?",
            (_REFERENCE_ROW_LIMIT,),
        ):
            texts.append(" ".join(filter(None, (row["prompt"], row["reference_answer"]))))
        for row in connection.execute(
            "SELECT query FROM rag_evaluation_fixtures LIMIT ?", (_REFERENCE_ROW_LIMIT,)
        ):
            texts.append(row["query"] or "")
        for row in connection.execute(
            "SELECT query_text FROM rag_sandbox_queries LIMIT ?", (_REFERENCE_ROW_LIMIT,)
        ):
            texts.append(row["query_text"] or "")
        return texts

    def recheck_candidates(self, candidate_public_ids: list[str]) -> dict[str, Any]:
        """Pure recheck -- returns a manifest, mutates nothing. The
        caller (`TrainingDatasetPromotionService`) decides what to do
        with a `confirmed_overlap`/`possible_overlap` result."""

        results: dict[str, Any] = {}
        with self._training.transaction() as connection:
            held_out_texts = self._held_out_split_texts(connection)
            evaluation_texts = self._evaluation_texts(connection)
            held_out_hashes = {_digest(text) for text in held_out_texts if text.strip()}
            evaluation_hashes = {_digest(text) for text in evaluation_texts if text.strip()}
            normalized_held_out = [
                _normalize(t) for t in held_out_texts if len(t.strip()) >= _MIN_SUBSTRING_LENGTH
            ]
            normalized_evaluation = [
                _normalize(t) for t in evaluation_texts if len(t.strip()) >= _MIN_SUBSTRING_LENGTH
            ]

            for candidate_public_id in candidate_public_ids:
                candidate = self._training.get_candidate(candidate_public_id)
                text = f"{candidate['prompt_text']}\n{candidate['assistant_text']}"
                digest = _digest(text)
                normalized = _normalize(text)

                if digest in evaluation_hashes:
                    result, reason = (
                        "confirmed_overlap",
                        "exact match against an evaluation/benchmark fixture or a Phase 13 "
                        "RAG sandbox query -- evaluation content can never enter training",
                    )
                elif digest in held_out_hashes:
                    result, reason = (
                        "confirmed_overlap",
                        "exact match against a held-out validation/test split record",
                    )
                elif len(normalized) >= _MIN_SUBSTRING_LENGTH and any(
                    normalized in other or other in normalized
                    for other in normalized_evaluation
                ):
                    result, reason = (
                        "possible_overlap",
                        "partial text overlap against an evaluation/benchmark fixture or "
                        "Phase 13 query",
                    )
                elif len(normalized) >= _MIN_SUBSTRING_LENGTH and any(
                    normalized in other or other in normalized for other in normalized_held_out
                ):
                    result, reason = (
                        "possible_overlap",
                        "partial text overlap against a held-out validation/test split record",
                    )
                else:
                    result, reason = "clear", "no overlap detected against any reference set"

                results[candidate_public_id] = {
                    "result": result,
                    "reason": reason,
                    "checksum_sha256": digest,
                }

        blocking = [cid for cid, r in results.items() if r["result"] == "confirmed_overlap"]
        return {
            "candidates": results,
            "blocking_candidate_ids": blocking,
            "reference_counts": {
                "held_out_split_records": len(held_out_texts),
                "evaluation_records": len(evaluation_texts),
            },
        }


__all__ = ["TrainingContaminationService"]
