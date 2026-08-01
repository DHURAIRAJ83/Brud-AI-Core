"""Phase 19 Step 21 -- deterministic daily knowledge-gap report.

Pure aggregation over already-persisted registry data -- no web
search, no model call, no scheduler. `generate()` is Admin/API
triggered only; nothing in this phase schedules it automatically.
"""

from __future__ import annotations

from datetime import UTC, datetime

from backend.core.config import Settings
from backend.database.repositories.knowledge_gap import KnowledgeGapRepository

MAX_TOP_CASES = 20


class KnowledgeGapDailyReportService:
    def __init__(self, settings: Settings) -> None:
        self.repository = KnowledgeGapRepository(settings.resolved_database_path)

    def generate(self, *, report_date: str | None = None) -> dict[str, object]:
        report_date = report_date or datetime.now(UTC).date().isoformat()

        overview = self.repository.aggregate_overview()
        top_cases = self.repository.list_cases(limit=MAX_TOP_CASES)
        review_required = self.repository.list_cases(limit=MAX_TOP_CASES, status="review_required")
        tamil = self.repository.tamil_capability_summary()
        web_demand = self.repository.web_demand_summary()
        tool_demand = self.repository.tool_demand_summary()
        language = self.repository.language_failure_summary()

        summary = {
            "new_cases": overview["by_status"].get("new", 0),
            "top_priority_clusters": [
                {
                    "public_id": c["public_id"],
                    "priority_band": c["priority_band"],
                    "priority_score": c["priority_score"],
                    "canonical_question": c["canonical_question"],
                }
                for c in top_cases
                if c["priority_band"] in ("critical", "high")
            ],
            "most_frequent_unresolved_questions": [
                {
                    "public_id": c["public_id"],
                    "frequency": c["frequency"],
                    "canonical_question": c["canonical_question"],
                }
                for c in sorted(top_cases, key=lambda c: c["frequency"], reverse=True)[:10]
                if c["status"] not in ("resolved", "rejected", "archived")
            ],
            "tamil_language_gaps": tamil,
            "wrong_language_failures": language,
            "rag_insufficiency": overview["by_event_type"].get("knowledge_gap", 0),
            "web_unavailable_demand": web_demand,
            "tool_unavailable_demand": tool_demand,
            "operational_failures": overview["by_event_type"].get("operational_failure", 0),
            "safety_events_recorded_elsewhere": True,
            "cases_needing_admin_review": [c["public_id"] for c in review_required],
            "cases_eligible_for_rag_research": overview["cases_eligible_for_rag_research"],
            "cases_eligible_for_training_assessment": overview[
                "cases_eligible_for_training_assessment"
            ],
        }
        return self.repository.record_daily_report(report_date, summary)

    def latest(self) -> dict[str, object] | None:
        return self.repository.get_latest_daily_report()

    def list_reports(self, *, limit: int = 30) -> list[dict[str, object]]:
        return self.repository.list_daily_reports(limit=limit)


__all__ = ["MAX_TOP_CASES", "KnowledgeGapDailyReportService"]
