"""Phase 23 — Version Comparison & Regression Detection Backend Service.

Compares Version N vs Version N+1 for RAG and Dataset artifacts to detect quality score deltas,
additions, deletions, modifications, and security regressions (`BETTER`, `SAME`, `REGRESSED`, `INCONCLUSIVE`).

CRITICAL INVARIANTS:
- A "BETTER" comparison result NEVER automatically promotes any production artifact.
- Security regressions explicitly classify comparison as "REGRESSED" and block approval.
- Zero autonomous execution, zero background workers.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from backend.database.repositories.evaluation_repository import EvaluationRepository
from core_model.capabilities.evaluation_service import (
    COMPARISON_BETTER,
    COMPARISON_INCONCLUSIVE,
    COMPARISON_REGRESSED,
    COMPARISON_SAME,
    EvaluationRecord,
    EvaluationService,
    VersionComparison,
)


class VersionComparisonService:
    """Backend service for executing version comparison and regression detection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn
        self.eval_repo = EvaluationRepository(conn)
        self.domain_service = EvaluationService()

    def compare_evaluations(
        self, evaluation_id_a: str, evaluation_id_b: str
    ) -> VersionComparison:
        """Compare two evaluation records (Version A vs Version B) and persist comparison."""
        eval_a = self.eval_repo.get_evaluation_by_id(evaluation_id_a)
        if not eval_a:
            raise ValueError(f"Evaluation record A '{evaluation_id_a}' not found.")

        eval_b = self.eval_repo.get_evaluation_by_id(evaluation_id_b)
        if not eval_b:
            raise ValueError(f"Evaluation record B '{evaluation_id_b}' not found.")

        # Check existing comparison
        existing = self.eval_repo.get_comparison(eval_a.artifact_version, eval_b.artifact_version)
        if existing:
            return existing

        comp = self.domain_service.engine.compare_versions(eval_a, eval_b)
        self.eval_repo.insert_version_comparison(comp)
        return comp
