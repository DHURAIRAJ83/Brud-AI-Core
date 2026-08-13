"""MB-09: Learning Memory helpers -- pure. Extracts the fields a
permanent memory entry needs from an already-computed MB-08
Continuous Learning Report. The actual permanent, insert-only
persistence lives in the repository/service layer; this module only
shapes what goes into it.
"""

from __future__ import annotations

from typing import Any


def extract_memory_fields(*, continuous_learning_report: dict[str, Any]) -> dict[str, Any]:
    # MB-08's own report stores weak_areas/strong_areas as flat domain-name
    # lists (see core_model.mini_brain.continuous_learning.continuous_learning_report),
    # not dicts -- read verbatim rather than assuming a richer shape.
    weak_domains = list(continuous_learning_report.get("weak_areas", []))
    strong_domains = list(continuous_learning_report.get("strong_areas", []))
    training_decision = continuous_learning_report.get("training_suggestion", {}).get("action")
    return {
        "weak_domains": weak_domains, "strong_domains": strong_domains,
        "training_decision": training_decision,
    }
