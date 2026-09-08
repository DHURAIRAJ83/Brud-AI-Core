"""Phase 17.2: Context Intelligence Layer.

Implements bounded, CPU/local-first conversation context intelligence:
1. Active Topic Tracking & Topic Transition Detection (Continuation, Related, New, Unknown)
2. Tamil & English Reference / Anaphora Resolution ("அது", "இதில்", "முந்தையது", "the previous one", etc.)
3. Unresolved Question Tracking with bounded history
4. Documented Context Relevance Ranking (0-100 scale)
5. Context Token Budgeting & Low-Relevance Pruning
6. G8 Secret Sanitization across all context state
7. Integration with canonical context orchestrator
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from core_model.conversation.context_orchestrator import build_context_items
from core_model.mini_brain.llm_runtime.message_sanitizer import sanitize_message
from core_model.mini_brain.llm_runtime.token_budget import estimate_tokens

# --- Domain Topic Taxonomy ---
TOPIC_TAXONOMY: dict[str, list[str]] = {
    "database_backup": [
        "backup", "restore", "snapshot", "backups", "database backup", "wal",
        "பேக்கப்", "மீட்டெடுப்பு", "தரவுத்தளம்", "டேட்டாபேஸ்"
    ],
    "rag_duplicate_detection": [
        "rag duplicate", "duplicate", "deduplication", "rag index", "rag sandbox",
        "vector index", "chunk", "citation", "டூப்ளிகேட்", "நகல்", "தேடல்", "ராக்"
    ],
    "training_dataset": [
        "dataset", "training", "sft", "corpus", "data source", "sample import",
        "quarantine", "மாதிரி", "தரவுத்தொகுப்பு", "பயிற்சி", "கற்பித்தல்"
    ],
    "model_release": [
        "model release", "deployment", "canary", "checkpoint", "activation",
        "rollback", "வெளியீடு", "மாடல்", "செயலாக்கம்"
    ],
    "security_review": [
        "security", "vulnerability", "audit", "pii", "secret", "permission",
        "பாதுகாப்பு", "தணிக்கை", "ரகசியம்"
    ],
    "system_health": [
        "health", "system status", "service slow", "cpu", "memory", "latency",
        "performance", "incident", "நலநிலை", "சேவை", "வேகம்", "மெதுவான"
    ],
    "plugin_governance": [
        "plugin", "execution token", "plugin runtime", "செருகுநிரல்", "அனுமதி"
    ],
    "conversation_memory": [
        "memory policy", "session memory", "consent", "turn persistence",
        "நினைவகம்", "அமர்வு", "ஒப்புதல்"
    ],
}

TOPIC_CLUSTERS: list[set[str]] = [
    {"database_backup", "system_health"},
    {"training_dataset", "rag_duplicate_detection"},
    {"model_release", "system_health"},
    {"security_review", "plugin_governance"},
    {"conversation_memory", "system_health"},
]

# --- Reference / Anaphora Patterns ---
TAMIL_REFERENCE_PATTERNS: list[tuple[str, str]] = [
    (r"(?:^|\s|[.,?!])அது(?:$|\s|[.,?!])", "that / it"),
    (r"(?:^|\s|[.,?!])இது(?:$|\s|[.,?!])", "this"),
    (r"(?:^|\s|[.,?!])இதில்(?:$|\s|[.,?!])", "in this"),
    (r"(?:^|\s|[.,?!])அதில்(?:$|\s|[.,?!])", "in that"),
    (r"(?:^|\s|[.,?!])முந்தையது(?:$|\s|[.,?!])", "the previous one"),
    (r"(?:^|\s|[.,?!])மேலே சொன்னது(?:$|\s|[.,?!])", "the above said"),
    (r"(?:^|\s|[.,?!])அந்த file(?:$|\s|[.,?!])", "that file"),
    (r"(?:^|\s|[.,?!])அந்த model(?:$|\s|[.,?!])", "that model"),
    (r"(?:^|\s|[.,?!])இதை(?:$|\s|[.,?!])", "this (accusative)"),
    (r"(?:^|\s|[.,?!])அதை(?:$|\s|[.,?!])", "that (accusative)"),
]

ENGLISH_REFERENCE_PATTERNS: list[tuple[str, str]] = [
    (r"\bthe previous one\b", "the previous one"),
    (r"\bthe above\b", "the above"),
    (r"\bthis one\b", "this one"),
    (r"\bthat file\b", "that file"),
    (r"\bthat model\b", "that model"),
    (r"\bthe earlier result\b", "the earlier result"),
    (r"\bit\b", "it"),
    (r"\bthis\b", "this"),
    (r"\bthat\b", "that"),
]

QUESTION_INDICATORS = [
    "?", "ஏன்", "எப்படி", "எப்போது", "எங்கு", "என்ன", "எது",
    "why", "how", "when", "where", "what", "which", "who",
    "check", "explain", "why is", "how to", "is it"
]


@dataclass
class ResolvedReference:
    reference_text: str
    language: str
    status: str  # "RESOLVED" | "UNKNOWN"
    resolved_entity: str | None
    target_type: str | None  # "topic" | "file" | "model" | "turn_result" | None
    confidence: float


@dataclass
class UnresolvedQuestion:
    question_id: str
    question_text: str
    topic: str | None
    turn_index: int
    status: str  # "UNRESOLVED" | "RESOLVED"
    created_at_turn: int


@dataclass
class ContextState:
    conversation_id: str
    active_topic: str | None
    previous_topic: str | None
    topic_changed: bool
    topic_transition: str  # "CONTINUATION" | "RELATED_TOPIC" | "NEW_TOPIC" | "UNKNOWN"
    current_intent: str
    unresolved_questions: list[dict[str, Any]] = field(default_factory=list)
    resolved_references: list[dict[str, Any]] = field(default_factory=list)
    relevant_turns: list[dict[str, Any]] = field(default_factory=list)
    context_budget: dict[str, Any] = field(default_factory=dict)
    context_items: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ContextIntelligenceManager:
    """Bounded, CPU/local-first Context Intelligence Manager."""

    def __init__(self, max_unresolved_history: int = 5, max_context_turns: int = 20) -> None:
        self.max_unresolved_history = max_unresolved_history
        self.max_context_turns = max_context_turns

    def detect_topic(self, text: str) -> str | None:
        """Determines the topic of a text snippet using deterministic taxonomy."""
        if not text:
            return None
        text_lower = text.lower()
        scored_topics: list[tuple[str, int]] = []
        for topic, keywords in TOPIC_TAXONOMY.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                scored_topics.append((topic, score))
        if not scored_topics:
            return None
        scored_topics.sort(key=lambda x: x[1], reverse=True)
        return scored_topics[0][0]

    def detect_topic_transition(
        self,
        current_topic: str | None,
        previous_topic: str | None,
        has_anaphora_reference: bool = False,
    ) -> str:
        """Determines topic transition state."""
        if not current_topic and not previous_topic:
            return "UNKNOWN"
        if not current_topic and previous_topic:
            return "CONTINUATION" if has_anaphora_reference else "UNKNOWN"
        if current_topic and not previous_topic:
            return "NEW_TOPIC"
        if current_topic == previous_topic:
            return "CONTINUATION"
        if previous_topic is not None and current_topic is not None:
            for cluster in TOPIC_CLUSTERS:
                if current_topic in cluster and previous_topic in cluster:
                    return "RELATED_TOPIC"
        return "NEW_TOPIC"

    def resolve_references(
        self,
        current_text: str,
        recent_turns: list[dict[str, Any]],
        active_topic: str | None = None,
    ) -> list[ResolvedReference]:
        """Resolves Tamil and English anaphora/contextual references against recent turns."""
        resolved: list[ResolvedReference] = []
        if not current_text:
            return resolved

        # Check Tamil references
        for pattern, ref_type in TAMIL_REFERENCE_PATTERNS:
            if re.search(pattern, current_text, re.IGNORECASE):
                ref = self._resolve_single_reference(
                    pattern=pattern,
                    matched_text=ref_type,
                    language="tamil",
                    recent_turns=recent_turns,
                    active_topic=active_topic,
                )
                resolved.append(ref)

        # Check English references
        for pattern, ref_type in ENGLISH_REFERENCE_PATTERNS:
            if re.search(pattern, current_text, re.IGNORECASE):
                ref = self._resolve_single_reference(
                    pattern=pattern,
                    matched_text=ref_type,
                    language="english",
                    recent_turns=recent_turns,
                    active_topic=active_topic,
                )
                resolved.append(ref)

        return resolved

    def _resolve_single_reference(
        self,
        pattern: str,
        matched_text: str,
        language: str,
        recent_turns: list[dict[str, Any]],
        active_topic: str | None,
    ) -> ResolvedReference:
        if not recent_turns:
            return ResolvedReference(
                reference_text=matched_text,
                language=language,
                status="UNKNOWN",
                resolved_entity=None,
                target_type=None,
                confidence=0.0,
            )

        last_turn = recent_turns[-1]
        last_content = last_turn.get("content", "") or last_turn.get("sanitized_text", "")

        # Target file or checkpoint reference
        file_match = re.search(r"([\w\-_\./]+\.(?:py|json|md|db|csv|txt|log|bin))", last_content, re.IGNORECASE)
        if file_match and ("file" in pattern.lower() or "previous" in matched_text.lower() or "this" in matched_text.lower() or "that" in matched_text.lower()):
            return ResolvedReference(
                reference_text=matched_text,
                language=language,
                status="RESOLVED",
                resolved_entity=file_match.group(1),
                target_type="file",
                confidence=0.95,
            )

        # Target model reference
        if "model" in pattern.lower():
            model_match = re.search(r"\b(llama[\w\-\.]*|gemini[\w\-\.]*|qwen[\w\-\.]*|ollama[\w\-\.]*)\b", last_content, re.IGNORECASE)
            if model_match:
                return ResolvedReference(
                    reference_text=matched_text,
                    language=language,
                    status="RESOLVED",
                    resolved_entity=model_match.group(1),
                    target_type="model",
                    confidence=0.90,
                )

        # Turn result reference for previous one / results
        if "previous" in matched_text.lower() or "முந்தையது" in pattern or "%" in last_content:
            if "%" in last_content or "accuracy" in last_content.lower() or "score" in last_content.lower() or "rag" in last_content.lower():
                short_entity = last_content[:80].strip()
                return ResolvedReference(
                    reference_text=matched_text,
                    language=language,
                    status="RESOLVED",
                    resolved_entity=short_entity,
                    target_type="turn_result",
                    confidence=0.85,
                )

        # Topic-level reference
        topic = self.detect_topic(last_content) or active_topic
        if topic:
            return ResolvedReference(
                reference_text=matched_text,
                language=language,
                status="RESOLVED",
                resolved_entity=topic,
                target_type="topic",
                confidence=0.85,
            )

        # Previous turn summary reference
        if last_content:
            short_entity = last_content[:80].strip()
            return ResolvedReference(
                reference_text=matched_text,
                language=language,
                status="RESOLVED",
                resolved_entity=short_entity,
                target_type="turn_result",
                confidence=0.75,
            )

        return ResolvedReference(
            reference_text=matched_text,
            language=language,
            status="UNKNOWN",
            resolved_entity=None,
            target_type=None,
            confidence=0.0,
        )

    def is_question(self, text: str) -> bool:
        """Determines if the text contains a question/investigation intent."""
        if not text:
            return False
        text_lower = text.lower()
        return any(ind in text_lower for ind in QUESTION_INDICATORS)

    def manage_unresolved_questions(
        self,
        current_text: str,
        existing_unresolved: list[dict[str, Any]],
        current_turn_index: int,
        topic: str | None,
        is_assistant_reply: bool = False,
    ) -> list[dict[str, Any]]:
        """Updates and bounds unresolved questions buffer."""
        updated: list[dict[str, Any]] = [dict(q) for q in existing_unresolved]

        if is_assistant_reply:
            # If assistant replied, mark unresolved questions matching the topic as resolved
            for q in updated:
                if q.get("status") == "UNRESOLVED":
                    if topic and q.get("topic") == topic:
                        q["status"] = "RESOLVED"
                    elif len(current_text) > 30:
                        # Non-trivial response resolves top pending question
                        q["status"] = "RESOLVED"
        else:
            # User turn
            if self.is_question(current_text):
                # Add new unresolved item
                qid = f"uq_{current_turn_index}"
                new_q = {
                    "question_id": qid,
                    "question_text": current_text[:150],
                    "topic": topic,
                    "turn_index": current_turn_index,
                    "status": "UNRESOLVED",
                    "created_at_turn": current_turn_index,
                }
                updated.append(new_q)

        # Keep only unresolved questions plus bounded history
        unresolved_only = [q for q in updated if q["status"] == "UNRESOLVED"]
        resolved_history = [q for q in updated if q["status"] == "RESOLVED"]
        bounded = unresolved_only[-self.max_unresolved_history:] + resolved_history[-2:]
        return bounded

    def score_turn_relevance(
        self,
        turn: dict[str, Any],
        turn_index: int,
        total_turns: int,
        active_topic: str | None,
        resolved_references: list[ResolvedReference],
        unresolved_questions: list[dict[str, Any]],
        active_task: str | None = None,
    ) -> float:
        """Calculates bounded relevance score (0 - 100) for a turn.

        Formula:
        relevance_score =
            task_relevance (0-30)
            + topic_relevance (0-25)
            + reference_relevance (0-20)
            + unresolved_relevance (0-15)
            + recency_score (0-10)
        """
        content = turn.get("content", "") or turn.get("sanitized_text", "")
        content_lower = content.lower()

        # 1. Task relevance (0 - 30)
        task_score = 0.0
        if active_task and active_task.lower() in content_lower:
            task_score = 30.0

        # 2. Topic relevance (0 - 25)
        topic_score = 0.0
        if active_topic:
            turn_topic = self.detect_topic(content)
            if turn_topic == active_topic:
                topic_score = 25.0
            elif turn_topic is not None and active_topic is not None:
                for cluster in TOPIC_CLUSTERS:
                    if turn_topic in cluster and active_topic in cluster:
                        topic_score = 15.0
                        break

        # 3. Reference relevance (0 - 20)
        ref_score = 0.0
        for ref in resolved_references:
            if ref.status == "RESOLVED" and ref.resolved_entity:
                ref_ent = ref.resolved_entity.lower().replace("_", " ")
                if ref_ent in content_lower or ref.resolved_entity.lower() in content_lower:
                    ref_score = max(ref_score, 20.0 * ref.confidence)

        # 4. Unresolved question relevance (0 - 15)
        unresolved_score = 0.0
        for uq in unresolved_questions:
            if uq.get("status") == "UNRESOLVED":
                q_text = uq.get("question_text", "").lower()
                if q_text:
                    q_words = [w for w in q_text.split() if len(w) > 3]
                    if q_text in content_lower or content_lower in q_text or (q_words and any(w in content_lower for w in q_words)):
                        unresolved_score = 15.0
                        break

        # 5. Recency score (0 - 10)
        recency_score = 0.0
        if total_turns > 0:
            recency_ratio = max(0.0, min(1.0, turn_index / total_turns))
            recency_score = 10.0 * recency_ratio

        total_score = round(task_score + topic_score + ref_score + unresolved_score + recency_score, 2)
        return min(100.0, max(0.0, total_score))

    def evaluate_context(
        self,
        *,
        conversation_id: str,
        current_request_text: str,
        history_turns: list[dict[str, Any]],
        system_instructions: str = "",
        rag_chunks: list[dict[str, Any]] | None = None,
        confirmed_memory_items: list[dict[str, Any]] | None = None,
        other_memory_items: list[dict[str, Any]] | None = None,
        existing_unresolved: list[dict[str, Any]] | None = None,
        previous_topic: str | None = None,
        token_budget_limit: int = 2048,
        active_task: str | None = None,
        trace_id: str | None = None,
    ) -> ContextState:
        """Performs full Context Intelligence evaluation for the current turn."""
        # 1. G8 Secret Sanitization
        sanitized_req = sanitize_message(raw_text=current_request_text)["sanitized_text"]

        # 2. Topic Detection & Transition
        current_topic = self.detect_topic(sanitized_req)
        # Check anaphora presence
        has_anaphora = False
        for p, _ in TAMIL_REFERENCE_PATTERNS + ENGLISH_REFERENCE_PATTERNS:
            if re.search(p, sanitized_req, re.IGNORECASE):
                has_anaphora = True
                break

        active_topic = current_topic or (previous_topic if has_anaphora else None)
        topic_transition = self.detect_topic_transition(
            current_topic=current_topic,
            previous_topic=previous_topic,
            has_anaphora_reference=has_anaphora,
        )
        topic_changed = topic_transition in ("NEW_TOPIC",)

        # 3. Reference Resolution
        resolved_refs = self.resolve_references(
            current_text=sanitized_req,
            recent_turns=history_turns,
            active_topic=active_topic,
        )

        # 4. Unresolved Question Management
        unresolved_questions = self.manage_unresolved_questions(
            current_text=sanitized_req,
            existing_unresolved=existing_unresolved or [],
            current_turn_index=len(history_turns) + 1,
            topic=active_topic,
            is_assistant_reply=False,
        )

        # 5. Relevance Scoring & Ranking of Previous Turns
        ranked_turns: list[dict[str, Any]] = []
        total_turns = len(history_turns)
        for idx, turn in enumerate(history_turns, start=1):
            score = self.score_turn_relevance(
                turn=turn,
                turn_index=idx,
                total_turns=total_turns,
                active_topic=active_topic,
                resolved_references=resolved_refs,
                unresolved_questions=unresolved_questions,
                active_task=active_task,
            )
            enriched_turn = dict(turn)
            enriched_turn["relevance_score"] = score
            enriched_turn["turn_index"] = idx
            ranked_turns.append(enriched_turn)

        # Sort by relevance score descending
        ranked_turns.sort(key=lambda t: t["relevance_score"], reverse=True)

        # 6. Context Budget Allocation & Selection
        selected_turns: list[dict[str, Any]] = []
        used_tokens = estimate_tokens(system_instructions) + estimate_tokens(sanitized_req)
        dropped_turns_count = 0

        # Always include the most recent prior reply if exists for continuity
        if history_turns:
            most_recent = history_turns[-1]
            mr_tokens = estimate_tokens(most_recent.get("content", "") or most_recent.get("sanitized_text", ""))
            if used_tokens + mr_tokens <= token_budget_limit:
                selected_turns.append(most_recent)
                used_tokens += mr_tokens

        # Fill remaining budget with highest relevance ranked turns
        for turn in ranked_turns:
            if any(t.get("public_id") == turn.get("public_id") for t in selected_turns if turn.get("public_id")):
                continue
            turn_text = turn.get("content", "") or turn.get("sanitized_text", "")
            cost = estimate_tokens(turn_text)
            if used_tokens + cost <= token_budget_limit:
                selected_turns.append(turn)
                used_tokens += cost
            else:
                dropped_turns_count += 1

        # Re-sort selected turns into chronological order
        selected_turns.sort(key=lambda t: t.get("turn_index", 0))

        # Format turn items for canonical context orchestrator
        formatted_turns = []
        for t in selected_turns:
            text = t.get("content", "") or t.get("sanitized_text", "")
            formatted_turns.append({
                "public_id": t.get("public_id") or f"turn_{t.get('turn_index', 0)}",
                "token_count": estimate_tokens(text),
                "content": text,
            })

        # 7. Canonical Context Items Assembly
        context_items = build_context_items(
            system_instructions_text=system_instructions,
            current_request_text=sanitized_req,
            rag_chunks=rag_chunks or [],
            confirmed_memory_items=confirmed_memory_items or [],
            recent_turns=formatted_turns,
            validated_summary=None,
            other_memory_items=other_memory_items or [],
            estimate_tokens=estimate_tokens,
        )

        budget_info = {
            "token_budget_limit": token_budget_limit,
            "used_tokens": used_tokens,
            "remaining_tokens": max(0, token_budget_limit - used_tokens),
            "total_turns": total_turns,
            "selected_turns_count": len(selected_turns),
            "dropped_turns_count": dropped_turns_count,
        }

        # Intent inference
        intent = "QUESTION" if self.is_question(sanitized_req) else "STATEMENT"
        if has_anaphora:
            intent = "FOLLOW_UP"

        return ContextState(
            conversation_id=conversation_id,
            active_topic=active_topic,
            previous_topic=previous_topic,
            topic_changed=topic_changed,
            topic_transition=topic_transition,
            current_intent=intent,
            unresolved_questions=unresolved_questions,
            resolved_references=[asdict(r) for r in resolved_refs],
            relevant_turns=selected_turns,
            context_budget=budget_info,
            context_items=context_items,
            trace_id=trace_id,
        )
