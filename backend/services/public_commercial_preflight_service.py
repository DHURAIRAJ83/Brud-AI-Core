"""Public export / commercial release preflight (Phase 7, Step 20).

Never a legal opinion and never a publishing action -- this only
surfaces a complete blocked-item report by combining the governed
build's own preflight (already rights/quality/duplicate/conflict
gated) with each entity's *current*, expiry-aware approval status
(`GovernanceApprovalService.status()`), since an override recorded
earlier may since have expired.
"""

from __future__ import annotations

from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import loads_json
from backend.database.repositories.base import ValidationError
from backend.database.repositories.governed_builds import GovernedBuildRepository, public_row
from backend.services.governance_service import GovernanceApprovalService
from core_model.pipeline_integration import PIPELINE_TARGET_USE_MAP

_PUBLIC_COMMERCIAL_TARGETS = frozenset({"commercial_release", "public_export"})


class PublicCommercialPreflightService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = GovernedBuildRepository(settings.resolved_database_path)
        self.approvals = GovernanceApprovalService(settings)

    def check(self, build_request_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            request_row = self.repository.build_request(connection, build_request_public_id)
            request = public_row(request_row)
            if request["target_pipeline"] not in _PUBLIC_COMMERCIAL_TARGETS:
                raise ValidationError(
                    "this preflight only applies to commercial_release/public_export builds"
                )
            items = self.repository.items_for_build_request(connection, request_row["id"])

        target_use = PIPELINE_TARGET_USE_MAP[request["target_pipeline"]]
        blocked_items: list[dict[str, Any]] = []
        allowed_items: list[dict[str, Any]] = []
        for item in items:
            entity_public_id = item["entity_public_id"]
            status = self.approvals.status(item["entity_type"], entity_public_id)
            target_status = status["targets"].get(target_use, {})
            decision = target_status.get("decision", "not_requested")
            entry = {
                "entity_public_id": entity_public_id,
                "decision": decision,
                "decision_code": target_status.get("decision_code"),
                "expired": target_status.get("expired", False),
                "warnings": loads_json(item["warnings_json"] or "[]"),
            }
            if decision == "allowed" and not target_status.get("expired"):
                allowed_items.append(entry)
            else:
                blocked_items.append(entry)

        return {
            "build_request_public_id": build_request_public_id,
            "target_pipeline": request["target_pipeline"],
            "target_use": target_use,
            "allowed_count": len(allowed_items),
            "blocked_count": len(blocked_items),
            "allowed_items": allowed_items,
            "blocked_items": blocked_items,
        }


__all__ = ["PublicCommercialPreflightService"]
