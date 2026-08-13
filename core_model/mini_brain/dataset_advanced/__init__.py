"""MB-05.1: Advanced Dataset Intelligence -- turns Brud Mini Brain into
an Advanced Dataset Advisor. MB-05 analyzes dataset QUALITY; MB-05.1
analyzes dataset INTELLIGENCE: conflicts, bias, coverage, difficulty,
curriculum sequencing, knowledge gaps, PII/secret risk, topic
structure, and priority-ranked recommendations. Every module here is
pure, deterministic, and explainable -- no AI, no embeddings, no
semantic/vector search, exactly like MB-05.

Reuse discipline (audited before writing anything): PII/secret
detection reuses `ExternalDatasetPIIScanService.scan()`
(`backend/services/dataset_sample_pii_safety_service.py`, itself a
thin wrapper over `core_model.corpus.pii_detection`/`secret_detection`)
unchanged -- never a second email/phone/API-key pattern
implementation. Exact-duplicate/normalized-duplicate grouping reuses
`ExternalDatasetDuplicateService` (already reused by MB-05) unchanged.
Conflict, bias, coverage, difficulty, curriculum, knowledge-gap,
graph, priority, and scoring logic are genuinely new -- MB-05 itself
does not compute any of these.
"""
