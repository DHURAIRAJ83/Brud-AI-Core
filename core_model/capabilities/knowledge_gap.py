"""Phase 19: Knowledge Gap Model & Taxonomy Schema.

Provides an immutable frozen dataclass schema and deterministic taxonomy definitions
for capturing structured Knowledge Gap observations across the Public Chat request
pipeline.

Design principles & safety invariants:
  ✅ Immutable (frozen dataclass).
  ✅ Deterministic taxonomy codes and severity mappings.
  ✅ Pure observation model — NO automatic training dataset generation, NO RAG
     data mutation, NO model weight modification, NO background worker creation.
  ✅ PII-safe & secret-sanitized safe_summary generation.
  ❌ No database writes or schema migrations.
  ❌ No external API or HTTP network calls.
  ❌ No subprocess, eval, or exec.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence
from uuid import uuid4

# ---------------------------------------------------------------------------
# Deterministic Gap Taxonomy Identifiers
# ---------------------------------------------------------------------------
GAP_TAXONOMY_ANSWERABLE = "ANSWERABLE"
GAP_TAXONOMY_UNKNOWN_INTENT = "UNKNOWN_INTENT"
GAP_TAXONOMY_LOW_ROUTING_CONFIDENCE = "LOW_ROUTING_CONFIDENCE"
GAP_TAXONOMY_AMBIGUOUS_INTENT = "AMBIGUOUS_INTENT"
GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND = "KNOWLEDGE_NOT_FOUND"
GAP_TAXONOMY_RAG_INSUFFICIENT_EVIDENCE = "RAG_INSUFFICIENT_EVIDENCE"
GAP_TAXONOMY_RAG_SCOPE_UNAVAILABLE = "RAG_SCOPE_UNAVAILABLE"
GAP_TAXONOMY_MEMORY_UNAVAILABLE = "MEMORY_UNAVAILABLE"
GAP_TAXONOMY_PROVIDER_UNAVAILABLE = "PROVIDER_UNAVAILABLE"
GAP_TAXONOMY_UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
GAP_TAXONOMY_CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
GAP_TAXONOMY_TECHNICAL_CONTEXT_UNRESOLVED = "TECHNICAL_CONTEXT_UNRESOLVED"
GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY = "SECURITY_ADMIN_BOUNDARY"

VALID_GAP_TYPES: tuple[str, ...] = (
    GAP_TAXONOMY_ANSWERABLE,
    GAP_TAXONOMY_UNKNOWN_INTENT,
    GAP_TAXONOMY_LOW_ROUTING_CONFIDENCE,
    GAP_TAXONOMY_AMBIGUOUS_INTENT,
    GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND,
    GAP_TAXONOMY_RAG_INSUFFICIENT_EVIDENCE,
    GAP_TAXONOMY_RAG_SCOPE_UNAVAILABLE,
    GAP_TAXONOMY_MEMORY_UNAVAILABLE,
    GAP_TAXONOMY_PROVIDER_UNAVAILABLE,
    GAP_TAXONOMY_UNSUPPORTED_CAPABILITY,
    GAP_TAXONOMY_CLARIFICATION_REQUIRED,
    GAP_TAXONOMY_TECHNICAL_CONTEXT_UNRESOLVED,
    GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY,
)

# ---------------------------------------------------------------------------
# Deterministic Severity Identifiers
# ---------------------------------------------------------------------------
SEVERITY_LOW = "low"
SEVERITY_MEDIUM = "medium"
SEVERITY_HIGH = "high"
SEVERITY_CRITICAL = "critical"

VALID_SEVERITIES: tuple[str, ...] = (
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_HIGH,
    SEVERITY_CRITICAL,
)

# Regex patterns for stripping sensitive credentials and tokens from summaries
_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)(api[_-]?key|secret|bearer|password|token|auth)\s*[:=]\s*\S+"),
    re.compile(r"bearer\s+[a-zA-Z0-9._\~+/-]+=*", re.IGNORECASE),
)


@dataclass(frozen=True)
class KnowledgeGap:
    """Immutable Knowledge Gap observation record.

    Attributes:
        gap_id: Unique gap observation identifier (e.g. "gap-uuid").
        request_id: Correlation ID linking to the Public Chat request trace.
        detected_language: Language code ("ta", "en", "tanglish", "mixed", "unknown").
        language_confidence: Detection confidence (0.0 to 1.0).
        normalized_intent: Safe normalized representation of the user query.
        requested_capability_id: Requested capability string or None.
        selected_capability_id: Router selected capability string or None.
        routing_confidence: Smart Router confidence score (0.0 to 1.0).
        failure_classification: Fallback/error code or "none".
        gap_type: One of VALID_GAP_TYPES string codes.
        severity: One of VALID_SEVERITIES ("low", "medium", "high", "critical").
        clarification_required: Boolean flag.
        clarification_question: Concise bilingual clarification text or None.
        evidence_status: Evidence status code ("none", "insufficient", etc.).
        source_stage: Stage where gap originated.
        safe_summary: PII-free, secret-sanitized semantic summary.
        metadata: Plain JSON-serializable dictionary.
    """

    gap_id: str
    request_id: str
    detected_language: str
    language_confidence: float
    normalized_intent: str
    requested_capability_id: str | None
    selected_capability_id: str | None
    routing_confidence: float
    failure_classification: str
    gap_type: str
    severity: str
    clarification_required: bool
    clarification_question: str | None
    evidence_status: str
    source_stage: str
    safe_summary: str
    metadata: dict[str, Any]

    def __post_init__(self) -> None:
        if self.gap_type not in VALID_GAP_TYPES:
            raise ValueError(f"Invalid gap_type {self.gap_type!r}")
        if self.severity not in VALID_SEVERITIES:
            raise ValueError(f"Invalid severity {self.severity!r}")


def generate_gap_id() -> str:
    """Generate a unique gap observation identifier."""
    return f"gap-{uuid4()}"


def sanitize_summary(text: str | None) -> str:
    """Produce a PII-free, secret-sanitized safe summary of input text."""
    if not text or not text.strip():
        return ""

    sanitized = text.strip()
    for pattern in _SECRET_PATTERNS:
        sanitized = pattern.sub("[REDACTED_SECRET]", sanitized)

    # Truncate summary to max 256 characters for observation bounds
    if len(sanitized) > 256:
        sanitized = sanitized[:253] + "..."

    return sanitized


def build_knowledge_gap_dict(gap: KnowledgeGap) -> dict[str, Any]:
    """Convert a KnowledgeGap dataclass into a plain, JSON-serializable dictionary."""
    return {
        "phase": "19",
        "record_type": "knowledge_gap",
        "gap_id": gap.gap_id,
        "request_id": gap.request_id,
        "detected_language": gap.detected_language,
        "language_confidence": round(float(gap.language_confidence), 2),
        "normalized_intent": gap.normalized_intent,
        "requested_capability_id": gap.requested_capability_id,
        "selected_capability_id": gap.selected_capability_id,
        "routing_confidence": round(float(gap.routing_confidence), 2),
        "failure_classification": gap.failure_classification,
        "gap_type": gap.gap_type,
        "severity": gap.severity,
        "clarification_required": gap.clarification_required,
        "clarification_question": gap.clarification_question,
        "evidence_status": gap.evidence_status,
        "source_stage": gap.source_stage,
        "safe_summary": gap.safe_summary,
        "metadata": dict(gap.metadata),
    }


__all__ = [
    "GAP_TAXONOMY_AMBIGUOUS_INTENT",
    "GAP_TAXONOMY_CLARIFICATION_REQUIRED",
    "GAP_TAXONOMY_KNOWLEDGE_NOT_FOUND",
    "GAP_TAXONOMY_LOW_ROUTING_CONFIDENCE",
    "GAP_TAXONOMY_MEMORY_UNAVAILABLE",
    "GAP_TAXONOMY_PROVIDER_UNAVAILABLE",
    "GAP_TAXONOMY_RAG_INSUFFICIENT_EVIDENCE",
    "GAP_TAXONOMY_RAG_SCOPE_UNAVAILABLE",
    "GAP_TAXONOMY_SECURITY_ADMIN_BOUNDARY",
    "GAP_TAXONOMY_TECHNICAL_CONTEXT_UNRESOLVED",
    "GAP_TAXONOMY_UNKNOWN_INTENT",
    "GAP_TAXONOMY_UNSUPPORTED_CAPABILITY",
    "SEVERITY_CRITICAL",
    "SEVERITY_HIGH",
    "SEVERITY_LOW",
    "SEVERITY_MEDIUM",
    "VALID_GAP_TYPES",
    "VALID_SEVERITIES",
    "KnowledgeGap",
    "build_knowledge_gap_dict",
    "generate_gap_id",
    "sanitize_summary",
]
