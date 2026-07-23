"""Repository for Phase 10 training-reliability persistence.

Covers worker heartbeats, worker leases, recovery attempts, dataset coverage,
stream manifests, run summaries, quality assessments/issues, checkpoint and
run comparisons, and checkpoint retention actions.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

INTERNAL = {
    "id",
    "pretraining_job_id",
    "training_quality_assessment_id",
}


def public_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        raise NotFoundError("training reliability row not found")
    data = dict(row)
    for key in list(data):
        if key in INTERNAL:
            data.pop(key)
        elif key.endswith("_json"):
            data[key.removesuffix("_json")] = loads_json(data.pop(key))
    return data


class TrainingReliabilityRepository(BaseRepository):
    # --- worker heartbeats ------------------------------------------------

    def register_worker(self, connection: sqlite3.Connection, worker_id: str) -> sqlite3.Row:
        existing = connection.execute(
            "SELECT * FROM worker_heartbeats WHERE worker_id=?", (worker_id,)
        ).fetchone()
        if existing:
            connection.execute(
                """UPDATE worker_heartbeats SET status='starting',current_job_public_id=NULL,
                lease_generation=NULL,lease_expires_at=NULL,shutdown_requested=0,
                last_heartbeat_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP
                WHERE worker_id=?""",
                (worker_id,),
            )
        else:
            connection.execute(
                """INSERT INTO worker_heartbeats(public_id,worker_id,status)
                VALUES (?,?,?)""",
                (str(uuid4()), worker_id, "starting"),
            )
        return self.worker(connection, worker_id)

    def worker(self, connection: sqlite3.Connection, worker_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM worker_heartbeats WHERE worker_id=?", (worker_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("worker not registered")
        return row

    def worker_by_public_id(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM worker_heartbeats WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("worker not found")
        return row

    def list_workers(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            "SELECT * FROM worker_heartbeats ORDER BY last_heartbeat_at DESC"
        ).fetchall()

    def heartbeat(
        self,
        connection: sqlite3.Connection,
        worker_id: str,
        *,
        status: str,
        current_job_public_id: str | None = None,
        lease_generation: int | None = None,
        lease_expires_at: str | None = None,
    ) -> None:
        connection.execute(
            """UPDATE worker_heartbeats SET status=?,current_job_public_id=?,
            lease_generation=?,lease_expires_at=?,last_heartbeat_at=CURRENT_TIMESTAMP,
            updated_at=CURRENT_TIMESTAMP WHERE worker_id=?""",
            (status, current_job_public_id, lease_generation, lease_expires_at, worker_id),
        )

    def request_shutdown(self, connection: sqlite3.Connection, worker_id: str) -> None:
        connection.execute(
            """UPDATE worker_heartbeats SET shutdown_requested=1,updated_at=CURRENT_TIMESTAMP
            WHERE worker_id=?""",
            (worker_id,),
        )

    def mark_stopped(self, connection: sqlite3.Connection, worker_id: str) -> None:
        connection.execute(
            """UPDATE worker_heartbeats SET status='stopped',current_job_public_id=NULL,
            lease_generation=NULL,updated_at=CURRENT_TIMESTAMP WHERE worker_id=?""",
            (worker_id,),
        )

    # --- worker leases ------------------------------------------------

    def upsert_lease(
        self,
        connection: sqlite3.Connection,
        *,
        worker_id: str,
        pretraining_job_id: int,
        status: str,
        lease_generation: int,
        lease_expires_at: str,
        owner_public_id: str,
    ) -> None:
        existing = connection.execute(
            "SELECT id FROM training_worker_leases WHERE worker_id=?", (worker_id,)
        ).fetchone()
        if existing:
            connection.execute(
                """UPDATE training_worker_leases SET pretraining_job_id=?,status=?,
                lease_generation=?,lease_expires_at=?,heartbeat_at=CURRENT_TIMESTAMP,
                owner_public_id=?,released_at=NULL,release_reason=NULL WHERE worker_id=?""",
                (
                    pretraining_job_id,
                    status,
                    lease_generation,
                    lease_expires_at,
                    owner_public_id,
                    worker_id,
                ),
            )
        else:
            connection.execute(
                """INSERT INTO training_worker_leases(worker_id,pretraining_job_id,status,
                lease_generation,lease_expires_at,owner_public_id)
                VALUES (?,?,?,?,?,?)""",
                (
                    worker_id,
                    pretraining_job_id,
                    status,
                    lease_generation,
                    lease_expires_at,
                    owner_public_id,
                ),
            )

    def renew_lease(
        self, connection: sqlite3.Connection, worker_id: str, *, lease_expires_at: str
    ) -> None:
        connection.execute(
            """UPDATE training_worker_leases SET lease_expires_at=?,heartbeat_at=CURRENT_TIMESTAMP
            WHERE worker_id=?""",
            (lease_expires_at, worker_id),
        )

    def release_lease(
        self, connection: sqlite3.Connection, worker_id: str, *, reason: str
    ) -> None:
        connection.execute(
            """UPDATE training_worker_leases SET status='idle',released_at=CURRENT_TIMESTAMP,
            release_reason=? WHERE worker_id=?""",
            (reason, worker_id),
        )

    def lease_for_job(
        self, connection: sqlite3.Connection, pretraining_job_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM training_worker_leases
            WHERE pretraining_job_id=? AND released_at IS NULL
            ORDER BY id DESC LIMIT 1""",
            (pretraining_job_id,),
        ).fetchone()

    # --- recovery attempts ------------------------------------------------

    def record_recovery_attempt(
        self, connection: sqlite3.Connection, pretraining_job_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO training_recovery_attempts(public_id,pretraining_job_id,recovery_type,
            status,source_worker_id,recovering_worker_id,source_checkpoint_public_id,
            previous_lease_generation,new_lease_generation,recovered_step,recovered_tokens,
            validation_summary_json,error_code,error_message,completed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
            (
                public_id,
                pretraining_job_id,
                values["recovery_type"],
                values["status"],
                values.get("source_worker_id"),
                values["recovering_worker_id"],
                values.get("source_checkpoint_public_id"),
                values["previous_lease_generation"],
                values["new_lease_generation"],
                values.get("recovered_step"),
                values.get("recovered_tokens"),
                values.get("validation_summary_json", "{}"),
                values.get("error_code"),
                values.get("error_message"),
            ),
        )
        return public_id

    def recovery_attempts(
        self, connection: sqlite3.Connection, pretraining_job_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM training_recovery_attempts WHERE pretraining_job_id=?
            ORDER BY started_at DESC, id DESC""",
            (pretraining_job_id,),
        ).fetchall()

    def recovery_attempt(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM training_recovery_attempts WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("recovery attempt not found")
        return row

    def stale_jobs(self, connection: sqlite3.Connection) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM pretraining_jobs
            WHERE status='running' AND lease_expires_at IS NOT NULL
            AND lease_expires_at < CURRENT_TIMESTAMP
            ORDER BY lease_expires_at"""
        ).fetchall()

    # --- coverage -----------------------------------------------------

    def record_coverage(
        self,
        connection: sqlite3.Connection,
        pretraining_job_id: int,
        split: str,
        values: dict[str, Any],
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO training_dataset_coverage(public_id,pretraining_job_id,split,
            total_records,eligible_records,encoded_records,excluded_records,zero_token_records,
            oversized_records,split_records,dropped_records,total_tokens,usable_tokens,
            padding_tokens,language_distribution_json,record_type_distribution_json,
            source_type_distribution_json,exclusion_reasons_json,coverage_ratio,
            stream_checksum_sha256)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                pretraining_job_id,
                split,
                values["total_records"],
                values["eligible_records"],
                values["encoded_records"],
                values["excluded_records"],
                values["zero_token_records"],
                values["oversized_records"],
                values["split_records"],
                values["dropped_records"],
                values["total_tokens"],
                values["usable_tokens"],
                values["padding_tokens"],
                values["language_distribution_json"],
                values["record_type_distribution_json"],
                values["source_type_distribution_json"],
                values["exclusion_reasons_json"],
                values["coverage_ratio"],
                values["stream_checksum_sha256"],
            ),
        )
        return public_id

    def latest_coverage(
        self, connection: sqlite3.Connection, pretraining_job_id: int
    ) -> list[sqlite3.Row]:
        rows = connection.execute(
            """SELECT * FROM training_dataset_coverage WHERE pretraining_job_id=?
            ORDER BY created_at DESC, id DESC""",
            (pretraining_job_id,),
        ).fetchall()
        seen: set[str] = set()
        latest: list[sqlite3.Row] = []
        for row in rows:
            if row["split"] not in seen:
                seen.add(row["split"])
                latest.append(row)
        return latest

    # --- stream manifests -----------------------------------------------

    def record_stream_manifest(
        self, connection: sqlite3.Connection, pretraining_job_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO training_stream_manifests(public_id,pretraining_job_id,split,
            dataset_version_public_id,dataset_checksum_sha256,tokenizer_version_public_id,
            tokenizer_checksum_sha256,sequence_length,packing_policy,partial_block_policy,
            eos_policy,overlength_policy,shuffle,seed,eligible_records,encoded_records,
            excluded_records,total_tokens,usable_tokens,block_count,stream_checksum_sha256,
            manifest_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                public_id,
                pretraining_job_id,
                values["split"],
                values["dataset_version_public_id"],
                values["dataset_checksum_sha256"],
                values["tokenizer_version_public_id"],
                values["tokenizer_checksum_sha256"],
                values["sequence_length"],
                values["packing_policy"],
                values["partial_block_policy"],
                values["eos_policy"],
                values["overlength_policy"],
                1 if values["shuffle"] else 0,
                values["seed"],
                values["eligible_records"],
                values["encoded_records"],
                values["excluded_records"],
                values["total_tokens"],
                values["usable_tokens"],
                values["block_count"],
                values["stream_checksum_sha256"],
                values.get("manifest_json", "{}"),
            ),
        )
        return public_id

    def stream_manifests(
        self, connection: sqlite3.Connection, pretraining_job_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM training_stream_manifests WHERE pretraining_job_id=?
            ORDER BY created_at DESC, id DESC""",
            (pretraining_job_id,),
        ).fetchall()

    # --- run summaries -----------------------------------------------

    def record_run_summary(
        self, connection: sqlite3.Connection, pretraining_job_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO training_run_summaries(public_id,pretraining_job_id,status,
            initial_step,final_step,initial_training_loss,final_training_loss,best_training_loss,
            initial_validation_loss,final_validation_loss,best_validation_loss,
            initial_perplexity,final_perplexity,processed_tokens,optimizer_steps,elapsed_seconds,
            average_tokens_per_second,peak_process_memory_bytes,checkpoint_count,pause_count,
            resume_count,recovery_count,non_finite_event_count,summary_json,completed_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
            (
                public_id,
                pretraining_job_id,
                values["status"],
                values["initial_step"],
                values["final_step"],
                values.get("initial_training_loss"),
                values.get("final_training_loss"),
                values.get("best_training_loss"),
                values.get("initial_validation_loss"),
                values.get("final_validation_loss"),
                values.get("best_validation_loss"),
                values.get("initial_perplexity"),
                values.get("final_perplexity"),
                values["processed_tokens"],
                values["optimizer_steps"],
                values["elapsed_seconds"],
                values.get("average_tokens_per_second"),
                values.get("peak_process_memory_bytes"),
                values["checkpoint_count"],
                values["pause_count"],
                values["resume_count"],
                values["recovery_count"],
                values["non_finite_event_count"],
                values.get("summary_json", "{}"),
            ),
        )
        return public_id

    def latest_run_summary(
        self, connection: sqlite3.Connection, pretraining_job_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM training_run_summaries WHERE pretraining_job_id=?
            ORDER BY created_at DESC, id DESC LIMIT 1""",
            (pretraining_job_id,),
        ).fetchone()

    # --- quality assessments -----------------------------------------------

    def record_quality_assessment(
        self, connection: sqlite3.Connection, pretraining_job_id: int, values: dict[str, Any]
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO training_quality_assessments(public_id,pretraining_job_id,
            assessment_version,overall_score,dimension_scores_json,readiness_status,summary_json)
            VALUES (?,?,?,?,?,?,?)""",
            (
                public_id,
                pretraining_job_id,
                values["assessment_version"],
                values["overall_score"],
                values["dimension_scores_json"],
                values["readiness_status"],
                values.get("summary_json", "{}"),
            ),
        )
        assessment_id = connection.execute(
            "SELECT id FROM training_quality_assessments WHERE public_id=?", (public_id,)
        ).fetchone()[0]
        for issue in values.get("issues", []):
            connection.execute(
                """INSERT INTO training_quality_issues(public_id,pretraining_job_id,
                training_quality_assessment_id,issue_code,severity,message,details_json)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    str(uuid4()),
                    pretraining_job_id,
                    assessment_id,
                    issue["code"],
                    issue["severity"],
                    issue["message"],
                    issue.get("details_json", "{}"),
                ),
            )
        return public_id

    def latest_quality_assessment(
        self, connection: sqlite3.Connection, pretraining_job_id: int
    ) -> sqlite3.Row | None:
        return connection.execute(
            """SELECT * FROM training_quality_assessments WHERE pretraining_job_id=?
            ORDER BY created_at DESC, id DESC LIMIT 1""",
            (pretraining_job_id,),
        ).fetchone()

    def quality_issues(
        self, connection: sqlite3.Connection, assessment_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM training_quality_issues WHERE training_quality_assessment_id=?
            ORDER BY CASE severity WHEN 'blocking' THEN 0 WHEN 'error' THEN 1
            WHEN 'warning' THEN 2 ELSE 3 END, id""",
            (assessment_id,),
        ).fetchall()

    # --- comparisons -----------------------------------------------

    def record_checkpoint_comparison(
        self,
        connection: sqlite3.Connection,
        *,
        left: str,
        right: str,
        compatibility: str,
        comparison_json: str,
        admin_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO training_checkpoint_comparisons(public_id,left_checkpoint_public_id,
            right_checkpoint_public_id,compatibility,comparison_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (public_id, left, right, compatibility, comparison_json, admin_id),
        )
        return public_id

    def checkpoint_comparison(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM training_checkpoint_comparisons WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("checkpoint comparison not found")
        return row

    def record_run_comparison(
        self,
        connection: sqlite3.Connection,
        *,
        left: str,
        right: str,
        compatibility: str,
        comparison_json: str,
        admin_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO training_run_comparisons(public_id,left_job_public_id,
            right_job_public_id,compatibility,comparison_json,created_by_admin_public_id)
            VALUES (?,?,?,?,?,?)""",
            (public_id, left, right, compatibility, comparison_json, admin_id),
        )
        return public_id

    def run_comparison(self, connection: sqlite3.Connection, public_id: str) -> sqlite3.Row:
        row = connection.execute(
            "SELECT * FROM training_run_comparisons WHERE public_id=?", (public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("run comparison not found")
        return row

    # --- retention -----------------------------------------------

    def record_retention_action(
        self,
        connection: sqlite3.Connection,
        pretraining_job_id: int,
        *,
        mode: str,
        checkpoint_public_id: str,
        classification: str,
        protection_reason: str | None,
        dry_run: bool,
        admin_id: str,
    ) -> str:
        public_id = str(uuid4())
        connection.execute(
            """INSERT INTO checkpoint_retention_actions(public_id,pretraining_job_id,mode,
            checkpoint_public_id,classification,protection_reason,dry_run,
            created_by_admin_public_id)
            VALUES (?,?,?,?,?,?,?,?)""",
            (
                public_id,
                pretraining_job_id,
                mode,
                checkpoint_public_id,
                classification,
                protection_reason,
                1 if dry_run else 0,
                admin_id,
            ),
        )
        return public_id

    def retention_actions(
        self, connection: sqlite3.Connection, pretraining_job_id: int
    ) -> list[sqlite3.Row]:
        return connection.execute(
            """SELECT * FROM checkpoint_retention_actions WHERE pretraining_job_id=?
            ORDER BY created_at DESC, id DESC""",
            (pretraining_job_id,),
        ).fetchall()
