"""Governed dataset-build lifecycle (Phase 7, Steps 3-10) -- wraps the
*existing* `DatasetVersioningService` rather than reimplementing
version creation, splitting, checksums, or JSONL export.

Lifecycle: create (draft) -> preview (ephemeral, no persistence) ->
preflight (persists a `governed_build_preflight_results` snapshot +
`governed_build_request_items`) -> update_selection (admin revises
which eligible/warning items are included) -> confirm
(preflight_ready -> approved_to_build) -> execute (drives the existing
builder for real, creates a `pipeline_artifact_links` row and lineage
edges) -> cancel, at any point before completion.
"""

from __future__ import annotations

from collections import Counter
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.database.repositories.governed_builds import GovernedBuildRepository, public_row
from backend.models.dataset_versions import BuildCreate, BuildRunRequest, SplitConfiguration
from backend.services.dataset_versioning import DatasetVersioningService
from backend.services.pipeline_eligibility_service import PipelineEligibilityService
from core_model.pipeline_integration import PIPELINE_TARGETS, TERMINAL_BUILD_STATUSES
from core_model.pipeline_integration.split_policy import split_configuration_for_target


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
            "governed_build_request",
            resource_id,
            "success",
            dumps_json(metadata),
        ),
    )


ENTITY_TYPE = "dataset_record"


class GovernedBuildService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = GovernedBuildRepository(settings.resolved_database_path)
        self.dataset_repository = DatasetQualityRepository(settings.resolved_database_path)
        self.versioning = DatasetVersioningService(self.dataset_repository, settings)
        self.eligibility = PipelineEligibilityService(settings)

    # --- request lifecycle ------------------------------------------------

    def create(
        self,
        *,
        target_pipeline: str,
        build_label: str = "",
        configuration: dict[str, Any] | None = None,
        admin_id: str,
    ) -> dict[str, Any]:
        if target_pipeline not in PIPELINE_TARGETS:
            raise ValidationError(f"unsupported target_pipeline: {target_pipeline}")
        with self.repository.transaction() as connection:
            build_code = self.repository.next_build_code(connection)
            public_id = self.repository.create_build_request(
                connection,
                {
                    "build_code": build_code,
                    "target_pipeline": target_pipeline,
                    "build_label": build_label,
                    "configuration_json": dumps_json(configuration or {}),
                    "requested_by_admin_public_id": admin_id,
                },
            )
            request_id = self.repository.build_request(connection, public_id)["id"]
            self.repository.create_lineage_event(
                connection,
                {
                    "build_request_id": request_id,
                    "event_type": "build_request_created",
                    "performed_by_admin_public_id": admin_id,
                    "notes": f"target_pipeline={target_pipeline}",
                },
            )
            _audit(connection, "governed_build_request_created", admin_id, public_id,
                   target_pipeline=target_pipeline)
            return public_row(self.repository.build_request(connection, public_id))

    def get(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = self.repository.build_request(connection, public_id)
            data = public_row(request)
            latest = self.repository.latest_preflight_result(connection, request["id"])
            data["latest_preflight"] = public_row(latest) if latest else None
            data["artifact_links"] = [
                public_row(link)
                for link in self.repository.artifact_links_for_request(connection, request["id"])
            ]
            return data

    def list(
        self,
        *,
        status: str | None = None,
        target_pipeline: str | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows, total = self.repository.list_build_requests(
                connection,
                status=status,
                target_pipeline=target_pipeline,
                limit=page_size,
                offset=(page - 1) * page_size,
            )
            counts = self.repository.counts_by_status(connection)
        return {
            "items": [public_row(row) for row in rows],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total else 0,
            "counts_by_status": counts,
        }

    def update(
        self, public_id: str, fields: dict[str, Any], *, admin_id: str
    ) -> dict[str, Any]:
        allowed = {"build_label", "configuration_json"}
        with self.repository.transaction() as connection:
            request = self.repository.build_request(connection, public_id)
            if request["status"] != "draft":
                raise ValidationError("only a draft build request may be revised")
            update_fields = {key: value for key, value in fields.items() if key in allowed}
            self.repository.update_build_request(connection, request["id"], update_fields)
            _audit(connection, "governed_build_request_updated", admin_id, public_id,
                   fields=sorted(update_fields))
            return public_row(self.repository.build_request(connection, public_id))

    def cancel(self, public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = self.repository.build_request(connection, public_id)
            if request["status"] in TERMINAL_BUILD_STATUSES:
                raise ValidationError(f"build request is already {request['status']}")
            self.repository.update_build_request(connection, request["id"], {"status": "cancelled"})
            self.repository.create_lineage_event(
                connection,
                {
                    "build_request_id": request["id"],
                    "event_type": "build_request_cancelled",
                    "performed_by_admin_public_id": admin_id,
                },
            )
            _audit(connection, "governed_build_request_cancelled", admin_id, public_id)
            return public_row(self.repository.build_request(connection, public_id))

    def history(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = self.repository.build_request(connection, public_id)
            events = self.repository.lineage_events_for_request(connection, request["id"])
            return {"items": [public_row(event) for event in events]}

    # --- candidate selection + preflight ----------------------------------

    def _candidates(self, connection, configuration: dict[str, Any]) -> list[dict[str, Any]]:
        rows = self.repository.candidate_dataset_records(
            connection,
            record_types=configuration.get("record_types"),
            languages=configuration.get("languages"),
            source_public_ids=configuration.get("source_public_ids"),
            include_entity_ids=configuration.get("include_entity_ids"),
            exclude_entity_ids=configuration.get("exclude_entity_ids"),
        )
        candidates = [dict(row) for row in rows]
        domains = configuration.get("domains")
        if domains:
            domain_set = set(domains)
            candidates = [
                c for c in candidates
                if loads_json(c.get("metadata_json") or "{}").get("domain") in domain_set
            ]
        return candidates

    def _run_preflight(
        self, build_request: dict[str, Any], *, admin_id: str, persist: bool
    ) -> dict[str, Any]:
        target_pipeline = build_request["target_pipeline"]
        configuration = build_request["configuration"]
        legacy_overrides = configuration.get("legacy_overrides", {})

        with self.dataset_repository.transaction() as connection:
            candidates = self._candidates(connection, configuration)

        entity_ids = [c["public_id"] for c in candidates]
        prior_evaluation_ids = self.eligibility.prior_evaluation_entity_ids()
        previously_exported_ids = self.eligibility.previously_exported_entity_ids(
            target_pipeline=target_pipeline, entity_type=ENTITY_TYPE, entity_public_ids=entity_ids
        )

        evaluated: list[dict[str, Any]] = []
        for candidate in candidates:
            result = self.eligibility.evaluate_entity(
                ENTITY_TYPE,
                candidate["public_id"],
                target_pipeline,
                admin_id=admin_id,
                persist=persist,
                prior_evaluation_entity_ids=prior_evaluation_ids,
                previously_exported_ids=previously_exported_ids,
                legacy_override_reason=legacy_overrides.get(candidate["public_id"]),
            )
            bucket = result["decision"]
            if bucket == "eligible" and result["warnings"]:
                bucket = "warning"
            evaluated.append({**result, "candidate": candidate, "bucket": bucket})

        eligible = [e for e in evaluated if e["bucket"] in ("eligible", "warning")]
        blocked = [e for e in evaluated if e["bucket"] == "blocked"]
        warning = [e for e in evaluated if e["bucket"] == "warning"]
        excluded = [e for e in evaluated if e["bucket"] == "excluded"]

        source_summary = Counter(
            e["candidate"].get("source_public_id") or "unknown" for e in evaluated
        )
        rights_summary = Counter(
            e["governance_decision"].get("decision", "unknown") for e in evaluated
        )
        duplicate_summary = Counter(
            "unresolved" for e in evaluated
            if "DUPLICATE" in (e["governance_decision"].get("decision_code") or "")
        )
        conflict_summary = Counter(
            "unresolved" for e in evaluated
            if "CONFLICT" in (e["governance_decision"].get("decision_code") or "")
        )
        language_distribution = Counter(
            e["candidate"].get("language", "unknown") for e in evaluated
        )
        record_type_distribution = Counter(
            e["candidate"].get("record_type", "unknown") for e in evaluated
        )
        legacy_count = sum(1 for e in evaluated if e["is_legacy"])

        summary = {
            "eligible_records": [e["candidate"]["public_id"] for e in eligible],
            "blocked_records": [
                {
                    "entity_public_id": e["candidate"]["public_id"],
                    "decision_code": e["decision_code"],
                    "blocking_reasons": e["blocking_reasons"],
                }
                for e in blocked
            ],
            "warning_records": [
                {"entity_public_id": e["candidate"]["public_id"], "warnings": e["warnings"]}
                for e in warning
            ],
            "excluded_records": [
                {
                    "entity_public_id": e["candidate"]["public_id"],
                    "decision_code": e["decision_code"],
                }
                for e in excluded
            ],
            "decision_summary": {
                "eligible": len(eligible),
                "blocked": len(blocked),
                "warning": len(warning),
                "excluded": len(excluded),
                "legacy_unclassified": legacy_count,
            },
            "source_summary": dict(source_summary),
            "rights_summary": dict(rights_summary),
            "quality_summary": {"total_candidates": len(evaluated)},
            "duplicate_summary": dict(duplicate_summary),
            "conflict_summary": dict(conflict_summary),
            "language_distribution": dict(language_distribution),
            "record_type_distribution": dict(record_type_distribution),
        }
        return {"summary": summary, "evaluated": evaluated}

    def preview(self, public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = public_row(self.repository.build_request(connection, public_id))
        result = self._run_preflight(request, admin_id=admin_id, persist=False)
        return result["summary"]

    def preflight(self, public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request_row = self.repository.build_request(connection, public_id)
            request = public_row(request_row)
            request_id = request_row["id"]
        result = self._run_preflight(request, admin_id=admin_id, persist=True)
        summary = result["summary"]

        with self.repository.transaction() as connection:
            preflight_public_id = self.repository.create_preflight_result(
                connection,
                {
                    "build_request_id": request_id,
                    "target_pipeline": request["target_pipeline"],
                    "eligible_count": summary["decision_summary"]["eligible"],
                    "blocked_count": summary["decision_summary"]["blocked"],
                    "warning_count": summary["decision_summary"]["warning"],
                    "excluded_count": summary["decision_summary"]["excluded"],
                    "decision_summary_json": dumps_json(summary["decision_summary"]),
                    "source_summary_json": dumps_json(summary["source_summary"]),
                    "rights_summary_json": dumps_json(summary["rights_summary"]),
                    "quality_summary_json": dumps_json(summary["quality_summary"]),
                    "duplicate_summary_json": dumps_json(summary["duplicate_summary"]),
                    "conflict_summary_json": dumps_json(summary["conflict_summary"]),
                    "language_distribution_json": dumps_json(summary["language_distribution"]),
                    "record_type_distribution_json": dumps_json(
                        summary["record_type_distribution"]
                    ),
                    "created_by_admin_public_id": admin_id,
                },
            )
            preflight_id = self.repository.preflight_result(connection, preflight_public_id)["id"]
            for entry in result["evaluated"]:
                self.repository.create_request_item(
                    connection,
                    {
                        "build_request_id": request_id,
                        "preflight_result_id": preflight_id,
                        "entity_type": ENTITY_TYPE,
                        "entity_public_id": entry["candidate"]["public_id"],
                        "source_public_id": entry["candidate"].get("source_public_id"),
                        "decision": entry["bucket"],
                        "decision_code": entry["decision_code"],
                        "blocking_reasons_json": dumps_json(entry["blocking_reasons"]),
                        "warnings_json": dumps_json(entry["warnings"]),
                        "included": entry["bucket"] in ("eligible", "warning"),
                    },
                )
            new_status = "preflight_ready" if summary["decision_summary"]["eligible"] else "blocked"
            self.repository.update_build_request(connection, request_id, {"status": new_status})
            self.repository.create_lineage_event(
                connection,
                {
                    "build_request_id": request_id,
                    "event_type": "preflight_run",
                    "performed_by_admin_public_id": admin_id,
                    "notes": f"eligible={summary['decision_summary']['eligible']}, "
                             f"blocked={summary['decision_summary']['blocked']}",
                },
            )
            _audit(connection, "governed_build_preflight_run", admin_id, public_id,
                   **summary["decision_summary"])
            return public_row(self.repository.build_request(connection, public_id))

    def update_selection(
        self, public_id: str, item_public_id: str, *, included: bool, admin_id: str
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = self.repository.build_request(connection, public_id)
            item = self.repository.request_item(connection, item_public_id)
            if item["build_request_id"] != request["id"]:
                raise ValidationError("item does not belong to this build request")
            if item["decision"] == "blocked" and included:
                raise ValidationError("a blocked item cannot be manually included")
            self.repository.update_request_item(connection, item["id"], {"included": included})
            self.repository.create_lineage_event(
                connection,
                {
                    "build_request_id": request["id"],
                    "event_type": "selection_updated",
                    "performed_by_admin_public_id": admin_id,
                    "notes": f"{item_public_id}: included={included}",
                },
            )
            _audit(connection, "governed_build_selection_updated", admin_id, public_id,
                   item_public_id=item_public_id, included=included)
            return public_row(self.repository.request_item(connection, item_public_id))

    def blocked_items(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = self.repository.build_request(connection, public_id)
            items = self.repository.items_for_build_request(connection, request["id"])
            return {"items": [public_row(i) for i in items if i["decision"] == "blocked"]}

    def items(self, public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = self.repository.build_request(connection, public_id)
            items = self.repository.items_for_build_request(connection, request["id"])
            return {"items": [public_row(i) for i in items]}

    # --- confirm + execute -------------------------------------------------

    def confirm(self, public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = self.repository.build_request(connection, public_id)
            if request["status"] != "preflight_ready":
                raise ValidationError(
                    "a build request must complete a successful preflight before confirmation"
                )
            self.repository.update_build_request(
                connection, request["id"], {"status": "approved_to_build"}
            )
            self.repository.create_lineage_event(
                connection,
                {
                    "build_request_id": request["id"],
                    "event_type": "build_request_confirmed",
                    "performed_by_admin_public_id": admin_id,
                },
            )
            _audit(connection, "governed_build_request_confirmed", admin_id, public_id)
            return public_row(self.repository.build_request(connection, public_id))

    def execute(self, public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request_row = self.repository.build_request(connection, public_id)
            if request_row["status"] != "approved_to_build":
                raise ValidationError(
                    "a build request must be confirmed (approved_to_build) before execution"
                )
            request = public_row(request_row)
            request_id = request_row["id"]
            included_items = self.repository.items_for_build_request(
                connection, request_id, included_only=True
            )
            included_ids = [item["entity_public_id"] for item in included_items]

        if not included_ids:
            raise ValidationError("no eligible records are included in this build")

        configuration = request["configuration"]
        split = split_configuration_for_target(
            request["target_pipeline"], requested=configuration.get("split_configuration")
        )

        with self.repository.transaction() as connection:
            self.repository.update_build_request(connection, request_id, {"status": "building"})

        split_kwargs = {key: value for key, value in split.items() if value is not None}
        build = self.versioning.create_build(
            BuildCreate(
                dataset_name=configuration.get("dataset_name") or request["build_code"],
                dataset_version=configuration.get("dataset_version") or "v1",
                description=request.get("build_label") or "",
                selection_filters={"include_public_ids": included_ids},
                split_configuration=SplitConfiguration(**split_kwargs),
                minimum_quality_score=configuration.get("minimum_quality_score", 0.0),
                require_ready_quality=configuration.get("require_ready_quality", False),
            ),
            admin_id,
        )
        self.versioning.validate_build(build["public_id"], admin_id)
        completed_build = self.versioning.run_build(
            build["public_id"], BuildRunRequest(confirm=True, allow_warnings=True), admin_id
        )
        version_public_id = completed_build["dataset_version_public_id"]

        with self.repository.transaction() as connection:
            self.repository.create_artifact_link(
                connection,
                {
                    "build_request_id": request_id,
                    "artifact_type": "dataset_version",
                    "artifact_public_id": version_public_id,
                    "created_by_admin_public_id": admin_id,
                },
            )
            for entity_public_id in included_ids:
                self.repository.create_lineage_edge(
                    connection,
                    {
                        "upstream_entity_type": ENTITY_TYPE,
                        "upstream_entity_id": entity_public_id,
                        "downstream_entity_type": "dataset_version",
                        "downstream_entity_id": version_public_id,
                        "relationship_type": "included_in",
                        "created_by_admin_public_id": admin_id,
                    },
                )
            self.repository.update_build_request(
                connection,
                request_id,
                {
                    "status": "completed",
                    "result_entity_type": "dataset_version",
                    "result_entity_public_id": version_public_id,
                },
            )
            connection.execute(
                "UPDATE governed_build_requests SET completed_at=CURRENT_TIMESTAMP WHERE id=?",
                (request_id,),
            )
            self.repository.create_lineage_event(
                connection,
                {
                    "build_request_id": request_id,
                    "event_type": "build_executed",
                    "performed_by_admin_public_id": admin_id,
                    "notes": f"dataset_version={version_public_id}",
                },
            )
            _audit(connection, "governed_build_executed", admin_id, public_id,
                   dataset_version_public_id=version_public_id, record_count=len(included_ids))
            return public_row(self.repository.build_request(connection, public_id))


__all__ = ["GovernedBuildService"]
