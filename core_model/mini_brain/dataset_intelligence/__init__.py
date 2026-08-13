"""MB-05: Dataset Intelligence -- turns Brud Mini Brain into an Admin
Dataset Expert. NOT a trainer, NOT a new AI model, NOT a dataset
editor, NOT automatic. Every module here only reads already-fetched
dataset records/sources and produces a deterministic, explainable
analysis -- never a mutation, never an approval, never a hidden score.

Reuse discipline (audited before writing anything): language
detection reuses `core_model.corpus.language_detection.assess_language`
unchanged; per-record quality checks reuse
`backend.services.dataset_sample_quality_service.ExternalDatasetQualityService`
unchanged; exact-duplicate grouping reuses
`backend.services.dataset_sample_duplicate_service.ExternalDatasetDuplicateService.group_exact_duplicates`
unchanged. Domain classification, readiness verdicts, token
estimation, scoring, and recommendations are genuinely new -- nothing
in the existing codebase already does these for Dataset Studio
records at the admin-advisory level MB-05 operates at.
"""
