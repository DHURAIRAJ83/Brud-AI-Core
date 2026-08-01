"""Positive/negative coverage for the finalization-pass SFT generators:
chunk-pair generators (fact_answer, instruction_following, Tamil_to_English,
English_to_Tamil, Tanglish_input_to_Tamil), summarization, spelling_correction
(from reviewed Tamil quality issues), and calculator-verified basic_math_reasoning."""

from pathlib import Path

import fitz
import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.data_sources import DataSourceRepository
from backend.models.data_sources import DataSourceCreate, SourceRightsUpsert
from backend.models.documents import (
    ProcessRequest,
    SftCandidateGenerationRequest,
    TamilQualityReviewAction,
)
from backend.services.data_source_service import SourceRegistryService, SourceRightsService
from backend.services.document_service import DocumentService
from backend.services.document_sft_candidate_service import DocumentSftCandidateGenerationService
from backend.services.document_tamil_quality_service import DocumentTamilQualityService
from backend.services.document_workspace_service import (
    DocumentPageReviewService,
    PDFResearchWorkspaceService,
)
from backend.services.semantic_chunk_service import SemanticChunkReviewService, SemanticChunkService

ADMIN_ID = "00000000-0000-0000-0000-000000000077"


def make_pdf(*texts: str) -> bytes:
    pdf = fitz.open()
    for text in texts:
        page = pdf.new_page()
        page.insert_text((72, 72), text)
    value = pdf.tobytes()
    pdf.close()
    return value


class FakeUploadFile:
    def __init__(self, filename: str, content: bytes, content_type: str = "application/pdf"):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._offset = 0

    async def read(self, size: int) -> bytes:
        chunk = self._content[self._offset : self._offset + size]
        self._offset += size
        return chunk


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    database_path = tmp_path / "generators.db"
    initialize_database(database_path)
    return Settings(
        database_path=database_path,
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )


@pytest.fixture
def services(settings: Settings):
    return {
        "documents": DocumentService(settings),
        "workspace": PDFResearchWorkspaceService(settings),
        "review": DocumentPageReviewService(settings),
        "chunks": SemanticChunkService(settings),
        "chunk_review": SemanticChunkReviewService(settings),
        "sft": DocumentSftCandidateGenerationService(settings),
        "tamil_quality": DocumentTamilQualityService(settings),
        "source_registry": SourceRegistryService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
        "rights": SourceRightsService(
            DataSourceRepository(settings.resolved_database_path), settings
        ),
    }


async def _approved_document(services, text="placeholder"):
    upload_file = FakeUploadFile("sample.pdf", make_pdf(text))
    document = await services["documents"].upload(upload_file, "embedded_text", "en", ADMIN_ID)
    services["documents"].process(
        document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID
    )
    source = services["source_registry"].create(
        DataSourceCreate(
            source_code=f"SRC-GEN-{document['public_id'][:8]}", title="s",
            source_type="document_derived",
        ),
        ADMIN_ID,
    )
    services["rights"].upsert(
        source["public_id"],
        SourceRightsUpsert(rights_status="public_domain", training_use_allowed=True),
        ADMIN_ID,
    )
    services["workspace"].link_source(document["public_id"], source["public_id"], ADMIN_ID)
    services["review"].approve(document["public_id"], 1, ADMIN_ID)
    return document["public_id"]


async def _approved_chunk_pair(services, document_public_id, first_type, first_text,
                                first_language, second_type, second_text, second_language):
    first = services["chunks"].create_manual_chunk(
        document_public_id, text=first_text, chunk_type=first_type, page_number=1,
        language=first_language, admin_id=ADMIN_ID,
    )
    second = services["chunks"].create_manual_chunk(
        document_public_id, text=second_text, chunk_type=second_type, page_number=1,
        language=second_language, admin_id=ADMIN_ID,
    )
    for chunk in (first, second):
        services["chunk_review"].submit_review(chunk["public_id"], ADMIN_ID)
        services["chunk_review"].approve(chunk["public_id"], ADMIN_ID)
    return first, second


class TestChunkPairGenerators:
    @pytest.mark.anyio
    async def test_fact_answer_generated_from_adjacent_question_answer_chunks(self, services):
        document_public_id = await _approved_document(services)
        await _approved_chunk_pair(
            services, document_public_id,
            "question", "What is the capital of Tamil Nadu?", "en",
            "answer", "Chennai is the capital of Tamil Nadu.", "en",
        )
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        fact_answers = [item for item in result["items"] if item["task"] == "fact_answer"]
        assert len(fact_answers) == 1
        assert fact_answers[0]["generation_method"] == "chunk_pair_v1"
        assert fact_answers[0]["response"] == "Chennai is the capital of Tamil Nadu."

    @pytest.mark.anyio
    async def test_no_fact_answer_without_an_answer_sibling(self, services):
        document_public_id = await _approved_document(services)
        services["chunks"].create_manual_chunk(
            document_public_id, text="What is the capital of Tamil Nadu?",
            chunk_type="question", page_number=1, language="en", admin_id=ADMIN_ID,
        )
        chunk = services["chunks"].list_chunks(document_public_id)["items"][0]
        services["chunk_review"].submit_review(chunk["public_id"], ADMIN_ID)
        services["chunk_review"].approve(chunk["public_id"], ADMIN_ID)
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        assert not [item for item in result["items"] if item["task"] == "fact_answer"]

    @pytest.mark.anyio
    async def test_instruction_following_generated_from_instruction_response_pair(self, services):
        document_public_id = await _approved_document(services)
        await _approved_chunk_pair(
            services, document_public_id,
            "instruction", "List the primary colors.", "en",
            "response", "The primary colors are red, blue, and yellow.", "en",
        )
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        matches = [item for item in result["items"] if item["task"] == "instruction_following"]
        assert len(matches) == 1

    @pytest.mark.anyio
    async def test_tamil_to_english_generated_from_translation_pair(self, services):
        document_public_id = await _approved_document(services)
        await _approved_chunk_pair(
            services, document_public_id,
            "translation_source", "வணக்கம்", "ta",
            "translation_target", "Hello", "en",
        )
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        matches = [item for item in result["items"] if item["task"] == "Tamil_to_English"]
        assert len(matches) == 1
        assert matches[0]["instruction"] == "வணக்கம்"
        assert matches[0]["response"] == "Hello"

    @pytest.mark.anyio
    async def test_english_to_tamil_generated_from_reverse_translation_pair(self, services):
        document_public_id = await _approved_document(services)
        await _approved_chunk_pair(
            services, document_public_id,
            "translation_source", "Hello", "en",
            "translation_target", "வணக்கம்", "ta",
        )
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        matches = [item for item in result["items"] if item["task"] == "English_to_Tamil"]
        assert len(matches) == 1

    @pytest.mark.anyio
    async def test_no_translation_candidate_for_a_non_ta_en_pair(self, services):
        document_public_id = await _approved_document(services)
        await _approved_chunk_pair(
            services, document_public_id,
            "translation_source", "Bonjour", "unknown",
            "translation_target", "Hello", "en",
        )
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        assert not [
            item for item in result["items"]
            if item["task"] in ("Tamil_to_English", "English_to_Tamil")
        ]

    @pytest.mark.anyio
    async def test_tanglish_input_to_tamil_generated_from_tanglish_pair(self, services):
        document_public_id = await _approved_document(services)
        await _approved_chunk_pair(
            services, document_public_id,
            "tanglish_text", "vanakkam eppadi irukkinga", "tgl",
            "tamil_text", "வணக்கம் எப்படி இருக்கீங்க", "ta",
        )
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        matches = [item for item in result["items"] if item["task"] == "Tanglish_input_to_Tamil"]
        assert len(matches) == 1
        assert matches[0]["output_language"] == "ta"


class TestSummarization:
    @pytest.mark.anyio
    async def test_summarization_generated_for_a_long_paragraph_chunk(self, services):
        document_public_id = await _approved_document(services)
        long_text = "This is the first sentence of a long passage. " + "More detail follows. " * 30
        chunk = services["chunks"].create_manual_chunk(
            document_public_id, text=long_text, chunk_type="paragraph", page_number=1,
            language="en", admin_id=ADMIN_ID,
        )
        services["chunk_review"].submit_review(chunk["public_id"], ADMIN_ID)
        services["chunk_review"].approve(chunk["public_id"], ADMIN_ID)
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        matches = [item for item in result["items"] if item["task"] == "summarization"]
        assert len(matches) == 1
        assert matches[0]["response"] == "This is the first sentence of a long passage."

    @pytest.mark.anyio
    async def test_no_summarization_for_a_short_paragraph_chunk(self, services):
        document_public_id = await _approved_document(services)
        chunk = services["chunks"].create_manual_chunk(
            document_public_id, text="A short passage.", chunk_type="paragraph", page_number=1,
            language="en", admin_id=ADMIN_ID,
        )
        services["chunk_review"].submit_review(chunk["public_id"], ADMIN_ID)
        services["chunk_review"].approve(chunk["public_id"], ADMIN_ID)
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        assert not [item for item in result["items"] if item["task"] == "summarization"]


class TestBasicMathReasoning:
    @pytest.mark.anyio
    async def test_math_candidate_generated_for_a_correct_stated_answer(self, services):
        document_public_id = await _approved_document(services)
        chunk = services["chunks"].create_manual_chunk(
            document_public_id, text="We know that 12 + 30 = 42 in this example.",
            chunk_type="paragraph", page_number=1, language="en", admin_id=ADMIN_ID,
        )
        services["chunk_review"].submit_review(chunk["public_id"], ADMIN_ID)
        services["chunk_review"].approve(chunk["public_id"], ADMIN_ID)
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        matches = [item for item in result["items"] if item["task"] == "basic_math_reasoning"]
        assert len(matches) == 1
        assert matches[0]["response"] == "42"

    @pytest.mark.anyio
    async def test_no_math_candidate_for_an_incorrect_stated_answer(self, services):
        document_public_id = await _approved_document(services)
        chunk = services["chunks"].create_manual_chunk(
            document_public_id, text="The book incorrectly claims 12 + 30 = 99.",
            chunk_type="paragraph", page_number=1, language="en", admin_id=ADMIN_ID,
        )
        services["chunk_review"].submit_review(chunk["public_id"], ADMIN_ID)
        services["chunk_review"].approve(chunk["public_id"], ADMIN_ID)
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        assert not [item for item in result["items"] if item["task"] == "basic_math_reasoning"]


async def _approved_two_page_document(services):
    pdf_bytes = make_pdf("placeholder page one", "placeholder page two")
    upload_file = FakeUploadFile("sample.pdf", pdf_bytes)
    document = await services["documents"].upload(upload_file, "embedded_text", "en", ADMIN_ID)
    services["documents"].process(
        document["public_id"], ProcessRequest(strategy="embedded_text"), ADMIN_ID
    )
    source = services["source_registry"].create(
        DataSourceCreate(
            source_code=f"SRC-GEN2-{document['public_id'][:8]}", title="s",
            source_type="document_derived",
        ),
        ADMIN_ID,
    )
    services["rights"].upsert(
        source["public_id"],
        SourceRightsUpsert(rights_status="public_domain", training_use_allowed=True),
        ADMIN_ID,
    )
    services["workspace"].link_source(document["public_id"], source["public_id"], ADMIN_ID)
    services["review"].approve(document["public_id"], 1, ADMIN_ID)
    services["review"].approve(document["public_id"], 2, ADMIN_ID)
    return document["public_id"]


class TestSpellingCorrection:
    @pytest.mark.anyio
    async def test_spelling_correction_generated_from_an_accepted_tamil_issue(self, services):
        # Two pages: page 1 carries the Tamil artefact (its correction flow
        # reopens page 1's review status); page 2 stays approved and
        # untouched so generate() has the required approved-chunk
        # precondition for a document that otherwise has zero chunks.
        document_public_id = await _approved_two_page_document(services)
        chunk = services["chunks"].create_manual_chunk(
            document_public_id, text="unrelated definition text",
            chunk_type="definition", page_number=2, language="en", admin_id=ADMIN_ID,
        )
        services["chunk_review"].submit_review(chunk["public_id"], ADMIN_ID)
        services["chunk_review"].approve(chunk["public_id"], ADMIN_ID)

        artefact_text = "தமிழ் வாசகம் ஒொ்டு தவறு"
        services["documents"].edit_page(document_public_id, 1, artefact_text, ADMIN_ID)
        services["tamil_quality"].detect(document_public_id, ADMIN_ID)
        issues = services["tamil_quality"].list_issues(
            document_public_id, issue_type="ocr_character_substitution"
        )
        issue = issues["items"][0]
        services["tamil_quality"].review(
            document_public_id, issue["public_id"],
            TamilQualityReviewAction(action="accept"), ADMIN_ID,
        )
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        matches = [item for item in result["items"] if item["task"] == "spelling_correction"]
        assert len(matches) == 1
        assert matches[0]["generation_method"] == "reviewed_correction_v1"

    @pytest.mark.anyio
    async def test_no_spelling_correction_from_an_unreviewed_issue(self, services):
        document_public_id = await _approved_document(services, text="placeholder")
        artefact_text = "தமிழ் வாசகம் ஒொ்டு தவறு"
        services["documents"].edit_page(document_public_id, 1, artefact_text, ADMIN_ID)
        services["tamil_quality"].detect(document_public_id, ADMIN_ID)
        # generate() requires at least one approved chunk before it will run
        # any pass -- add an unrelated one so this test isolates "no
        # unreviewed-issue leakage" rather than "generation refused outright".
        chunk = services["chunks"].create_manual_chunk(
            document_public_id, text="unrelated definition text", chunk_type="definition",
            page_number=1, language="en", admin_id=ADMIN_ID,
        )
        services["chunk_review"].submit_review(chunk["public_id"], ADMIN_ID)
        services["chunk_review"].approve(chunk["public_id"], ADMIN_ID)
        result = services["sft"].generate(
            document_public_id, SftCandidateGenerationRequest(), ADMIN_ID
        )
        assert not [item for item in result["items"] if item["task"] == "spelling_correction"]
