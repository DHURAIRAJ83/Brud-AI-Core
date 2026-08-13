"""MB-15: Learning Memory -- pure. MB-15 never retrains anything; this
module only assembles the permanent rollup record a future training
phase could reuse: how many predictions a provider made, how many an
admin approved unchanged versus corrected versus rejected, and the
resulting correction rate. Every input is already-computed data from
earlier stages -- nothing here is a new measurement.
"""

from __future__ import annotations

from typing import Any


def build_learning_memory(*, predictions: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(predictions)
    approved = sum(1 for p in predictions if p["review_status"] == "approved" and p["source"] == "ai_predicted")
    corrected = sum(1 for p in predictions if p["source"] == "admin_corrected")
    rejected = sum(1 for p in predictions if p["review_status"] in ("rejected", "deleted"))
    correction_rate = round(corrected / total, 3) if total else None

    return {
        "total_predictions": total, "approved_count": approved, "corrected_count": corrected,
        "rejected_count": rejected, "correction_rate": correction_rate,
    }
