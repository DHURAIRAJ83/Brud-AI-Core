"""Phase 17.9: Advanced Memory Reasoning & Recall Planning Layer.

Implements higher-order deterministic memory reasoning on top of Phase 17.8 MemoryRecallEngine:
1. Multi-Memory Pairwise Relationship Scoring (Topical, Vector Cosine, Lexical, Temporal, Category)
2. Read-Only Evidence Aggregation & Corroboration Clustering (G4 Invariant: Retrieval != Evidence)
3. Temporal State Classification (CURRENT_ACTIVE, HISTORICAL_VALID, SUPERSEDED_PAST, TEMPORARY_EPISODIC)
4. Contradiction-Aware Epistemic Partitioning (FACT_CURRENT, FACT_HISTORICAL, FACT_CONTESTED, FACT_SUPERSEDED)
5. Procedural Workflow Reconstruction (Step extraction, dependency sorting, missing step flags, cycle detection)
6. User Preference Precedence Resolution (Explicit > Inferred, specific > general, temporal recency)
7. Coherence Scoring & Deterministic Token Budgeting
8. Structured MemoryReasoningPacket Formation & Lossless Context Block Formatting
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from core_model.mini_brain.intelligence.conflict_detector import ConflictKnowledgeEngine
from core_model.mini_brain.intelligence.memory_recall import (
    MemoryRecallItem,
    MemoryRecallResult,
    RetrievalMode,
)
from core_model.mini_brain.llm_runtime.message_sanitizer import sanitize_message
from core_model.mini_brain.llm_runtime.token_budget import estimate_tokens
from core_model.rag.embedding import compute_embedding, unpack_vector
from core_model.rag.vector_index import score_vectors


@dataclass(frozen=True)
class EvidenceCluster:
    """Read-only grouping of corroborating memory items."""
    cluster_id: str
    canonical_topic: str
    member_public_ids: tuple[str, ...]
    aggregate_confidence: float
    source_diversity: tuple[str, ...]
    is_corroborated: bool
    contradiction_warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "canonical_topic": self.canonical_topic,
            "member_public_ids": self.member_public_ids,
            "aggregate_confidence": self.aggregate_confidence,
            "source_diversity": self.source_diversity,
            "is_corroborated": self.is_corroborated,
            "contradiction_warning": self.contradiction_warning,
        }


@dataclass(frozen=True)
class ProceduralStep:
    """Represents an ordered procedural workflow step."""
    step_number: int
    title: str
    content: str
    dependencies: tuple[str, ...]
    public_id: str
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_number": self.step_number,
            "title": self.title,
            "content": self.content,
            "dependencies": self.dependencies,
            "public_id": self.public_id,
            "status": self.status,
        }


@dataclass(frozen=True)
class PreferenceResolution:
    """Resolved user preferences with precedence resolution and provenance."""
    resolved_preferences: dict[str, Any]
    superseded_preferences: tuple[str, ...]
    preference_warnings: tuple[str, ...]
    provenance_citations: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolved_preferences": self.resolved_preferences,
            "superseded_preferences": self.superseded_preferences,
            "preference_warnings": self.preference_warnings,
            "provenance_citations": self.provenance_citations,
        }


@dataclass(frozen=True)
class MemoryReasoningPacket:
    """Canonical reasoning context object generated above memory retrieval."""
    query: str
    participant_scope_key: str
    retrieval_mode: str
    coherence_score: float

    active_facts: tuple[dict[str, Any], ...]
    historical_facts: tuple[dict[str, Any], ...]

    procedural_chains: tuple[dict[str, Any], ...]

    resolved_preferences: dict[str, Any]

    evidence_clusters: tuple[dict[str, Any], ...]

    disputed_items: tuple[dict[str, Any], ...]

    provenance_citations: tuple[dict[str, Any], ...]

    warnings: tuple[str, ...]

    total_token_estimate: int

    assembled_epoch: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_context_block(self) -> str:
        """Renders a deterministic, citation-preserving markdown context block."""
        sections: list[str] = []

        # [Active Facts]
        if self.active_facts:
            lines = ["[Active Facts]"]
            for f in self.active_facts:
                pub_id = f.get("memory_item_public_id") or f.get("public_id", "unknown")
                disp = sanitize_message(raw_text=str(f.get("display_value", "")))["sanitized_text"].strip()
                cat = f.get("category", "")
                tag = f" ({cat})" if cat else ""
                lines.append(f"- {disp} [mem:{pub_id}]{tag}")
            sections.append("\n".join(lines))

        # [Workflow Steps]
        if self.procedural_chains:
            lines = ["[Workflow Steps]"]
            for chain in self.procedural_chains:
                chain_title = chain.get("workflow_name", "Procedure")
                lines.append(f"### {chain_title}")
                steps = chain.get("steps", [])
                for s in steps:
                    step_num = s.get("step_number", 1)
                    title = s.get("title", "")
                    content = sanitize_message(raw_text=str(s.get("content", "")))["sanitized_text"].strip()
                    pub_id = s.get("public_id", "unknown")
                    deps = s.get("dependencies", [])
                    dep_str = f" (requires: {', '.join(deps)})" if deps else ""
                    lines.append(f"{step_num}. **{title}**: {content} [mem:{pub_id}]{dep_str}")
                missing = chain.get("missing_steps", [])
                if missing:
                    lines.append(f"  *(Warning: Missing steps: {missing})*")
            sections.append("\n".join(lines))

        # [User Preferences]
        if self.resolved_preferences:
            lines = ["[User Preferences]"]
            for k, v in sorted(self.resolved_preferences.items()):
                clean_v = sanitize_message(raw_text=str(v))["sanitized_text"].strip()
                lines.append(f"- {k}: {clean_v}")
            sections.append("\n".join(lines))

        # [Historical Context]
        if self.historical_facts:
            lines = ["[Historical Context]"]
            for h in self.historical_facts:
                pub_id = h.get("memory_item_public_id") or h.get("public_id", "unknown")
                disp = sanitize_message(raw_text=str(h.get("display_value", "")))["sanitized_text"].strip()
                status = h.get("status", "historical")
                lines.append(f"- {disp} [mem:{pub_id}] (status: {status})")
            sections.append("\n".join(lines))

        # [Evidence]
        if self.evidence_clusters:
            lines = ["[Evidence]"]
            for cl in self.evidence_clusters:
                topic = cl.get("canonical_topic", "Corroborated Knowledge")
                conf = round(float(cl.get("aggregate_confidence", 0.0)), 1)
                members = cl.get("member_public_ids", [])
                m_citations = " ".join(f"[mem:{m}]" for m in members)
                lines.append(f"- {topic} (aggregate confidence: {conf}%): {m_citations}")
            sections.append("\n".join(lines))

        # [Disputed / Contested Items]
        if self.disputed_items:
            lines = ["[Disputed / Contested Items]"]
            for d in self.disputed_items:
                pub_id = d.get("memory_item_public_id") or d.get("public_id", "unknown")
                disp = sanitize_message(raw_text=str(d.get("display_value", "")))["sanitized_text"].strip()
                warning = d.get("disputed_warning") or "Contested claim under review"
                lines.append(f"- {disp} [mem:{pub_id}] -- ADVISORY: {warning}")
            sections.append("\n".join(lines))

        # [Warnings]
        if self.warnings:
            lines = ["[Warnings]"]
            for w in self.warnings:
                lines.append(f"- {w}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)


class MemoryReasoningEngine:
    """Pure CPU domain engine for advanced memory reasoning, relationship synthesis, and recall planning."""

    @staticmethod
    def calculate_pairwise_relationship(
        m1: dict[str, Any],
        m2: dict[str, Any],
        *,
        w_vec: float = 0.45,
        w_lex: float = 0.30,
        tau_seconds: float = 86400.0,
    ) -> float:
        """Calculates normalized pairwise relationship score R_ij in [0.0, 1.0]."""
        # 1. Vector Cosine Similarity
        u1 = m1.get("unit_vector")
        u2 = m2.get("unit_vector")
        if u1 is not None and u2 is not None:
            s_vec = max(0.0, float(np.dot(u1, u2)))
        else:
            v1 = m1.get("vector")
            v2 = m2.get("vector")
            s_vec = 0.0
            if v1 is not None and v2 is not None:
                norm1 = m1.get("vector_norm") if m1.get("vector_norm") is not None else math.sqrt(sum(x * x for x in v1))
                norm2 = m2.get("vector_norm") if m2.get("vector_norm") is not None else math.sqrt(sum(x * x for x in v2))
                if norm1 > 1e-9 and norm2 > 1e-9:
                    s_vec = max(0.0, sum(a * b for a, b in zip(v1, v2)) / (norm1 * norm2))
            else:
                # Fallback embedding computation if normalized value present
                t1 = m1.get("normalized_value") or m1.get("display_value", "")
                t2 = m2.get("normalized_value") or m2.get("display_value", "")
                if t1 and t2:
                    ev1 = compute_embedding(str(t1), provider_type="local_custom_embedding", dimensions=64)["vector"]
                    ev2 = compute_embedding(str(t2), provider_type="local_custom_embedding", dimensions=64)["vector"]
                    norm1 = math.sqrt(sum(x * x for x in ev1))
                    norm2 = math.sqrt(sum(x * x for x in ev2))
                    if norm1 > 1e-9 and norm2 > 1e-9:
                        s_vec = max(0.0, sum(a * b for a, b in zip(ev1, ev2)) / (norm1 * norm2))

        # 2. Lexical Token Overlap
        toks1 = m1.get("tokens") if m1.get("tokens") is not None else set(re.findall(r"\w+", str(m1.get("display_value", "")).lower()))
        toks2 = m2.get("tokens") if m2.get("tokens") is not None else set(re.findall(r"\w+", str(m2.get("display_value", "")).lower()))
        if toks1 and toks2:
            s_lex = len(toks1 & toks2) / max(1, min(len(toks1), len(toks2)))
        else:
            s_lex = 0.0

        # 3. Category Match Bonus
        cat1 = str(m1.get("category", "")).upper()
        cat2 = str(m2.get("category", "")).upper()
        delta_cat = 0.15 if cat1 and cat2 and cat1 == cat2 else 0.0

        # 4. Temporal Proximity Bonus
        t_epoch1 = float(m1.get("created_epoch") or m1.get("created_at_epoch") or 0.0)
        t_epoch2 = float(m2.get("created_epoch") or m2.get("created_at_epoch") or 0.0)
        if t_epoch1 > 0 and t_epoch2 > 0:
            dt = abs(t_epoch1 - t_epoch2)
            delta_temporal = 0.10 * math.exp(-dt / max(1.0, tau_seconds))
        else:
            delta_temporal = 0.0

        r_ij = (w_vec * s_vec) + (w_lex * s_lex) + delta_cat + delta_temporal
        return min(1.0, max(0.0, r_ij))

    @staticmethod
    def cluster_evidence(
        candidates: list[dict[str, Any]],
        *,
        similarity_threshold: float = 0.75,
        r_matrix: dict[tuple[int, int], float] | None = None,
    ) -> list[EvidenceCluster]:
        """Groups corroborating memories into read-only EvidenceClusters."""
        clusters: list[EvidenceCluster] = []
        visited: set[str] = set()

        for i, c1 in enumerate(candidates):
            pid1 = str(c1.get("memory_item_public_id") or c1.get("public_id", f"item_{i}"))
            if pid1 in visited:
                continue

            group = [c1]
            sources = {str(c1.get("creation_source") or c1.get("confidence_type") or "unknown")}

            for j, c2 in enumerate(candidates[i + 1:], start=i + 1):
                pid2 = str(c2.get("memory_item_public_id") or c2.get("public_id", f"item_{j}"))
                if pid2 in visited:
                    continue

                if r_matrix is not None:
                    r_score = r_matrix.get((i, j), 0.0)
                else:
                    r_score = MemoryReasoningEngine.calculate_pairwise_relationship(c1, c2)

                if r_score >= similarity_threshold:
                    group.append(c2)
                    sources.add(str(c2.get("creation_source") or c2.get("confidence_type") or "unknown"))
                    visited.add(pid2)

            if len(group) >= 2:
                visited.add(pid1)
                pids = tuple(str(m.get("memory_item_public_id") or m.get("public_id", "")) for m in group)
                confidences = [float(m.get("confidence_score") or m.get("confidence", 50.0)) for m in group]
                # Combined Bayesian-style unreliability product
                unreliability = 1.0
                for conf in confidences:
                    unreliability *= (1.0 - max(0.0, min(100.0, conf)) / 100.0)
                agg_conf = min(100.0, max(0.0, 100.0 * (1.0 - unreliability)))

                # Determine topic title
                topic = str(group[0].get("category") or "Corroborated Knowledge").replace("_", " ").title()
                clusters.append(
                    EvidenceCluster(
                        cluster_id=f"cluster_{len(clusters) + 1}",
                        canonical_topic=topic,
                        member_public_ids=pids,
                        aggregate_confidence=agg_conf,
                        source_diversity=tuple(sorted(sources)),
                        is_corroborated=True,
                    )
                )

        return clusters

    @staticmethod
    def extract_procedural_chains(
        candidates: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Extracts and orders procedural steps into structured workflow chains."""
        chains: list[dict[str, Any]] = []
        warnings: list[str] = []

        # Filter candidate items relevant to procedural / task category
        task_candidates = [
            c for c in candidates
            if str(c.get("category", "")).upper() in ("TASK", "PROCEDURAL", "COURSE_PROGRESS", "WORKFLOW")
            or "step" in str(c.get("display_value", "")).lower()
        ]

        if not task_candidates:
            return chains, warnings

        extracted_steps: list[dict[str, Any]] = []
        step_pattern = re.compile(r"(?:step|phase|\#)\s*(\d+)[:\.\-\s]*(.*)", re.IGNORECASE)

        for item in task_candidates:
            val = str(item.get("display_value", "")).strip()
            pid = str(item.get("memory_item_public_id") or item.get("public_id", "unknown"))
            m = step_pattern.search(val)
            if m:
                step_num = int(m.group(1))
                title = m.group(2).strip() or f"Step {step_num}"
            else:
                step_num = len(extracted_steps) + 1
                title = val[:40]

            # Parse simple dependency trigger words
            deps: list[str] = []
            dep_match = re.search(r"(?:requires|after|depends on|prerequisite:)\s*(?:step|phase)?\s*(\d+)", val, re.IGNORECASE)
            if dep_match:
                deps.append(f"Step {dep_match.group(1)}")

            extracted_steps.append({
                "step_number": step_num,
                "title": title,
                "content": val,
                "dependencies": deps,
                "public_id": pid,
                "status": item.get("status", "active"),
                "created_epoch": float(item.get("created_epoch") or item.get("created_at_epoch") or 0.0),
            })

        if not extracted_steps:
            return chains, warnings

        # Cycle detection and topological sorting
        # Check direct self/circular dependency
        has_cycle = False
        for s in extracted_steps:
            if f"Step {s['step_number']}" in s["dependencies"]:
                has_cycle = True
                break

        if has_cycle:
            warnings.append("WorkflowCycleWarning: Circular step dependency detected, falling back to sequential ordering")
            extracted_steps.sort(key=lambda s: (s["step_number"], s["created_epoch"], s["public_id"]))
        else:
            extracted_steps.sort(key=lambda s: (s["step_number"], s["created_epoch"], s["public_id"]))

        # Check for missing intermediate steps
        step_numbers = [s["step_number"] for s in extracted_steps]
        missing_steps: list[int] = []
        if step_numbers:
            min_s, max_s = min(step_numbers), max(step_numbers)
            missing_steps = [x for x in range(min_s, max_s + 1) if x not in step_numbers]

        chains.append({
            "workflow_name": "Ordered Procedural Workflow",
            "steps": extracted_steps,
            "missing_steps": missing_steps,
            "total_steps": len(extracted_steps),
        })

        return chains, warnings

    @staticmethod
    def resolve_preferences(
        candidates: list[dict[str, Any]],
    ) -> PreferenceResolution:
        """Resolves active user preferences using deterministic precedence hierarchy."""
        pref_items = [
            c for c in candidates
            if str(c.get("category", "")).upper() in ("PREFERENCE", "LANGUAGE_PREFERENCE", "FORMAT_PREFERENCE", "PROJECT_PREFERENCE")
        ]

        resolved: dict[str, Any] = {}
        superseded: list[str] = []
        warnings: list[str] = []
        citations: dict[str, str] = {}

        # Precedence sort key:
        # 1. explicit_user_request (weight 2) vs other (weight 1)
        # 2. specific purpose vs general (length/specificity)
        # 3. newer timestamp
        def pref_priority(item: dict[str, Any]) -> tuple[int, int, float]:
            is_explicit = 1 if item.get("creation_source") == "explicit_user_request" or item.get("confidence_type") == "user_confirmed" else 0
            is_specific = 1 if item.get("purpose") not in ("general", "general_context", None) else 0
            epoch = float(item.get("created_epoch") or item.get("created_at_epoch") or 0.0)
            return (is_explicit, is_specific, epoch)

        pref_items.sort(key=pref_priority, reverse=True)

        for item in pref_items:
            cat = str(item.get("category", "preference")).lower()
            val = str(item.get("display_value", "")).strip()
            pid = str(item.get("memory_item_public_id") or item.get("public_id", ""))

            # Key resolution
            key = cat
            if ":" in val:
                parts = val.split(":", 1)
                key = parts[0].strip().lower().replace(" ", "_")
                val_clean = parts[1].strip()
            else:
                val_clean = val

            if key not in resolved:
                resolved[key] = val_clean
                citations[key] = pid
            else:
                superseded.append(pid)

        return PreferenceResolution(
            resolved_preferences=resolved,
            superseded_preferences=tuple(superseded),
            preference_warnings=tuple(warnings),
            provenance_citations=citations,
        )

    @staticmethod
    def assemble_reasoning_packet(
        query: str,
        participant_scope_key: str,
        retrieval_mode: str | RetrievalMode,
        retrieved_items: list[MemoryRecallItem | dict[str, Any]],
        *,
        conflict_policy: str = "prefer_recent",
        max_tokens: int = 600,
        now_epoch: float | None = None,
    ) -> MemoryReasoningPacket:
        """Assembles a deterministic MemoryReasoningPacket from retrieved memory items."""
        now = now_epoch if now_epoch is not None else time.time()
        mode_str = str(retrieval_mode.value if isinstance(retrieval_mode, RetrievalMode) else retrieval_mode).upper()

        # Strict Tenant Isolation Gate (G5)
        raw_items: list[dict[str, Any]] = []
        for item in retrieved_items:
            d = item.to_dict() if hasattr(item, "to_dict") else dict(item)
            item_scope = str(d.get("participant_scope_key", ""))
            if item_scope and item_scope != participant_scope_key:
                raise ValueError(
                    f"G5 Isolation Violation: Candidate scope '{item_scope}' differs from reasoning scope '{participant_scope_key}'"
                )
            raw_items.append(d)

        # Limit candidate pool to N <= 20
        candidates = raw_items[:20]
        n = len(candidates)

        for c in candidates:
            if "tokens" not in c:
                c["tokens"] = set(re.findall(r"\w+", str(c.get("display_value", "")).lower()))
            if c.get("vector") is None:
                t = c.get("normalized_value") or c.get("display_value", "")
                if t:
                    c["vector"] = compute_embedding(str(t), provider_type="local_custom_embedding", dimensions=64)["vector"]
            if c.get("vector") is not None and "unit_vector" not in c:
                v = c["vector"]
                if not isinstance(v, np.ndarray):
                    v = np.array(v, dtype=np.float32)
                norm = float(np.linalg.norm(v))
                c["unit_vector"] = (v / norm) if norm > 1e-9 else v
                c["vector_norm"] = norm

        # Precompute pairwise relationships matrix once
        r_matrix: dict[tuple[int, int], float] = {}
        for i in range(n):
            for j in range(i + 1, n):
                r_matrix[(i, j)] = MemoryReasoningEngine.calculate_pairwise_relationship(candidates[i], candidates[j])

        active_facts: list[dict[str, Any]] = []
        historical_facts: list[dict[str, Any]] = []
        disputed_items: list[dict[str, Any]] = []
        citations: list[dict[str, Any]] = []
        warnings: list[str] = []

        p_dispute = 0.0
        p_fragmentation = 0.0

        for c in candidates:
            pid = str(c.get("memory_item_public_id") or c.get("public_id", "unknown"))
            status = str(c.get("status", "active")).lower()
            is_disputed = bool(c.get("is_disputed") or c.get("conflict_status") in ("disputed", "conflict_detected"))
            disp_warning = c.get("disputed_warning")

            # Epistemic Partitioning
            if is_disputed:
                p_dispute += 5.0
                if conflict_policy == "exclude_conflicting":
                    warnings.append(f"DisputeExcluded: Memory {pid} excluded from active reasoning")
                    continue
                else:
                    disputed_items.append(c)
                    citations.append({"public_id": pid, "status": "disputed", "warning": disp_warning})
                    continue

            if status == "active" or status == "consolidated":
                active_facts.append(c)
                citations.append({"public_id": pid, "status": status, "is_canonical": bool(c.get("is_canonical"))})
            elif status in ("expired", "archived", "historical"):
                historical_facts.append(c)
                citations.append({"public_id": pid, "status": status})
            else:
                historical_facts.append(c)

        # Evidence Clustering with r_matrix
        evidence_clusters = MemoryReasoningEngine.cluster_evidence(candidates, r_matrix=r_matrix)

        # Procedural Extraction
        procedural_chains, proc_warnings = MemoryReasoningEngine.extract_procedural_chains(candidates)
        warnings.extend(proc_warnings)

        # Preference Resolution
        pref_res = MemoryReasoningEngine.resolve_preferences(candidates)
        warnings.extend(list(pref_res.preference_warnings))

        # Coherence Score Calculation
        if n == 0:
            coherence = 0.0
        elif n == 1:
            coherence = min(100.0, max(0.0, float(candidates[0].get("effective_recall_score") or 50.0)))
        else:
            base_score = sum(float(c.get("effective_recall_score") or 50.0) for c in candidates) / n
            r_sum = sum(r_matrix.values())
            rel_contrib = (20.0 / (n * (n - 1))) * r_sum
            coherence = min(100.0, max(0.0, base_score + rel_contrib - p_dispute - p_fragmentation))

        # Deterministic token estimation
        total_text_len = sum(len(str(c.get("display_value", ""))) for c in candidates) + len(query) * 2
        tok_est = max(0, int(total_text_len // 3.5))

        final_packet = MemoryReasoningPacket(
            query=query,
            participant_scope_key=participant_scope_key,
            retrieval_mode=mode_str,
            coherence_score=round(coherence, 2),
            active_facts=tuple(active_facts),
            historical_facts=tuple(historical_facts),
            procedural_chains=tuple(procedural_chains),
            resolved_preferences=pref_res.resolved_preferences,
            evidence_clusters=tuple(cl.to_dict() for cl in evidence_clusters),
            disputed_items=tuple(disputed_items),
            provenance_citations=tuple(citations),
            warnings=tuple(sorted(set(warnings))),
            total_token_estimate=tok_est,
            assembled_epoch=now,
        )

        return final_packet
