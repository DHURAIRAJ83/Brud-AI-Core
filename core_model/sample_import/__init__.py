"""Phase 12: pure enums, bounds, and status rules for Approved Sample
Import, Quarantine, File Safety, PII & Data Quality Validation.

Nothing in this package (or anything it describes) ever downloads a
full external dataset, clones a repository, executes downloaded
content, extracts an unbounded archive, inserts a quarantined record
into `dataset_records`/RAG/training tables, activates RAG, creates a
training dataset version, starts training, or releases a model. A
sample-import always links to exactly one existing, *finalized* Phase
11 verification case; approval never implies dataset-level approval,
sample-validation-passed never implies RAG-production approval, and
RAG-sandbox-eligible never implies training approval. See
docs/sample_import/phase12_sample_import_quarantine_plan.md.
"""

from __future__ import annotations

# -- modalities (Step 2) -----------------------------------------------------

MODALITIES = ("text", "image", "audio", "video", "multimodal")

# Modalities that receive only bounded metadata/file-safety validation in
# Phase 12 -- never semantic evaluation. `multimodal` receives manifest and
# cross-reference validation only.
METADATA_ONLY_MODALITIES = ("image", "audio", "video")
MANIFEST_ONLY_MODALITIES = ("multimodal",)

SUPPORTED_TEXT_FORMATS = ("txt", "markdown", "csv", "json", "jsonl", "pdf")

# -- sample-import lifecycle (Step 4) ----------------------------------------

SAMPLE_IMPORT_STATUSES = (
    "draft", "awaiting_approval", "approved", "downloading", "downloaded",
    "quarantined", "scanning", "parsing", "needs_review", "validated",
    "validated_with_conditions", "rejected", "failed", "cancelled", "expired",
    "withdrawn", "deleted",
)
ACTIVE_SAMPLE_IMPORT_STATUSES = (
    "draft", "awaiting_approval", "approved", "downloading", "downloaded",
    "quarantined", "scanning", "parsing", "needs_review",
)
TERMINAL_SAMPLE_IMPORT_STATUSES = (
    "validated", "validated_with_conditions", "rejected", "failed",
    "cancelled", "expired", "withdrawn", "deleted",
)

# A single boolean must never stand in for the lifecycle (Step 4) -- stage
# is tracked as its own enum column alongside, never instead of, status.
SAMPLE_IMPORT_STAGES = (
    "eligibility_check", "approval", "download", "file_validation",
    "archive_extraction", "security_scan", "content_parsing", "pii_scan",
    "quality_scan", "duplicate_scan", "contamination_scan", "human_review",
    "final_report",
)


def is_terminal_sample_import_status(status: str) -> bool:
    return status in TERMINAL_SAMPLE_IMPORT_STATUSES


# -- sample approval (Step 5) -------------------------------------------------

SAMPLE_IMPORT_PURPOSES = (
    "manual_review", "quality_evaluation", "rag_sandbox_preparation",
    "format_validation", "language_validation", "security_validation",
)

# Never permitted as a Phase 12 approval purpose -- these imply
# dataset-level/production/training approval, which this phase never grants.
PROHIBITED_SAMPLE_IMPORT_PURPOSES = ("production_rag", "training", "model_release")

APPROVAL_STATUSES = ("pending", "approved", "rejected", "expired", "superseded")


def validate_sample_import_purpose(purpose: str) -> None:
    """Raises `ValueError` for a prohibited or unrecognized purpose --
    application code must call this before persisting any approval
    request, never trust client-supplied purpose values silently."""

    if purpose in PROHIBITED_SAMPLE_IMPORT_PURPOSES:
        raise ValueError(f"purpose '{purpose}' is never permitted for a Phase 12 sample import")
    if purpose not in SAMPLE_IMPORT_PURPOSES:
        raise ValueError(f"unrecognized sample import purpose: {purpose}")


# -- sample selection (Step 7) ------------------------------------------------

SELECTION_METHODS = (
    "provider_sample_endpoint", "provider_file_metadata", "bounded_row_range",
    "bounded_split_subset", "specific_approved_files", "deterministic_first_n",
    "deterministic_seeded_sample", "manual_file_selection",
)

# -- file validation (Step 10) ------------------------------------------------

FILE_STATUSES = (
    "pending", "safe_for_scan", "unsupported", "suspicious", "blocked",
    "corrupt", "oversized", "validated",
)
BLOCKED_FILE_STATUSES = ("blocked",)

# Classes of file that are always blocked outright, regardless of extension
# claims -- detection is by MIME/magic-byte signature, never extension alone.
BLOCKED_FILE_CLASSES = (
    "executable", "shared_library", "shell_script", "batch_script",
    "powershell_script", "macro_document", "java_archive", "android_package",
    "disk_image", "device_file", "encrypted_archive", "password_protected_archive",
    "unknown_binary_blob", "model_weight_file",
)

# -- archive safety (Step 11) -------------------------------------------------

SUPPORTED_ARCHIVE_FORMATS = ("zip", "tar", "tar.gz")
ARCHIVE_ENTRY_REJECTION_REASONS = (
    "path_traversal", "absolute_path", "symlink", "hard_link", "device_file",
    "encrypted_entry", "duplicate_path", "depth_exceeded", "nested_archive_depth_exceeded",
)

# -- security scan (Step 12) --------------------------------------------------

SCAN_VERDICTS = (
    "clean_by_policy", "suspicious", "blocked", "unsupported",
    "scanner_unavailable", "needs_review",
)
BLOCKING_SCAN_VERDICTS = ("blocked",)

# -- record normalization / language (Steps 14-15) ---------------------------

RECORD_STATUSES = (
    "pending", "normalized", "flagged", "excluded", "accepted", "rejected",
)
SAMPLE_LANGUAGES = ("tamil", "english", "tanglish", "mixed", "other", "unknown")

# -- PII / sensitive data (Step 16) -------------------------------------------

PII_CATEGORIES = (
    "email_address", "phone_number", "postal_address", "government_identifier",
    "financial_account_number", "payment_card", "api_key", "token", "password",
    "private_key", "credential", "health_information", "biometric_reference",
    "precise_location", "minor_data", "personal_name_sensitive_context",
    "private_conversation",
)
PII_FINDING_STATUSES = (
    "not_detected", "possible", "likely", "confirmed", "false_positive",
    "redacted_candidate", "blocked",
)
# A finding at these statuses is ambiguous and structurally requires a human
# review row -- never auto-resolved (Step 16: "Ambiguous ... require human
# review").
AMBIGUOUS_PII_FINDING_STATUSES = ("possible", "likely")

# -- safety / harmful content (Step 17) ---------------------------------------

SAFETY_CATEGORIES = (
    "violent_content", "sexual_content", "self_harm_content", "hate_or_harassment",
    "illegal_activity_instructions", "extremist_content", "malware_instructions",
    "weapons_content", "personal_data_abuse", "fraud_or_scam_content",
    "medical_misinformation_risk", "legal_misinformation_risk",
)
SAFETY_SEVERITIES = ("low", "moderate", "high", "severe")

# -- quality (Step 18) ---------------------------------------------------------

QUALITY_STATES = ("pass", "pass_with_warning", "needs_review", "fail")
QUALITY_ISSUE_TYPES = (
    "empty_content", "too_short", "too_long", "encoding_corruption",
    "ocr_corruption", "language_mismatch", "task_mismatch", "malformed_structure",
    "missing_required_fields", "low_information_content", "template_repetition",
    "spam", "machine_generated_noise", "broken_markup", "invalid_labels",
    "question_answer_mismatch", "translation_mismatch", "unbalanced_conversation_turns",
)

# -- duplicate / conflict (Step 19) -------------------------------------------

DUPLICATE_TYPES = (
    "exact_duplicate", "normalized_duplicate", "near_duplicate", "cross_file_duplicate",
    "duplicate_against_approved_dataset", "duplicate_against_rag_corpus",
    "duplicate_against_evaluation_set",
)
CONFLICT_TYPES = (
    "conflicting_label", "conflicting_answer", "conflicting_translation",
    "conflicting_metadata",
)
DUPLICATE_CONFLICT_RESOLUTION_STATUSES = ("open", "resolved", "acknowledged")

# -- evaluation contamination (Step 20) ---------------------------------------

CONTAMINATION_STATUSES = ("clear", "possible_overlap", "confirmed_overlap", "unknown")
BLOCKING_CONTAMINATION_STATUSES = ("confirmed_overlap",)

# -- poisoning / anomaly (Step 21) --------------------------------------------

POISONING_SIGNAL_TYPES = (
    "instruction_injection", "prompt_injection", "system_prompt_imitation",
    "data_exfiltration_instruction", "repeated_malicious_trigger", "label_flipping",
    "adversarial_unicode", "hidden_control_character", "zero_width_character",
    "homoglyph_abuse", "extreme_repetition", "outlier_record_length",
    "abnormal_language_distribution", "suspicious_source_concentration",
)
POISONING_RESULTS = ("no_known_signal", "warning", "high_risk", "blocked", "needs_review")
BLOCKING_POISONING_RESULTS = ("blocked",)

# -- human review (Step 22) ----------------------------------------------------

REVIEW_TARGET_TYPES = (
    "file", "record", "issue", "duplicate_group", "conflict", "pii", "safety",
    "quality", "contamination", "language", "ocr_correction",
)
REVIEW_DECISIONS = (
    "accept", "accept_with_conditions", "edit_derived_copy", "redact_derived_copy",
    "exclude", "reject_file", "reject_sample", "needs_more_evidence",
)
# Decisions that create a new versioned derived-content row rather than a
# plain acknowledgement -- the *original* is never touched by any of these.
DERIVED_REVISION_REVIEW_DECISIONS = ("edit_derived_copy", "redact_derived_copy")

# -- RAG sandbox eligibility / training-assessment signal (Steps 24-25) ------

TRAINING_ASSESSMENT_STATUSES = (
    "not_assessed", "potentially_suitable", "needs_more_review", "not_suitable", "blocked",
)
# Deliberately absent from every enum in this module: any status meaning
# "training approved". No Phase 12 code path can write a value that does
# not exist here.

# -- deletion (Step 26) ---------------------------------------------------------

DELETION_REQUEST_STATUSES = ("requested", "confirmed", "executed", "cancelled")

# -- bounded execution constants (Step 36) -------------------------------------

DOWNLOAD_CHUNK_BYTES = 65_536
DOWNLOAD_TIMEOUT_SECONDS = 30.0
MAX_DOWNLOAD_REDIRECTS = 2
MAX_DOWNLOAD_RETRIES = 1

DEFAULT_MAX_SAMPLE_BYTES = 50_000_000
DEFAULT_MAX_SAMPLE_RECORDS = 5_000

MAX_ARCHIVE_MEMBER_COUNT = 2_000
MAX_ARCHIVE_EXPANDED_BYTES = 200_000_000
ARCHIVE_COMPRESSION_RATIO_THRESHOLD = 100.0
MAX_ARCHIVE_DIRECTORY_DEPTH = 12
MAX_NESTED_ARCHIVE_DEPTH = 1
ARCHIVE_EXTRACTION_TIMEOUT_SECONDS = 60.0

MAX_PDF_PAGES = 50
MAX_OCR_PAGES = 10
MAX_TEXT_RECORD_CHARS = 50_000
MAX_JSON_NESTING_DEPTH = 20
MAX_CSV_ROWS = 20_000
MAX_JSONL_LINES = 20_000

RECORD_BATCH_SIZE = 200
