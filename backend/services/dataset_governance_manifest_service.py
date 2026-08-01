"""Governance-aware manifest extension for a completed governed build
(Phase 7, Step 9).

Never touches the existing `dataset_versions.manifest_json`/
`checksum_sha256` (owned entirely by `DatasetVersioningService`) --
this service only assembles and persists an *additive* extension,
stored in `governed_build_requests.manifest_extension_json`, generated
once from already-persisted, real data (the build's own preflight
summary and Phase 2 source-rights links) and never recomputed or
edited afterward.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import dumps_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.data_sources import public_row as source_public_row
from backend.database.repositories.dataset_quality import DatasetQualityRepository
from backend.database.repositories.governance import GovernanceRepository
from backend.database.repositories.governed_builds import GovernedBuildRepository, public_row
from backend.services.dataset_versioning import DatasetVersioningService
from core_model.pipeline_integration import PIPELINE_TARGET_USE_MAP
from core_model.pipeline_integration.manifest import build_manifest_extension


class DatasetGovernanceManifestService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = GovernedBuildRepository(settings.resolved_database_path)
        self.dataset_repository = DatasetQualityRepository(settings.resolved_database_path)
        self.versioning = DatasetVersioningService(self.dataset_repository, settings)
        self.sources = DataSourceRepository(settings.resolved_database_path)
        self.governance = GovernanceRepository(settings.resolved_database_path)

    def _attribution_entries(self, entity_public_ids: list[str]) -> list[dict[str, Any]]:
        """Real attribution only -- an entity with no Phase 2
        `source_record_links` row simply contributes no entry; nothing
        is ever invented to fill the gap."""

        seen_sources: set[str] = set()
        entries: list[dict[str, Any]] = []
        with self.sources.transaction() as connection:
            for entity_public_id in entity_public_ids:
                for link in self.sources.links_for_entity(
                    connection, "dataset_record", entity_public_id
                ):
                    source = source_public_row(
                        self.sources.source_by_id(connection, link["data_source_id"])
                    )
                    if source["public_id"] in seen_sources:
                        continue
                    seen_sources.add(source["public_id"])
                    rights_row = self.sources.rights_for_source(connection, link["data_source_id"])
                    rights = source_public_row(rights_row) if rights_row else {}
                    entries.append(
                        {
                            "source_public_id": source["public_id"],
                            "source_title": source.get("title"),
                            "license_name": rights.get("license_name"),
                            "attribution_text": rights.get("attribution_text"),
                            "attribution_required": bool(rights.get("attribution_required")),
                        }
                    )
        return entries

    def _override_count(self, entity_public_ids: list[str], *, target_pipeline: str) -> int:
        target_use = PIPELINE_TARGET_USE_MAP[target_pipeline]
        count = 0
        with self.governance.transaction() as connection:
            for entity_public_id in entity_public_ids:
                latest = self.governance.latest_target_approval(
                    connection, "dataset_record", entity_public_id, target_use
                )
                if latest is not None and latest["is_override"]:
                    count += 1
        return count

    def generate(self, build_request_public_id: str, *, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request_row = self.repository.build_request(connection, build_request_public_id)
            request = public_row(request_row)
            is_completed_version = (
                request["status"] == "completed"
                and request["result_entity_type"] == "dataset_version"
            )
            if not is_completed_version:
                raise ValidationError(
                    "a manifest can only be generated for a completed build with a dataset "
                    "version result"
                )
            if request.get("manifest_extension") not in (None, {}):
                return request["manifest_extension"]

            latest_preflight = self.repository.latest_preflight_result(
                connection, request_row["id"]
            )
            if latest_preflight is None:
                raise ValidationError("no preflight result exists for this build request")
            preflight = public_row(latest_preflight)
            items = self.repository.items_for_build_request(
                connection, request_row["id"], included_only=True
            )
            included_ids = [item["entity_public_id"] for item in items]

        attribution_entries = self._attribution_entries(included_ids)
        verification_status_counts = {
            "not_independently_tracked_at_manifest_layer": len(included_ids)
        }

        extension = build_manifest_extension(
            build_request_code=request["build_code"],
            target_pipeline=request["target_pipeline"],
            dataset_version_public_id=request["result_entity_public_id"],
            record_type_counts=preflight["record_type_distribution"],
            language_counts=preflight["language_distribution"],
            domain_counts={},
            source_counts=preflight["source_summary"],
            rights_status_counts=preflight["rights_summary"],
            verification_status_counts=verification_status_counts,
            quality_summary=preflight["quality_summary"],
            duplicate_resolution_summary=preflight["duplicate_summary"],
            conflict_resolution_summary=preflight["conflict_summary"],
            approval_summary=preflight["decision_summary"],
            legacy_record_count=preflight["decision_summary"].get("legacy_unclassified", 0),
            override_count=self._override_count(
                included_ids, target_pipeline=request["target_pipeline"]
            ),
            attribution_entries=attribution_entries,
            created_at=datetime.now(UTC).isoformat(),
        )

        with self.repository.transaction() as connection:
            connection.execute(
                "UPDATE governed_build_requests SET manifest_extension_json=? WHERE public_id=?",
                (dumps_json(extension), build_request_public_id),
            )
            self.repository.create_lineage_event(
                connection,
                {
                    "build_request_id": request_row["id"],
                    "event_type": "manifest_generated",
                    "performed_by_admin_public_id": admin_id,
                },
            )
        return extension

    def get(self, build_request_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request = public_row(self.repository.build_request(connection, build_request_public_id))
        version_manifest: dict[str, Any] = {}
        if request.get("result_entity_type") == "dataset_version" and request.get(
            "result_entity_public_id"
        ):
            version_manifest = self.versioning.manifest(request["result_entity_public_id"])
        return {
            "dataset_version_manifest": version_manifest,
            "governance_extension": request.get("manifest_extension") or {},
        }


__all__ = ["DatasetGovernanceManifestService"]
