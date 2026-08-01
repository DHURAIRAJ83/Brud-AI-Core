"""SFT (supervised fine-tuning) candidate generation and review for documents.

Generates candidates only from approved semantic chunks (`semantic_chunks.status='approved'`,
reusing Phase 5's chunk service and schema unchanged -- no second chunk table), from
already-reviewed Tamil quality corrections, and from calculator-verified arithmetic --
never from raw model inference. This session runs in CPU-only, no-model-inference mode,
so every generated candidate is a direct, source-grounded, or independently-verified
transformation (never an invented fact), and only the task types that can be produced this
way are generated. `contextual_meaning`, `multiple_meanings`, `clarification_request`,
`computer_basics`, and `safety_response` are supported by the schema/review/export pipeline
but are not generated in this pass -- no non-fabricated data source exists for them in this
repository. See docs/data_studio/document_sft_finalization_audit.md for the full disclosure.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from uuid import uuid4

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.data_sources import DataSourceRepository
from backend.database.repositories.documents import DocumentRepository, decode
from backend.models.documents import (
    SftBulkApprovalRequest,
    SftCandidateGenerationRequest,
    SftCandidateReviewAction,
)
from backend.services.document_service import audit, now
from core_model.tool_gateway.calculator import CalculatorError
from core_model.tool_gateway.calculator import evaluate as calculator_evaluate

_CANDIDATE_JSON: set[str] = set()

_STANDALONE_TASK_BY_CHUNK_TYPE = {
    "definition": "definition",
    "dictionary_entry": "definition",
    "example": "explanation",
    "grammar_rule": "grammar",
}

# Adjacent-chunk pairing: (prompt_chunk_type, response_chunk_type) -> task.
# Only fires for two chunks that are direct siblings (same parent_chunk_id,
# consecutive reading_order) -- never a guessed pairing across the document.
_PAIR_TASK_BY_TYPES = {
    ("question", "answer"): "fact_answer",
    ("instruction", "response"): "instruction_following",
}
_TRANSLATION_TYPES = ("translation_source", "translation_target")
_TANGLISH_TYPES = ("tanglish_text", "tamil_text")
_TAMIL_LANGUAGE_ALIASES = {"ta", "tamil"}
_ENGLISH_LANGUAGE_ALIASES = {"en", "english"}

_MIN_SUMMARIZATION_CHARS = 400
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?ெ-்])\s+")
_ARITHMETIC_STATEMENT = re.compile(
    r"(?<![\w.])(\d+(?:\.\d+)?\s*[+\-*/]\s*\d+(?:\.\d+)?)\s*=\s*(-?\d+(?:\.\d+)?)(?!\w)"
)

_LOW_RISK_GENERATION_METHODS = {
    "template_heuristic_v1",
    "chunk_pair_v1",
    "reviewed_correction_v1",
    "calculator_verified_v1",
}

_BLOCKED_RIGHTS_STATUSES = {"restricted", "prohibited", "expired", "internal_only"}
_ELIGIBLE_RIGHTS_STATUSES = {"public_domain", "open_license", "licensed", "permission_granted"}

_TAMIL_TEMPLATES = {
    "definition": "இந்த பத்தியில் விவரிக்கப்பட்டுள்ள சொல்லின் பொருளை விளக்குக.",
    "explanation": "இந்த உதாரணத்தை விளக்குக.",
    "grammar": "இந்த இலக்கண விதியை விளக்குக.",
    "summarization": "இந்த பத்தியை சுருக்கவும்.",
}
_ENGLISH_TEMPLATES = {
    "definition": "Explain the meaning of the term covered in this passage.",
    "explanation": "Explain this example.",
    "grammar": "Explain this grammar rule.",
    "summarization": "Summarize this passage.",
}


def _instruction_for(task: str, language: str) -> str:
    templates = _TAMIL_TEMPLATES if language in _TAMIL_LANGUAGE_ALIASES else _ENGLISH_TEMPLATES
    return templates.get(task, _ENGLISH_TEMPLATES[task])


def _content_hash(task: str, instruction: str, response: str) -> str:
    digest = hashlib.sha256()
    digest.update(f"{task}:{instruction}:{response}".encode())
    return digest.hexdigest()


class DocumentSftCandidateGenerationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = DocumentRepository(settings.resolved_database_path)
        self.source_repository = DataSourceRepository(settings.resolved_database_path)

    def _rights_status(self, document_public_id: str) -> str:
        with self.source_repository.transaction() as connection:
            links = self.source_repository.links_for_entity(
                connection, "document", document_public_id
            )
            if not links:
                return "pending"
            source = self.source_repository.source_by_id(connection, links[0]["data_source_id"])
            rights = self.source_repository.rights_for_source(connection, source["id"])
        status = rights["rights_status"] if rights else "unknown"
        training_use_allowed = bool(rights and rights["training_use_allowed"])
        if rights is None or status in ("unknown", "pending_review"):
            return "pending"
        if status in _BLOCKED_RIGHTS_STATUSES or not training_use_allowed:
            return "blocked"
        if status in _ELIGIBLE_RIGHTS_STATUSES and training_use_allowed:
            return "verified"
        return "pending"

    def _insert_candidate(
        self, connection, *, document_id: int, chunk_id: int | None, page_start: int,
        page_end: int, task: str, domain: str, instruction: str, context: str, response: str,
        input_language: str, output_language: str, rights_status: str, generation_method: str,
    ) -> str | None:
        digest = _content_hash(task, instruction, response)
        duplicate = connection.execute(
            "SELECT public_id FROM document_sft_candidates WHERE content_hash=?", (digest,)
        ).fetchone()
        candidate_id = str(uuid4())
        connection.execute(
            """INSERT INTO document_sft_candidates(
                public_id,document_source_id,source_chunk_id,source_page_start,
                source_page_end,task,domain,difficulty,instruction,context,response,
                input_language,output_language,rights_status,quality_status,
                generation_method,content_hash,duplicate_of_public_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                candidate_id, document_id, chunk_id, page_start, page_end, task, domain,
                "basic", instruction, context, response, input_language, output_language,
                rights_status, "duplicate" if duplicate else "pending_review",
                generation_method, digest, duplicate["public_id"] if duplicate else None,
            ),
        )
        return candidate_id

    def _generate_standalone(self, connection, document, chunks, rights_status, budget):
        created: list[str] = []
        for chunk in chunks:
            if len(created) >= budget:
                break
            task = _STANDALONE_TASK_BY_CHUNK_TYPE.get(chunk["chunk_type"])
            text = (chunk["text"] or "").strip()
            if task is None or not text:
                continue
            language = chunk["language"] or "unknown"
            page_number = chunk["page_number"] or 1
            candidate_id = self._insert_candidate(
                connection, document_id=document["id"], chunk_id=chunk["id"],
                page_start=page_number, page_end=page_number, task=task,
                domain=chunk["domain"] or "general", instruction=_instruction_for(task, language),
                context="", response=text, input_language=language, output_language=language,
                rights_status=rights_status, generation_method="template_heuristic_v1",
            )
            created.append(candidate_id)
        return created

    def _generate_summaries(self, connection, document, chunks, rights_status, budget):
        created: list[str] = []
        for chunk in chunks:
            if len(created) >= budget:
                break
            if chunk["chunk_type"] != "paragraph":
                continue
            text = (chunk["text"] or "").strip()
            if len(text) < _MIN_SUMMARIZATION_CHARS:
                continue
            sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text) if s.strip()]
            if not sentences:
                continue
            # Conservative, source-grounded proxy: the chunk's own opening
            # sentence, never a paraphrase invented beyond the source text.
            summary = sentences[0]
            language = chunk["language"] or "unknown"
            page_number = chunk["page_number"] or 1
            candidate_id = self._insert_candidate(
                connection, document_id=document["id"], chunk_id=chunk["id"],
                page_start=page_number, page_end=page_number, task="summarization",
                domain=chunk["domain"] or "general",
                instruction=_instruction_for("summarization", language), context=text,
                response=summary, input_language=language, output_language=language,
                rights_status=rights_status, generation_method="template_heuristic_v1",
            )
            created.append(candidate_id)
        return created

    def _generate_pairs(self, connection, document, chunks, rights_status, budget):
        created: list[str] = []
        by_parent: dict[Any, list[Any]] = {}
        for chunk in chunks:
            by_parent.setdefault(chunk["parent_chunk_id"], []).append(chunk)
        for siblings in by_parent.values():
            index = 0
            while index < len(siblings) - 1 and len(created) < budget:
                first, second = siblings[index], siblings[index + 1]
                task, input_language, output_language = self._pair_task(first, second)
                index += 1
                if task is None:
                    continue
                first_text = (first["text"] or "").strip()
                second_text = (second["text"] or "").strip()
                if not first_text or not second_text:
                    continue
                page_start = min(first["page_number"] or 1, second["page_number"] or 1)
                page_end = max(first["page_number"] or 1, second["page_number"] or 1)
                candidate_id = self._insert_candidate(
                    connection, document_id=document["id"], chunk_id=first["id"],
                    page_start=page_start, page_end=page_end, task=task,
                    domain=first["domain"] or "general", instruction=first_text, context="",
                    response=second_text, input_language=input_language,
                    output_language=output_language, rights_status=rights_status,
                    generation_method="chunk_pair_v1",
                )
                created.append(candidate_id)
                index += 1
        return created

    @staticmethod
    def _pair_task(first, second) -> tuple[str | None, str, str]:
        pair_types = (first["chunk_type"], second["chunk_type"])
        first_language = (first["language"] or "unknown").lower()
        second_language = (second["language"] or "unknown").lower()
        if pair_types in _PAIR_TASK_BY_TYPES:
            return _PAIR_TASK_BY_TYPES[pair_types], first_language, second_language
        if pair_types == _TRANSLATION_TYPES:
            first_is_tamil = first_language in _TAMIL_LANGUAGE_ALIASES
            second_is_tamil = second_language in _TAMIL_LANGUAGE_ALIASES
            first_is_english = first_language in _ENGLISH_LANGUAGE_ALIASES
            second_is_english = second_language in _ENGLISH_LANGUAGE_ALIASES
            if first_is_tamil and second_is_english:
                return "Tamil_to_English", first_language, second_language
            if first_is_english and second_is_tamil:
                return "English_to_Tamil", first_language, second_language
            return None, first_language, second_language
        if pair_types == _TANGLISH_TYPES:
            return "Tanglish_input_to_Tamil", first_language, second_language
        return None, first_language, second_language

    def _generate_spelling_corrections(self, connection, document, rights_status, budget):
        created: list[str] = []
        rows = connection.execute(
            "SELECT * FROM document_tamil_quality_issues WHERE document_source_id=? "
            "AND review_status IN ('accepted','edited') ORDER BY id",
            (document["id"],),
        ).fetchall()
        for row in rows:
            if len(created) >= budget:
                break
            corrected = row["suggested_text"] or row["original_text"]
            if not row["original_text"] or not corrected or row["original_text"] == corrected:
                continue
            candidate_id = self._insert_candidate(
                connection, document_id=document["id"], chunk_id=None,
                page_start=row["page_number"], page_end=row["page_number"],
                task="spelling_correction", domain="general",
                instruction=row["original_text"], context=row["context"], response=corrected,
                input_language="ta", output_language="ta", rights_status=rights_status,
                generation_method="reviewed_correction_v1",
            )
            created.append(candidate_id)
        return created

    def _generate_math_reasoning(self, connection, document, chunks, rights_status, budget):
        created: list[str] = []
        for chunk in chunks:
            if len(created) >= budget:
                break
            text = chunk["text"] or ""
            for match in _ARITHMETIC_STATEMENT.finditer(text):
                if len(created) >= budget:
                    break
                expression, stated_answer = match.group(1), match.group(2)
                try:
                    result = calculator_evaluate(expression)
                except CalculatorError:
                    continue
                if result.result.strip("0").rstrip(".") != stated_answer.strip("0").rstrip("."):
                    # Source states an answer the deterministic calculator
                    # disagrees with -- never generate a candidate that
                    # would teach an incorrect arithmetic fact.
                    continue
                language = chunk["language"] or "unknown"
                page_number = chunk["page_number"] or 1
                instruction = (
                    f"Calculate {expression.strip()}." if language not in _TAMIL_LANGUAGE_ALIASES
                    else f"{expression.strip()} என்பதைக் கணக்கிடுக."
                )
                candidate_id = self._insert_candidate(
                    connection, document_id=document["id"], chunk_id=chunk["id"],
                    page_start=page_number, page_end=page_number, task="basic_math_reasoning",
                    domain=chunk["domain"] or "mathematics", instruction=instruction,
                    context=text, response=result.result, input_language=language,
                    output_language=language, rights_status=rights_status,
                    generation_method="calculator_verified_v1",
                )
                created.append(candidate_id)
        return created

    def generate(
        self, document_public_id: str, payload: SftCandidateGenerationRequest, admin_id: str
    ) -> dict[str, Any]:
        rights_status = self._rights_status(document_public_id)
        if rights_status == "blocked":
            raise ValidationError(
                "this document's rights status blocks SFT candidate generation"
            )
        max_candidates = payload.max_candidates or self.settings.document_sft_max_candidates_per_job
        if max_candidates > self.settings.document_sft_generator_max_candidates:
            raise ValidationError(
                "max_candidates exceeds the configured generator batch limit "
                f"({self.settings.document_sft_generator_max_candidates})"
            )
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            query = (
                "SELECT c.id,c.public_id,c.chunk_type,c.language,c.domain,c.parent_chunk_id,"
                "r.text,r.page_number "
                "FROM semantic_chunks c JOIN semantic_chunk_revisions r "
                "ON r.id=c.active_revision_id "
                "WHERE c.document_source_id=? AND c.status='approved'"
            )
            params: list[Any] = [document["id"]]
            if payload.chunk_public_ids:
                placeholders = ",".join("?" for _ in payload.chunk_public_ids)
                query += f" AND c.public_id IN ({placeholders})"
                params.extend(payload.chunk_public_ids)
            query += " ORDER BY c.reading_order,c.id"
            chunks = connection.execute(query, params).fetchall()
            if not chunks:
                raise ValidationError(
                    "no approved chunks are available for SFT candidate generation"
                )
            vision_required_pages = {
                row["page_number"]
                for row in connection.execute(
                    "SELECT page_number FROM document_content_classifications WHERE "
                    "document_source_id=? AND vision_required=1",
                    (document["id"],),
                ).fetchall()
            }
            blocked_vision_required: list[dict[str, Any]] = []
            if vision_required_pages:
                eligible_chunks = []
                for chunk in chunks:
                    if (chunk["page_number"] or 1) in vision_required_pages:
                        blocked_vision_required.append(
                            {
                                "chunk_public_id": chunk["public_id"],
                                "page_number": chunk["page_number"],
                                "content_classification": "image_without_usable_text",
                                "review_status": "vision_required",
                                "blocking_reason": (
                                    "this page's meaning depends on image content that "
                                    "text-only extraction cannot recover -- blocked from "
                                    "text-only SFT generation"
                                ),
                            }
                        )
                    else:
                        eligible_chunks.append(chunk)
                chunks = eligible_chunks
            if not chunks:
                raise ValidationError(
                    "every approved chunk for this document is on a vision_required page "
                    "-- no text-only SFT generation is possible without a vision model"
                )
            created: list[str] = []
            created += self._generate_standalone(
                connection, document, chunks, rights_status, max_candidates - len(created)
            )
            created += self._generate_pairs(
                connection, document, chunks, rights_status, max_candidates - len(created)
            )
            created += self._generate_summaries(
                connection, document, chunks, rights_status, max_candidates - len(created)
            )
            created += self._generate_math_reasoning(
                connection, document, chunks, rights_status, max_candidates - len(created)
            )
            created += self._generate_spelling_corrections(
                connection, document, rights_status, max_candidates - len(created)
            )
            audit(
                connection, "document_sft_candidates_generated", admin_id, document_public_id,
                candidate_count=len(created), rights_status=rights_status,
                vision_blocked_count=len(blocked_vision_required),
            )
        result = self.list_candidates(document_public_id)
        result["vision_blocked"] = blocked_vision_required
        return result

    def list_candidates(
        self,
        document_public_id: str,
        page: int = 1,
        page_size: int = 50,
        quality_status: str | None = None,
        task: str | None = None,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            clauses = ["document_source_id=?"]
            params: list[Any] = [document["id"]]
            if quality_status:
                clauses.append("quality_status=?")
                params.append(quality_status)
            if task:
                clauses.append("task=?")
                params.append(task)
            where = " AND ".join(clauses)
            total = connection.execute(
                f"SELECT COUNT(*) FROM document_sft_candidates WHERE {where}", params
            ).fetchone()[0]
            offset = (page - 1) * page_size
            rows = connection.execute(
                f"SELECT * FROM document_sft_candidates WHERE {where} "
                "ORDER BY source_page_start,id LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            ).fetchall()
        items = []
        for row in rows:
            item = decode(row, _CANDIDATE_JSON)
            item["source_id"] = row["public_id"]
            item["source_document_id"] = document_public_id
            items.append(item)
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    def summary(self, document_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            rows = connection.execute(
                "SELECT task,quality_status,COUNT(*) count FROM document_sft_candidates "
                "WHERE document_source_id=? GROUP BY task,quality_status",
                (document["id"],),
            ).fetchall()
        by_task: dict[str, int] = {}
        by_status: dict[str, int] = {}
        total = 0
        for row in rows:
            by_task[row["task"]] = by_task.get(row["task"], 0) + row["count"]
            status = row["quality_status"]
            by_status[status] = by_status.get(status, 0) + row["count"]
            total += row["count"]
        return {
            "document_public_id": document_public_id,
            "total_candidates": total,
            "by_task": by_task,
            "by_quality_status": by_status,
            "approved_count": by_status.get("approved", 0),
        }

    def review(
        self,
        document_public_id: str,
        candidate_public_id: str,
        payload: SftCandidateReviewAction,
        admin_id: str,
    ) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            candidate = self.repository.sft_candidate(
                connection, document["id"], candidate_public_id
            )
            if candidate["quality_status"] in ("approved", "rejected"):
                raise ValidationError(
                    "this SFT candidate has already reached a final review decision"
                )
            if candidate["rights_status"] != "verified" and payload.action == "approve":
                raise ValidationError(
                    "a candidate without verified rights status cannot be approved"
                )
            status_by_action = {
                "approve": "approved",
                "reject": "rejected",
                "edit": "pending_review",
                "needs_correction": "needs_correction",
            }
            instruction = payload.edited_instruction or candidate["instruction"]
            context = (
                candidate["context"]
                if payload.edited_context is None
                else payload.edited_context
            )
            response = payload.edited_response or candidate["response"]
            connection.execute(
                "UPDATE document_sft_candidates SET instruction=?,context=?,response=?,"
                "quality_status=?,updated_at=? WHERE id=?",
                (
                    instruction, context, response, status_by_action[payload.action], now(),
                    candidate["id"],
                ),
            )
            connection.execute(
                """INSERT INTO document_sft_candidate_reviews(
                    public_id,candidate_id,action,actor_reference,notes
                ) VALUES (?,?,?,?,?)""",
                (str(uuid4()), candidate["id"], payload.action, admin_id, payload.notes),
            )
            audit(
                connection, "document_sft_candidate_reviewed", admin_id, document_public_id,
                candidate_public_id=candidate_public_id, action=payload.action,
            )
        return self.list_candidates(document_public_id)

    def bulk_approve(
        self, document_public_id: str, payload: SftBulkApprovalRequest, admin_id: str
    ) -> dict[str, Any]:
        if len(payload.candidate_public_ids) > self.settings.document_sft_bulk_approval_max_items:
            raise ValidationError(
                "bulk approval exceeds the maximum allowed batch size for this operation"
            )
        with self.repository.transaction() as connection:
            document = self.repository.document(connection, document_public_id)
            approved: list[str] = []
            blocked: list[dict[str, str]] = []
            for candidate_public_id in payload.candidate_public_ids:
                candidate = self.repository.sft_candidate(
                    connection, document["id"], candidate_public_id
                )
                if candidate["quality_status"] != "pending_review":
                    blocked.append(
                        {
                            "candidate_public_id": candidate_public_id,
                            "reason": "not_low_risk_pending",
                        }
                    )
                    continue
                if candidate["rights_status"] != "verified":
                    blocked.append(
                        {
                            "candidate_public_id": candidate_public_id,
                            "reason": "rights_not_verified",
                        }
                    )
                    continue
                if candidate["generation_method"] not in _LOW_RISK_GENERATION_METHODS:
                    blocked.append(
                        {
                            "candidate_public_id": candidate_public_id,
                            "reason": "not_low_risk_generation_method",
                        }
                    )
                    continue
                connection.execute(
                    "UPDATE document_sft_candidates SET quality_status='approved',updated_at=? "
                    "WHERE id=?",
                    (now(), candidate["id"]),
                )
                connection.execute(
                    """INSERT INTO document_sft_candidate_reviews(
                        public_id,candidate_id,action,actor_reference,notes
                    ) VALUES (?,?,?,?,?)""",
                    (str(uuid4()), candidate["id"], "approve", admin_id, "bulk approval"),
                )
                approved.append(candidate_public_id)
            audit(
                connection, "document_sft_candidates_bulk_approved", admin_id, document_public_id,
                approved_count=len(approved), blocked_count=len(blocked),
            )
        return {"approved": approved, "blocked": blocked}
