# Phase 60 WS02 — Schema Specification

**Execution Phase:** Phase 60 — Capability Expansion & Generalization Improvement  
**Workstream:** WS02 — Dataset Expansion Architecture & Curation Specification  
**Date:** 2026-08-31  
**Status:** ✅ **CANONICAL JSON SCHEMA FULLY SPECIFIED**

---

## 1. Canonical Record Schema

Every record in Phase 60 Dataset v001 MUST adhere to the following JSON structure:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "Phase60DatasetRecord",
  "type": "object",
  "required": [
    "record_id",
    "task_type",
    "capability_id",
    "language",
    "instruction",
    "optional_context",
    "response",
    "expected_behavior",
    "difficulty",
    "source_type",
    "provenance",
    "quality_status",
    "safety_class",
    "split",
    "tokenizer_version",
    "contamination_status",
    "reviewer_status",
    "created_at",
    "content_hash"
  ],
  "properties": {
    "record_id": {"type": "string", "pattern": "^p60_rec_[0-9a-f]{12}$"},
    "task_type": {
      "type": "string",
      "enum": [
        "definition_concepts",
        "factual_qa_knowledge",
        "dialogue_conversational",
        "directives_constraints",
        "structured_response",
        "tool_boundaries_math",
        "safety_refusals",
        "translation_summarization"
      ]
    },
    "capability_id": {
      "type": "string",
      "pattern": "^CAP-(0[1-9]|1[0-9]|2[0-4])$"
    },
    "language": {"type": "string", "enum": ["ta", "en", "mixed", "tgl"]},
    "instruction": {"type": "string", "minLength": 3, "maxLength": 512},
    "optional_context": {"type": "string", "maxLength": 1024},
    "response": {"type": "string", "minLength": 1, "maxLength": 1024},
    "expected_behavior": {"type": "string", "minLength": 5},
    "difficulty": {"type": "string", "enum": ["basic", "intermediate", "advanced"]},
    "source_type": {
      "type": "string",
      "enum": ["curated_human", "verified_corpus", "controlled_synthetic", "rule_transformation"]
    },
    "provenance": {"type": "string", "minLength": 5},
    "quality_status": {"type": "string", "enum": ["PASSED_ALL_QUALITY_GATES", "QUARANTINED"]},
    "safety_class": {"type": "string", "enum": ["benign", "refusal_required", "boundary_dispatch"]},
    "split": {"type": "string", "enum": ["train", "validation", "test"]},
    "tokenizer_version": {"type": "string", "enum": ["v2"]},
    "contamination_status": {"type": "string", "enum": ["CLEAN_ZERO_BENCHMARK_OVERLAP", "FLAGGED"]},
    "reviewer_status": {"type": "string", "enum": ["VERIFIED", "PENDING_REVIEW"]},
    "created_at": {"type": "string", "format": "date-time"},
    "content_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"}
  }
}
```

---

## 2. Backward Compatibility with Phase 55 & 59
- `source_id`: Mapped to historical Phase 55 `source_id` where records originate from the Phase 55 corpus.
- `domain`: Preserved as metadata tag under provenance attributes.
- `rights_status`: Preserved and validated (`verified` / `permissive`).
