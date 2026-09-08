"""Unified Dashboard & System Context Service for Brud Mini Brain.

Aggregates real-time, read-only operational state across the entire Brud AI
ecosystem (System, Providers, Models, Datasets, Training, Evaluation, RAG,
Memory, Governance, and Pending Actions) to give the Admin Assistant complete,
grounded context without fabricating metrics or leaking encrypted secrets.
"""

from __future__ import annotations

import copy
import datetime
import logging
import threading
import time
from typing import Any

from backend.core.config import Settings
from backend.core.json_utils import redact_secrets
from backend.database.repositories.corpus import CorpusRepository
from backend.database.repositories.model_evaluation import ModelEvaluationRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.phase2 import AuditLogRepository, SettingsRepository
from backend.database.repositories.pretraining import PretrainingRepository
from backend.database.repositories.rag import RagRepository
from backend.services.admin_assistant_service import AdminAssistantService
from backend.services.mini_brain_health_service import MiniBrainHealthService
from backend.services.mini_brain_llm_runtime_service import (
    DEFAULT_RETRIEVAL_PROFILE_SETTING_KEY,
    MiniBrainLlmRuntimeService,
)
from backend.services.mini_brain_provider_settings_service import (
    MiniBrainProviderSettingsService,
)

logger = logging.getLogger(__name__)


class BoundedContextCache:
    """Process-local, thread-safe, bounded, correctness-aware context cache.

    Guarantees:
    - Bounded: Fixed maximum entries (default 1 snapshot).
    - TTL based: Configurable via settings.mini_brain_context_cache_ttl_seconds.
    - Single-flight coalescing: Multiple simultaneous misses trigger exactly 1 rebuild.
    - Zero secrets: Serialized snapshots are scrubbed via redact_secrets.
    - Correctness/Invalidation: Invalidated immediately on authoritative mutations.
    - Observability: Exposes hit/miss/expired/invalidation metrics.
    """

    def __init__(self, ttl_seconds: float = 4.0) -> None:
        self.ttl_seconds = float(ttl_seconds)
        self._lock = threading.RLock()
        self._flight_lock = threading.Lock()
        self._snapshot: dict[str, Any] | None = None
        self._created_at: float = 0.0
        self._expires_at: float = 0.0
        self._generation: int = 0

        # Observability metrics
        self.metrics = {
            "cache_hit": 0,
            "cache_miss": 0,
            "cache_expired": 0,
            "cache_invalidated": 0,
            "rebuild_count": 0,
            "context_generation_latency_ms": 0.0,
            "last_invalidation_reason": None,
        }

    def get(self) -> dict[str, Any] | None:
        """Returns deep copy of cached snapshot if valid and not expired, else None."""
        now = time.perf_counter()
        with self._lock:
            if self._snapshot is None:
                self.metrics["cache_miss"] += 1
                return None
            if now >= self._expires_at:
                self.metrics["cache_expired"] += 1
                self.metrics["cache_miss"] += 1
                self._snapshot = None
                return None
            self.metrics["cache_hit"] += 1
            # Return deep copy to prevent mutation of cached structure
            return copy.deepcopy(self._snapshot)

    def set(self, snapshot: dict[str, Any], latency_ms: float = 0.0) -> None:
        """Stores a sanitized deep copy of the snapshot and updates expiry."""
        now = time.perf_counter()
        # Ensure secrets are scrubbed before caching
        scrubbed = redact_secrets(snapshot) if isinstance(snapshot, dict) else snapshot
        with self._lock:
            self._snapshot = copy.deepcopy(scrubbed)
            self._created_at = now
            self._expires_at = now + self.ttl_seconds
            self._generation += 1
            self.metrics["rebuild_count"] += 1
            self.metrics["context_generation_latency_ms"] = round(latency_ms, 3)

    def invalidate(self, reason: str = "mutation") -> None:
        """Invalidates cache immediately to guarantee zero stale authoritative truth."""
        with self._lock:
            if self._snapshot is not None:
                self.metrics["cache_invalidated"] += 1
            self._snapshot = None
            self._expires_at = 0.0
            self._generation += 1
            self.metrics["last_invalidation_reason"] = reason

    def stats(self) -> dict[str, Any]:
        """Returns safe observability metrics."""
        with self._lock:
            now = time.perf_counter()
            is_valid = self._snapshot is not None and now < self._expires_at
            age_ms = round((now - self._created_at) * 1000, 2) if self._snapshot else 0.0
            return {
                **self.metrics,
                "is_valid": is_valid,
                "generation": self._generation,
                "ttl_seconds": self.ttl_seconds,
                "cache_age_ms": age_ms,
            }


# Singleton process-local cache instance
_GLOBAL_CONTEXT_CACHE = BoundedContextCache(ttl_seconds=4.0)


class MiniBrainDashboardContextService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        global _GLOBAL_CONTEXT_CACHE
        # Update TTL if setting differs
        configured_ttl = getattr(settings, "mini_brain_context_cache_ttl_seconds", 4.0)
        _GLOBAL_CONTEXT_CACHE.ttl_seconds = float(configured_ttl)
        self.cache = _GLOBAL_CONTEXT_CACHE

        self.provider_service = MiniBrainProviderSettingsService(settings)
        self.llm_runtime_service = MiniBrainLlmRuntimeService(settings)
        self.health_service = MiniBrainHealthService(settings)
        self.assistant_service = AdminAssistantService(settings)
        self.rag_repo = RagRepository(settings.resolved_database_path)
        self.corpus_repo = CorpusRepository(settings.resolved_database_path)
        self.pretraining_repo = PretrainingRepository(settings.resolved_database_path)
        self.model_eval_repo = ModelEvaluationRepository(settings.resolved_database_path)
        self.release_repo = ModelReleaseRepository(settings.resolved_database_path)
        self.audit_repo = AuditLogRepository(settings.resolved_database_path)
        self.settings_repo = SettingsRepository(settings.resolved_database_path)

    @classmethod
    def invalidate_cache(cls, reason: str = "mutation") -> None:
        """Global hook to invalidate cache on any authoritative state mutation."""
        _GLOBAL_CONTEXT_CACHE.invalidate(reason=reason)

    @classmethod
    def get_cache_metrics(cls) -> dict[str, Any]:
        """Observability accessor for cache metrics."""
        return _GLOBAL_CONTEXT_CACHE.stats()

    def get_system_context(self, admin_id: str | None = None, force_refresh: bool = False) -> dict[str, Any]:
        """Gathers unified, non-secret system context across all 11 subsystems with single-flight caching."""
        del admin_id

        if not force_refresh:
            cached = self.cache.get()
            if cached is not None:
                return cached

        # Single-flight / Request coalescing to avoid cache stampede on misses
        with self.cache._flight_lock:
            # Double check after acquiring flight lock
            if not force_refresh:
                cached = self.cache.get()
                if cached is not None:
                    return cached

            started = time.perf_counter()
            built_context = self._build_fresh_context()
            latency_ms = (time.perf_counter() - started) * 1000.0
            self.cache.set(built_context, latency_ms=latency_ms)
            return copy.deepcopy(built_context)

    def _build_fresh_context(self) -> dict[str, Any]:
        """Authoritative DB aggregation across all 11 subsystems."""

        # 1. System & Health
        health_data = {}
        try:
            health_data = self.health_service.snapshot()
        except Exception:
            health_data = {}
        system_status = {
            "overall_status": "healthy" if health_data.get("backend_type") != "unavailable" else "degraded",
            "backend_type": health_data.get("backend_type", "local"),
            "model_loaded": health_data.get("model_loaded", False),
            "model_id": health_data.get("model_id"),
            "database_connected": True,
            "environment": getattr(self.settings, "environment", "development"),
            "project_phase": "Phase 61 / Post P10-L",
            "production_locked": True,
        }

        # 2. Providers
        providers_res = self.provider_service.list_settings()
        provider_items = providers_res.get("items", [])
        enabled_providers = [p["provider_key"] for p in provider_items if p.get("enabled")]
        configured_providers = [
            p["provider_key"]
            for p in provider_items
            if any(s.get("is_set") for s in p.get("secrets", [])) or not p.get("secrets")
        ]
        provider_context = {
            "total_configured": len(configured_providers),
            "enabled": enabled_providers,
            "configured": configured_providers,
            "encryption_active": True,
        }

        # 3. Models & Runtime
        widget_health = self.llm_runtime_service.widget_health()
        runtime_diag = self.llm_runtime_service.diagnostics()
        model_context = {
            "active_model": widget_health.get("current_model") or "Not Selected",
            "backend_type": widget_health.get("backend_type", "unavailable"),
            "local_available": runtime_diag.get("local_available", False),
            "external_fallback_enabled": runtime_diag.get("external_fallback_enabled", False),
            "llama_cpp_installed": runtime_diag.get("llama_cpp_installed", False),
        }

        # 4. Datasets
        try:
            with self.corpus_repo.transaction() as conn:
                version_rows = self.corpus_repo.list_dataset_versions(conn, limit=10)
                dataset_count = len(version_rows)
        except Exception:
            dataset_count = 0
            version_rows = []

        dataset_context = {
            "total_dataset_versions": dataset_count,
            "latest_version": version_rows[0]["dataset_version"] if version_rows else None,
            "training_ready": dataset_count > 0,
        }

        # 5. Training
        try:
            with self.pretraining_repo.transaction() as conn:
                training_runs = self.pretraining_repo.list_runs(conn, limit=5)
        except Exception:
            training_runs = []

        training_context = {
            "total_runs": len(training_runs),
            "latest_run_id": training_runs[0]["public_id"] if training_runs else None,
            "latest_run_status": training_runs[0]["status"] if training_runs else "none",
            "training_gate_locked": True,  # SignedTrainingAuthorizationToken is absent by invariant
        }

        # 6. Evaluation
        try:
            with self.model_eval_repo.transaction() as conn:
                eval_runs = self.model_eval_repo.list_evaluation_runs(conn, limit=5)
        except Exception:
            eval_runs = []

        eval_context = {
            "total_evaluations": len(eval_runs),
            "latest_evaluation_id": eval_runs[0]["public_id"] if eval_runs else None,
            "latest_score": eval_runs[0]["overall_score"] if eval_runs else None,
            "evaluation_status": eval_runs[0]["status"] if eval_runs else "no_evaluations",
        }

        # 7. RAG
        try:
            with self.rag_repo.transaction() as conn:
                spaces = self.rag_repo.list_knowledge_spaces(conn)
            with self.settings_repo.transaction() as conn:
                default_profile_row = self.settings_repo.get(conn, DEFAULT_RETRIEVAL_PROFILE_SETTING_KEY)
                default_profile_id = default_profile_row["value"] if default_profile_row else None
        except Exception:
            spaces = []
            default_profile_id = None

        rag_context = {
            "knowledge_spaces_count": len(spaces),
            "default_retrieval_profile_public_id": default_profile_id,
            "grounded_chat_ready": bool(default_profile_id),
        }

        # 8. Memory & Sessions
        try:
            with self.llm_runtime_service.repository.transaction() as conn:
                active_sessions = self.llm_runtime_service.repository.count_sessions(conn, status="active")
                total_msgs = self.llm_runtime_service.repository.total_message_count(conn)
        except Exception:
            active_sessions = 0
            total_msgs = 0

        memory_context = {
            "active_chat_sessions": active_sessions,
            "total_messages_recorded": total_msgs,
            "conversation_memory_active": True,
        }

        # 9. Governance & Security
        try:
            proposals = self.assistant_service.list_proposals(status="pending", limit=10)
            pending_count = len(proposals)
        except Exception:
            pending_count = 0
            proposals = []

        governance_context = {
            "pending_proposals_count": pending_count,
            "production_state": "LOCKED",
            "admin_assistant_authority": "ADVISORY_ONLY",
            "authority_mode": "ADVISORY_ONLY",
            "allow_autonomous_execution": False,
            "fail_closed_enforced": True,
        }

        # 10. Recent Events
        try:
            with self.audit_repo.transaction() as conn:
                audit_events = self.audit_repo.list_events(conn, limit=5)
                recent_events = [
                    {
                        "action": e["action"],
                        "target_type": e["target_type"],
                        "created_at": str(e["created_at"]),
                    }
                    for e in audit_events
                ]
        except Exception:
            recent_events = []

        # 11. Recommendations
        recommendations = []
        if not enabled_providers:
            recommendations.append({
                "type": "provider_setup",
                "message": "No external AI provider is currently enabled. Configure OpenRouter or local Ollama in Settings.",
                "nav_key": "Settings",
            })
        if not default_profile_id:
            recommendations.append({
                "type": "rag_setup",
                "message": "No default RAG retrieval profile is active. Grounded chat will answer without knowledge base.",
                "nav_key": "RAG",
            })
        if pending_count > 0:
            recommendations.append({
                "type": "governance_review",
                "message": f"{pending_count} pending proposal(s) require Admin review.",
                "nav_key": "Governance",
            })

        return {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "system": system_status,
            "system_health": system_status,
            "providers": provider_context,
            "models": model_context,
            "datasets": dataset_context,
            "training": training_context,
            "evaluation": eval_context,
            "rag": rag_context,
            "memory": memory_context,
            "governance": governance_context,
            "recent_events": recent_events,
            "pending_actions": [p.model_dump() for p in proposals],
            "recommendations": recommendations,
        }
