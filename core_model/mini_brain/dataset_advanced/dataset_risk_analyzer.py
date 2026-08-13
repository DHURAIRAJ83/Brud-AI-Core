"""MB-05.1: Dataset Risk Analyzer -- Email, Phone, Password, API Keys,
Secrets, Private Tokens. Reuses
`ExternalDatasetPIIScanService.scan()` (Phase 12 Step 16/17's own
wrapper over `core_model.corpus.pii_detection.detect_pii()` and
`core_model.corpus.secret_detection.detect_secrets()`) UNCHANGED --
never a second email/phone/API-key/secret regex implementation.
"""

from __future__ import annotations

from typing import Any

from backend.services.dataset_sample_pii_safety_service import ExternalDatasetPIIScanService

_PII_SERVICE = ExternalDatasetPIIScanService()

_SEVERITY_MAP = {"blocked": "critical", "likely": "high", "possible": "medium"}
MAX_REPORTED_RISK_ITEMS = 200


def _record_text(record: dict[str, Any]) -> str:
    parts = [record.get("instruction"), record.get("input_text"), record.get("output_text")]
    return "\n".join(part for part in parts if part)


def analyze_risk(records: list[dict[str, Any]]) -> dict[str, Any]:
    risk_items: list[dict[str, Any]] = []
    category_counts: dict[str, int] = {}

    for record in records:
        text = _record_text(record)
        if not text.strip():
            continue
        result = _PII_SERVICE.scan(text)
        for finding in result["findings"]:
            severity = _SEVERITY_MAP.get(finding["status"], "medium")
            risk_items.append({
                "public_id": record.get("public_id"), "category": finding["category"],
                "severity": severity, "status": finding["status"],
            })
            category_counts[finding["category"]] = category_counts.get(finding["category"], 0) + 1

    total = len(records) or 1
    risk_score = round(len(risk_items) / total, 3)

    return {
        "risk_score": risk_score,
        "risk_items": risk_items[:MAX_REPORTED_RISK_ITEMS],
        "risk_items_truncated": len(risk_items) > MAX_REPORTED_RISK_ITEMS,
        "risk_item_count": len(risk_items),
        "category_counts": category_counts,
        "reason": (
            f"{len(risk_items)} PII/secret finding(s) across {total} record(s), via the existing, "
            "unmodified ExternalDatasetPIIScanService"
        ),
    }
