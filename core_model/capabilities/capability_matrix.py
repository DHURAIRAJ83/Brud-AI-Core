"""Phase 16: Centralized, deterministic Capability Matrix for Brud AI.

Every capability definition is backed by repository evidence and actual
implementation entrypoints. Frozen dataclasses guarantee immutability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

VALID_AVAILABILITY = {"available", "partial", "unavailable", "deprecated", "blocked"}
VALID_ACCESS_LEVELS = {"public", "authenticated", "admin", "super_admin", "internal", "unavailable"}
VALID_RISK_LEVELS = {"low", "medium", "high", "critical"}


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    name: str
    description: str
    category: str
    source_component: str
    implementation_type: str  # "function" | "service_class" | "registry" | "policy"
    availability: str  # "available" | "partial" | "unavailable" | "deprecated" | "blocked"
    access_level: str  # "public" | "authenticated" | "admin" | "super_admin" | "internal" | "unavailable"
    risk_level: str  # "low" | "medium" | "high" | "critical"
    requires_human_approval: bool
    supports_public_chat: bool
    supports_admin_assistant: bool
    supports_local_execution: bool
    supports_cloud_execution: bool
    input_types: tuple[str, ...]
    output_types: tuple[str, ...]
    dependencies: tuple[str, ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.availability not in VALID_AVAILABILITY:
            raise ValueError(f"Invalid availability {self.availability!r}")
        if self.access_level not in VALID_ACCESS_LEVELS:
            raise ValueError(f"Invalid access_level {self.access_level!r}")
        if self.risk_level not in VALID_RISK_LEVELS:
            raise ValueError(f"Invalid risk_level {self.risk_level!r}")


# System capability inventory verified by direct repository evidence
_CAPABILITY_LIST: tuple[CapabilityDefinition, ...] = (
    CapabilityDefinition(
        capability_id="language_detection",
        name="Deterministic Language Detection",
        description="Detects Tamil script, English, Tanglish, and Mixed language input using Unicode ranges and signal words.",
        category="language_detection",
        source_component="core_model.nlp.text_processor.process_text",
        implementation_type="function",
        availability="available",
        access_level="public",
        risk_level="low",
        requires_human_approval=False,
        supports_public_chat=True,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("text/plain",),
        output_types=("application/json",),
        dependencies=("core_model.mini_brain.prompting.language_detector",),
        limitations=("Rule-based classification; coverage bounded by signal dictionary",),
    ),
    CapabilityDefinition(
        capability_id="tanglish_normalization",
        name="Tanglish to Tamil Word Normalization",
        description="Maps Latin-script Tanglish vocabulary to native Tamil script using deterministic dictionary lookup.",
        category="tanglish_normalization",
        source_component="core_model.mini_brain.prompting.tanglish_normalizer.normalize_tanglish",
        implementation_type="function",
        availability="available",
        access_level="public",
        risk_level="low",
        requires_human_approval=False,
        supports_public_chat=True,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("text/plain",),
        output_types=("text/plain",),
        dependencies=(),
        limitations=("Dictionary-based substitution; unmatched English words left intact",),
    ),
    CapabilityDefinition(
        capability_id="text_normalization",
        name="Unicode NFC & Source Text Normalization",
        description="Applies Unicode NFC normalization, control character removal, and whitespace collapsing.",
        category="text_normalization",
        source_component="core_model.rag.text_normalization.normalize_source_text",
        implementation_type="function",
        availability="available",
        access_level="internal",
        risk_level="low",
        requires_human_approval=False,
        supports_public_chat=True,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("text/plain",),
        output_types=("application/json",),
        dependencies=(),
        limitations=("Does not alter semantic meaning or lower-case non-Latin script",),
    ),
    CapabilityDefinition(
        capability_id="unicode_validation",
        name="Tamil & General Unicode Validation",
        description="Validates Unicode code points, orphan marks, and character cleanliness.",
        category="unicode_validation",
        source_component="core_model.mini_brain.language_intelligence.unicode_validator.analyze_unicode",
        implementation_type="function",
        availability="available",
        access_level="public",
        risk_level="low",
        requires_human_approval=False,
        supports_public_chat=True,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("text/plain",),
        output_types=("application/json",),
        dependencies=(),
        limitations=("Structural validation only; does not perform semantic analysis",),
    ),
    CapabilityDefinition(
        capability_id="rag_retrieval",
        name="Hybrid RAG Vector & Keyword Retrieval",
        description="Performs tenant-gated hybrid vector and keyword search across knowledge bases.",
        category="rag",
        source_component="core_model.rag.hybrid_retrieval.hybrid_retrieve",
        implementation_type="function",
        availability="available",
        access_level="public",
        risk_level="low",
        requires_human_approval=False,
        supports_public_chat=True,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=True,
        input_types=("text/plain",),
        output_types=("application/json",),
        dependencies=("core_model.rag.embedding", "core_model.rag.keyword_index"),
        limitations=("Bounded by vector index state and tenant access boundaries",),
    ),
    CapabilityDefinition(
        capability_id="conversation_memory",
        name="Public Chat Conversation Memory Window",
        description="Maintains sliding window conversation context across user interactions.",
        category="memory",
        source_component="core_model.mini_brain.public_chat_runtime.conversation_window.get_recent_messages",
        implementation_type="function",
        availability="available",
        access_level="public",
        risk_level="low",
        requires_human_approval=False,
        supports_public_chat=True,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("text/plain",),
        output_types=("application/json",),
        dependencies=(),
        limitations=("In-memory sliding window; bounded context length",),
    ),
    CapabilityDefinition(
        capability_id="safety_filtering",
        name="Public Chat Input Safety Gate",
        description="Classifies input safety signals and enforces policy rules before processing.",
        category="monitoring",
        source_component="core_model.public_chat.input_safety.evaluate_input_safety",
        implementation_type="function",
        availability="available",
        access_level="public",
        risk_level="low",
        requires_human_approval=False,
        supports_public_chat=True,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("text/plain",),
        output_types=("application/json",),
        dependencies=("core_model.knowledge_routing.safety_signal",),
        limitations=("Pattern-based classification; does not block safe sensitive queries",),
    ),
    CapabilityDefinition(
        capability_id="provider_routing",
        name="Public Answer Language & Provider Policy",
        description="Determines answer language (Tamil/English) based on input category and explicit user overrides.",
        category="provider_routing",
        source_component="core_model.public_chat.language_policy.resolve_answer_language",
        implementation_type="function",
        availability="available",
        access_level="public",
        risk_level="low",
        requires_human_approval=False,
        supports_public_chat=True,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("text/plain",),
        output_types=("application/json",),
        dependencies=(),
        limitations=("Public output restricted to 'ta' or 'en' only; Tanglish output forbidden",),
    ),
    CapabilityDefinition(
        capability_id="admin_assistant_governance",
        name="Phase 4 Propose / Review / Execute Write Governance",
        description="Enforces dual-key approval, risk levels, preview stamping, stale checks, and audit logging for administrative write actions.",
        category="governance",
        source_component="backend.services.admin_assistant_write_governance.propose_with_governance",
        implementation_type="service_class",
        availability="available",
        access_level="admin",
        risk_level="high",
        requires_human_approval=True,
        supports_public_chat=False,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("application/json",),
        output_types=("application/json",),
        dependencies=("backend.services.admin_assistant_tool_governance",),
        limitations=("Proposer cannot approve high-risk proposals; approval required before execution",),
    ),
    CapabilityDefinition(
        capability_id="automation_evaluation",
        name="Phase 13 Automation Evaluation & Dry-Run Simulation",
        description="Provides read-only diagnostic evaluation, simulation status, and operator observations for defined automations without execution.",
        category="automation",
        source_component="core_model.admin_assistant.automation_policy.evaluate_automation",
        implementation_type="function",
        availability="available",
        access_level="admin",
        risk_level="medium",
        requires_human_approval=True,
        supports_public_chat=False,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("application/json",),
        output_types=("application/json",),
        dependencies=("core_model.admin_assistant.action_registry",),
        limitations=("Read-only diagnostic simulation only; never dispatches real actions",),
    ),
    CapabilityDefinition(
        capability_id="manual_automation_execution",
        name="Phase 14 Human-Triggered Manual Execution Control",
        description="Evaluates human-triggered single-run manual execution readiness. Fails closed when allowlist is empty.",
        category="automation",
        source_component="core_model.admin_assistant.automation_policy.evaluate_manual_automation_execution",
        implementation_type="function",
        availability="blocked",
        access_level="super_admin",
        risk_level="critical",
        requires_human_approval=True,
        supports_public_chat=False,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("application/json",),
        output_types=("application/json",),
        dependencies=("core_model.admin_assistant.automation_policy",),
        limitations=("Blocked by default-deny posture: AUTOMATION_ALLOWED_ACTIONS = frozenset()",),
    ),
    CapabilityDefinition(
        capability_id="tool_execution",
        name="Governed ActionDefinition Tool Execution",
        description="Executes audited governed administrative tool actions via strict Phase 3 RBAC and Phase 4 write governance.",
        category="tool_execution",
        source_component="core_model.admin_assistant.action_registry.ACTION_DEFINITIONS",
        implementation_type="registry",
        availability="available",
        access_level="admin",
        risk_level="high",
        requires_human_approval=True,
        supports_public_chat=False,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("application/json",),
        output_types=("application/json",),
        dependencies=("backend.services.admin_assistant_tools",),
        limitations=("104 registered ActionDefinitions; requires tool.execute permission and proposal approval",),
    ),
    CapabilityDefinition(
        capability_id="data_studio_chunking",
        name="Semantic Chunk & Structured Record Studio",
        description="Builds semantic chunks and structured record candidate studio workflows.",
        category="data_studio",
        source_component="backend.services.semantic_chunk_service.SemanticChunkService",
        implementation_type="service_class",
        availability="available",
        access_level="admin",
        risk_level="medium",
        requires_human_approval=False,
        supports_public_chat=False,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("application/json",),
        output_types=("application/json",),
        dependencies=(),
        limitations=("Requires admin permissions for dataset studio operations",),
    ),
    CapabilityDefinition(
        capability_id="vision_rag",
        name="Multimodal Vision RAG & OCR Evidence Fusion",
        description="Performs OCR text extraction, image retrieval, and visual evidence fusion.",
        category="image",
        source_component="backend.services.mini_brain_vision_rag_service.MiniBrainVisionRAGService",
        implementation_type="service_class",
        availability="available",
        access_level="authenticated",
        risk_level="medium",
        requires_human_approval=False,
        supports_public_chat=True,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("image/png", "image/jpeg", "text/plain"),
        output_types=("application/json",),
        dependencies=("core_model.mini_brain.vision_rag",),
        limitations=("Requires valid image input or OCR text payload",),
    ),
    CapabilityDefinition(
        capability_id="voice_runtime",
        name="Mini-Brain Voice Runtime Permission & Stream Service",
        description="Handles voice streaming permission checks and audio processing.",
        category="voice",
        source_component="backend.services.mini_brain_voice_runtime_service.MiniBrainVoiceRuntimeService",
        implementation_type="service_class",
        availability="partial",
        access_level="authenticated",
        risk_level="medium",
        requires_human_approval=False,
        supports_public_chat=False,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("audio/wav", "audio/mp3"),
        output_types=("application/json",),
        dependencies=(),
        limitations=("Partial capability; voice streaming permissions required",),
    ),
    CapabilityDefinition(
        capability_id="incremental_training",
        name="Incremental Language Training Pipeline",
        description="Manages dataset candidate promotion, checkpoint staging, and training pipeline governance.",
        category="training",
        source_component="backend.services.mini_brain_training_pipeline_service.MiniBrainTrainingPipelineService",
        implementation_type="service_class",
        availability="available",
        access_level="super_admin",
        risk_level="critical",
        requires_human_approval=True,
        supports_public_chat=False,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=False,
        input_types=("application/json",),
        output_types=("application/json",),
        dependencies=(),
        limitations=("Critical system operation; super_admin role and multi-stage human approval required",),
    ),
    CapabilityDefinition(
        capability_id="external_ai_provider_gateway",
        name="External AI Provider Registry & Request Policy Gateway",
        description="Manages provider configurations, prompt sanitization, and external model request policies.",
        category="provider_routing",
        source_component="core_model.mini_brain.external_ai_gateway.provider_registry",
        implementation_type="policy",
        availability="available",
        access_level="admin",
        risk_level="high",
        requires_human_approval=False,
        supports_public_chat=False,
        supports_admin_assistant=True,
        supports_local_execution=True,
        supports_cloud_execution=True,
        input_types=("application/json",),
        output_types=("application/json",),
        dependencies=(),
        limitations=("Strict request policy enforcement; external API keys required",),
    ),
    CapabilityDefinition(
        capability_id="autonomous_execution",
        name="Unattended Background Worker & Scheduler",
        description="Autonomous background task scheduling and loop execution engine.",
        category="automation",
        source_component="unbuilt_platform_boundary",
        implementation_type="policy",
        availability="unavailable",
        access_level="unavailable",
        risk_level="critical",
        requires_human_approval=True,
        supports_public_chat=False,
        supports_admin_assistant=False,
        supports_local_execution=False,
        supports_cloud_execution=False,
        input_types=(),
        output_types=(),
        dependencies=(),
        limitations=("Autonomous execution is explicitly unbuilt and forbidden by platform safety policy.",),
    ),
)

SYSTEM_CAPABILITIES: Mapping[str, CapabilityDefinition] = {
    cap.capability_id: cap for cap in _CAPABILITY_LIST
}


def get_capability(capability_id: str) -> CapabilityDefinition | None:
    """Returns the immutable CapabilityDefinition for `capability_id`, or None."""
    return SYSTEM_CAPABILITIES.get(capability_id)


def list_capabilities() -> tuple[CapabilityDefinition, ...]:
    """Returns all system capabilities as an immutable tuple."""
    return _CAPABILITY_LIST


def get_capabilities_by_category(category: str) -> tuple[CapabilityDefinition, ...]:
    """Returns capabilities belonging to `category`."""
    return tuple(cap for cap in _CAPABILITY_LIST if cap.category == category)


def get_capabilities_by_access(access_level: str) -> tuple[CapabilityDefinition, ...]:
    """Returns capabilities matching `access_level`."""
    return tuple(cap for cap in _CAPABILITY_LIST if cap.access_level == access_level)
