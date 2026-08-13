"""MB-13: Brud Mini Brain Language Intelligence & Dataset
Normalization Center -- the orchestration layer for the 12-stage
language-scan-to-certification workflow described in the MB-13 task
spec.

This service NEVER edits a dataset record, NEVER starts training,
NEVER deploys, and NEVER calls RAG Sandbox -- confirmed by structural/
safety tests reading this file's own source. It composes existing,
unmodified systems through their public methods only:

- `DatasetService` (Dataset Studio's own service) -- ONLY
  `.get_source()`/`.list_records()`, the same bounded-pagination
  pattern MB-05/MB-05.1 already established (100 records/page, capped
  at `MAX_RECORDS_PER_ANALYSIS`). MB-13 never calls a write method.
- `MiniBrainDatasetIntelligenceService` (MB-05) -- ONLY `.language()`,
  for the dataset-level language distribution the Language Scan stage
  reports on.
- `DocumentTamilCorrectionRegistryService` (Task Finalization) --
  ONLY `.list_rules(status="active")`, the existing admin-curated Tamil
  correction-rule registry. MB-13 never creates or transitions a rule.
- `ExternalDatasetDuplicateService` (Phase 12) -- ONLY
  `.group_normalized_duplicates()`, reused unchanged exactly as MB-09/
  MB-10/MB-11 already use it.
- The twelve pure `core_model.mini_brain.language_intelligence`
  modules, which themselves reuse `core_model.corpus.language_
  detection`, `core_model.corpus.unicode_normalization`, `core_model.
  corpus.tamil_normalization`, `core_model.mini_brain.quality.
  tamil_fluency_validator`, `core_model.mini_brain.prompting.
  tanglish_normalizer`, and `core_model.admin_assistant.localization.
  tanglish_renderer` unchanged -- never a second Unicode/Tamil-script/
  Tanglish implementation.

Every irreversible step (a dataset actually being edited, corrected,
or replaced) requires an explicit prior admin decision recorded on the
session; nothing here proceeds automatically, and nothing here ever
applies a suggested correction to a real record.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from backend.core.config import Settings
from backend.database.repositories.base import ValidationError
from backend.database.repositories.dataset_admin import DatasetAdminRepository
from backend.database.repositories.mini_brain_language_intelligence import (
    MiniBrainLanguageIntelligenceRepository,
    public_session_row,
)
from backend.services.dataset_service import DatasetService
from backend.services.dataset_sample_duplicate_service import ExternalDatasetDuplicateService
from backend.services.document_tamil_correction_registry_service import (
    DocumentTamilCorrectionRegistryService,
)
from backend.services.mini_brain_dataset_intelligence_service import (
    MiniBrainDatasetIntelligenceService,
)
from core_model.corpus.tamil_normalization import normalize_tamil_text
from core_model.mini_brain.language_intelligence.language_dataset_generator import (
    generate_language_drafts,
)
from core_model.mini_brain.language_intelligence.language_quality_engine import (
    score_language_quality,
)
from core_model.mini_brain.language_intelligence.language_report_generator import (
    generate_language_report,
)
from core_model.mini_brain.language_intelligence.ocr_correction_planner import (
    plan_ocr_corrections,
)
from core_model.mini_brain.language_intelligence.reverse_tanglish import generate_reverse_tanglish
from core_model.mini_brain.language_intelligence.sentence_quality_analyzer import (
    analyze_sentence_quality,
)
from core_model.mini_brain.language_intelligence.tamil_character_validator import (
    validate_tamil_characters,
)
from core_model.mini_brain.language_intelligence.tamil_grammar_analyzer import analyze_grammar
from core_model.mini_brain.language_intelligence.tamil_spell_analyzer import analyze_spelling
from core_model.mini_brain.language_intelligence.tanglish_intelligence import analyze_tanglish
from core_model.mini_brain.language_intelligence.translation_intelligence import analyze_translation
from core_model.mini_brain.language_intelligence.unicode_validator import analyze_unicode

PAGE_SIZE = 100
MAX_RECORDS_PER_ANALYSIS = 500
MAX_DRAFT_SAMPLE_RECORDS = 20
ADMIN_DECISIONS = {"approve", "reject", "request_fix", "archive"}
ADMIN_STATUS_MAP = {
    "approve": "admin_approved", "reject": "admin_rejected", "request_fix": "admin_requested_fix",
    "archive": "admin_archived",
}


def _now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")


class MiniBrainLanguageIntelligenceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repository = MiniBrainLanguageIntelligenceRepository(settings.resolved_database_path)

        self.dataset_service = DatasetService(DatasetAdminRepository(settings.resolved_database_path))
        self.dataset_intelligence = MiniBrainDatasetIntelligenceService(self.dataset_service)
        self.correction_registry = DocumentTamilCorrectionRegistryService(settings)
        self.duplicate_service = ExternalDatasetDuplicateService()

    # -- helpers -------------------------------------------------------

    def _fetch_records(self, source_public_id: str) -> tuple[list[dict[str, Any]], bool]:
        records: list[dict[str, Any]] = []
        page = 1
        total = None
        while len(records) < MAX_RECORDS_PER_ANALYSIS:
            result = self.dataset_service.list_records({"source": source_public_id}, page, PAGE_SIZE)
            records.extend(result.items)
            total = result.total
            if len(result.items) < PAGE_SIZE or len(records) >= total:
                break
            page += 1
        truncated = total is not None and total > len(records)
        return records[:MAX_RECORDS_PER_ANALYSIS], truncated

    @staticmethod
    def _record_text(record: dict[str, Any]) -> str:
        parts = [record.get("instruction"), record.get("input_text"), record.get("output_text")]
        return "\n".join(part for part in parts if part)

    def _event(
        self, connection, language_session_id: int, event_type: str, *, stage: str | None = None,
        message: str = "", metadata: dict[str, Any] | None = None,
    ) -> None:
        self.repository.record_event(
            connection, language_session_id=language_session_id, event_type=event_type,
            stage=stage, message=message, metadata=metadata,
        )

    def session(self, session_public_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            return public_session_row(self.repository.session(connection, session_public_id))

    def list_sessions(self, *, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            rows = self.repository.list_sessions(connection, limit=limit, offset=offset)
        return {"items": [public_session_row(row) for row in rows]}

    def events(self, session_public_id: str, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            rows = self.repository.list_events(
                connection, language_session_id=session_row["id"], limit=limit, offset=offset
            )
        return {"items": [dict(row) for row in rows]}

    # -- stage 1: session creation --------------------------------------

    def create_session(self, *, dataset_source_public_id: str, admin_id: str) -> dict[str, Any]:
        with self.repository.transaction() as connection:
            public_id = self.repository.create_session(
                connection, dataset_source_public_id=dataset_source_public_id, created_by_admin_public_id=admin_id,
            )
            session_row = self.repository.session(connection, public_id)
            self._event(
                connection, session_row["id"], "session_created", stage="language_scan",
                message=f"language intelligence cycle created for dataset source {dataset_source_public_id}",
            )
            return public_session_row(self.repository.session(connection, public_id))

    # -- stage 1: language scan ------------------------------------------

    def run_language_scan_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "language_scan":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'language_scan'")

        source_id = session_data["dataset_source_public_id"]
        language_result = self.dataset_intelligence.language(source_id)
        percentages = language_result.get("distribution_percentages", {})
        dominant_language = max(percentages, key=percentages.get) if percentages else "unknown"

        scan_report = {
            "total_records": language_result.get("total_records", 0),
            "distribution_counts": language_result.get("distribution_counts", {}),
            "distribution_percentages": percentages,
            "dominant_language": dominant_language,
            "dominant_language_percent": round(percentages.get(dominant_language, 0.0), 1),
            "analysis_truncated": language_result.get("analysis_truncated", False),
        }

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"language_scan_report_json": scan_report, "stage": "unicode_validation"},
            )
            self._event(
                connection, session_row["id"], "language_scanned", stage="language_scan",
                message=f"dominant language: {dominant_language} ({scan_report['dominant_language_percent']}%)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 2: unicode validation --------------------------------------

    def run_unicode_validation_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "unicode_validation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'unicode_validation'")

        records, truncated = self._fetch_records(session_data["dataset_source_public_id"])
        texts = [self._record_text(r) for r in records]

        unicode_result = analyze_unicode(texts=texts)
        character_result = validate_tamil_characters(texts=texts)
        unicode_report = {**unicode_result, "character_validation": character_result, "analysis_truncated": truncated}

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"unicode_report_json": unicode_report, "stage": "spell_analysis"},
            )
            self._event(
                connection, session_row["id"], "unicode_validated", stage="unicode_validation",
                message=f"unicode score {unicode_result['unicode_score']}, character score {character_result['character_score']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 3: spell analysis ------------------------------------------

    def run_spell_analysis_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "spell_analysis":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'spell_analysis'")

        records, _ = self._fetch_records(session_data["dataset_source_public_id"])
        texts = [self._record_text(r) for r in records]
        active_rules = self.correction_registry.list_rules(status="active", page_size=100)["items"]

        spell_report = analyze_spelling(texts=texts, active_rules=active_rules)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"spell_report_json": spell_report, "stage": "grammar_analysis"},
            )
            self._event(
                connection, session_row["id"], "spelling_analyzed", stage="spell_analysis",
                message=f"spell score {spell_report['spell_score']}, {spell_report['match_count']} match(es) against {spell_report['rules_checked']} active rule(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 4: grammar analysis (+ sentence quality) ----------------------

    def run_grammar_analysis_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "grammar_analysis":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'grammar_analysis'")

        records, _ = self._fetch_records(session_data["dataset_source_public_id"])
        texts = [self._record_text(r) for r in records]

        grammar_report = analyze_grammar(texts=texts)

        duplicate_records = [
            {"public_id": r.get("public_id"), "normalized_content": " ".join(t.lower().split())}
            for r, t in zip(records, texts)
        ]
        duplicate_groups = self.duplicate_service.group_normalized_duplicates(duplicate_records)
        sentence_quality_report = analyze_sentence_quality(texts=texts, duplicate_groups=duplicate_groups)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {
                    "grammar_report_json": grammar_report, "sentence_quality_report_json": sentence_quality_report,
                    "stage": "ocr_analysis",
                },
            )
            self._event(
                connection, session_row["id"], "grammar_analyzed", stage="grammar_analysis",
                message=f"grammar confidence {grammar_report['grammar_confidence']}, naturalness {sentence_quality_report['naturalness_score']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 5: OCR analysis -----------------------------------------------

    def run_ocr_analysis_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "ocr_analysis":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'ocr_analysis'")

        records, _ = self._fetch_records(session_data["dataset_source_public_id"])
        texts = [self._record_text(r) for r in records]
        normalization_results = [normalize_tamil_text(t) for t in texts]

        ocr_report = plan_ocr_corrections(texts=texts, normalization_results=normalization_results)

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"ocr_report_json": ocr_report, "stage": "tanglish_analysis"},
            )
            self._event(
                connection, session_row["id"], "ocr_analyzed", stage="ocr_analysis",
                message=f"ocr score {ocr_report['ocr_score']}, {ocr_report['possible_correction_count']} possible correction(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 6: Tanglish analysis (forward + reverse) ------------------------

    def run_tanglish_analysis_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "tanglish_analysis":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'tanglish_analysis'")

        records, _ = self._fetch_records(session_data["dataset_source_public_id"])
        texts = [self._record_text(r) for r in records]

        forward = analyze_tanglish(texts=texts)
        reverse = generate_reverse_tanglish(texts=texts)
        tanglish_report = {"forward": forward, "reverse": reverse}

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"tanglish_report_json": tanglish_report, "stage": "translation_analysis"},
            )
            self._event(
                connection, session_row["id"], "tanglish_analyzed", stage="tanglish_analysis",
                message=f"tanglish confidence {forward['confidence_score']}, {reverse['sample_count']} reverse sample(s)",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 7: translation analysis (pair validator, never a translator) -------

    def run_translation_analysis_stage(
        self, session_public_id: str, *, admin_id: str, pairs: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "translation_analysis":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'translation_analysis'")

        translation_report = analyze_translation(pairs=pairs or [])

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"translation_report_json": translation_report, "stage": "dataset_draft_generation"},
            )
            self._event(
                connection, session_row["id"], "translation_analyzed", stage="translation_analysis",
                message=f"{translation_report['pairs_analyzed']} pair(s) analyzed",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 8: dataset draft generation ------------------------------------

    def run_dataset_draft_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "dataset_draft_generation":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'dataset_draft_generation'")

        records, _ = self._fetch_records(session_data["dataset_source_public_id"])
        texts = [self._record_text(r) for r in records]
        dominant_language = session_data["language_scan_report"]["dominant_language"]

        draft_report = generate_language_drafts(
            dominant_language=dominant_language, sample_texts=texts[:MAX_DRAFT_SAMPLE_RECORDS],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"dataset_draft_report_json": draft_report, "stage": "language_quality_score"},
            )
            self._event(
                connection, session_row["id"], "dataset_draft_generated", stage="dataset_draft_generation",
                message=f"applicable={draft_report['applicable']} -- verified=False, Dataset Studio remains the only place a dataset is actually written",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 9: language quality score --------------------------------------

    def run_quality_score_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "language_quality_score":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'language_quality_score'")

        unicode_report = session_data["unicode_report"]
        quality_report = score_language_quality(
            unicode_score=unicode_report["unicode_score"],
            character_score=unicode_report["character_validation"]["character_score"],
            spell_score=session_data["spell_report"]["spell_score"],
            grammar_confidence=session_data["grammar_report"]["grammar_confidence"],
            naturalness_score=session_data["sentence_quality_report"]["naturalness_score"],
            ocr_score=session_data["ocr_report"]["ocr_score"],
            tanglish_confidence=session_data["tanglish_report"]["forward"]["confidence_score"],
            translation_score=session_data["translation_report"]["translation_quality_score"],
            dominant_language_percent=session_data["language_scan_report"]["dominant_language_percent"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"quality_score_report_json": quality_report, "stage": "language_report"},
            )
            self._event(
                connection, session_row["id"], "quality_scored", stage="language_quality_score",
                message=f"overall language quality {quality_report['overall_language_quality']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 10: language report --------------------------------------------

    def generate_report_stage(self, session_public_id: str, *, admin_id: str) -> dict[str, Any]:
        del admin_id
        session_data = self.session(session_public_id)
        if session_data["stage"] != "language_report":
            raise ValidationError(f"session is at stage '{session_data['stage']}', not 'language_report'")

        report = generate_language_report(
            session_public_id=session_public_id, dataset_source_public_id=session_data["dataset_source_public_id"],
            unicode_report=session_data["unicode_report"],
            character_report=session_data["unicode_report"]["character_validation"],
            spell_report=session_data["spell_report"], ocr_report=session_data["ocr_report"],
            sentence_quality_report=session_data["sentence_quality_report"],
            dataset_draft_report=session_data["dataset_draft_report"],
            quality_score_report=session_data["quality_score_report"],
        )

        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            self.repository.update_session(
                connection, session_public_id,
                {"language_report_json": report, "stage": "awaiting_admin_review"},
            )
            self._event(
                connection, session_row["id"], "language_report_generated", stage="language_report",
                message=f"status={report['status']}, ready={report['ready']}",
            )
            return public_session_row(self.repository.session(connection, session_public_id))

    # -- stage 11/12: admin review -> certified -------------------------------------

    def admin_review(self, session_public_id: str, *, decision: str, admin_id: str) -> dict[str, Any]:
        if decision not in ADMIN_DECISIONS:
            raise ValidationError(f"decision must be one of {sorted(ADMIN_DECISIONS)}")
        with self.repository.transaction() as connection:
            session_row = self.repository.session(connection, session_public_id)
            if session_row["stage"] != "awaiting_admin_review":
                raise ValidationError(f"session is at stage '{session_row['stage']}', not 'awaiting_admin_review'")

            fields: dict[str, Any] = {
                "admin_decision": decision, "admin_decided_by": admin_id, "admin_decided_at": _now(),
                "status": ADMIN_STATUS_MAP[decision], "stage": "certified" if decision == "approve" else "closed",
            }
            self.repository.update_session(connection, session_public_id, fields)
            self._event(
                connection, session_row["id"], f"language_review_{decision}", stage="awaiting_admin_review",
                message=(
                    f"admin decided '{decision}' on the language report -- no dataset record was edited "
                    "by this service; Dataset Studio remains the only place that happens. A 'certified' "
                    "session is eligible for MB-11 Dataset Evolution, RAG Sandbox, and MB-06 Learning "
                    "Supervisor -- this service never submits it to any of them automatically"
                ),
                metadata={"admin_id": admin_id},
            )
            return public_session_row(self.repository.session(connection, session_public_id))


__all__ = ["MiniBrainLanguageIntelligenceService"]
