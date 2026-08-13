"""MB-11: Synthetic Dataset Planner -- pure. Designs structure, fields,
schema, validation rules, expected size, quality rules, and a
verification plan for a synthetic dataset that would close a
particular gap. Never generates a single record -- Dataset Studio, or
a future content-generation phase, remains the only place records are
actually written, and only after an admin approves this design.
"""

from __future__ import annotations

from typing import Any

BASE_FIELDS = ("public_id", "instruction", "input_text", "output_text", "domain", "difficulty", "language")
REQUIRED_FIELDS = ("instruction", "output_text", "domain")


def plan_synthetic_dataset(
    *, target_domain: str, content_type: str, predicted_record_count: int,
) -> dict[str, Any]:
    expected_size = max(50, round(predicted_record_count * 0.1))

    return {
        "target_domain": target_domain,
        "content_type": content_type,
        "structure": f"{content_type} records for domain '{target_domain}', one record per concept/example",
        "schema": {
            "fields": list(BASE_FIELDS),
            "required_fields": list(REQUIRED_FIELDS),
            "field_types": {
                "public_id": "string (uuid)", "instruction": "string", "input_text": "string (optional)",
                "output_text": "string", "domain": "string", "difficulty": "enum(Easy,Medium,Hard,Very Hard)",
                "language": "string (ISO 639-1)",
            },
        },
        "validation_rules": [
            "instruction and output_text must be non-empty",
            "domain must match target_domain",
            "no exact-duplicate output_text within the batch (reuse ExternalDatasetDuplicateService before ingest)",
            "no PII or secrets (reuse ExternalDatasetPIIScanService before ingest)",
        ],
        "expected_size": expected_size,
        "quality_rules": [
            "clean_ratio target >= 0.85 before this batch is considered Ready",
            "duplicate_ratio target <= 0.05 within the batch",
            f"every record must be traceable to a real source for domain '{target_domain}' -- no unsourced claims",
        ],
        "verification_plan": [
            "human review of a sample before the batch enters Dataset Studio",
            "run through MB-05 Dataset Intelligence (.training()) once ingested, before this domain's status changes",
            "route through RAG Sandbox evaluation before any training use, matching the RAG-first precedent MB-06/MB-10 already established",
        ],
        "verified": False,
        "status": "design_only",
    }
