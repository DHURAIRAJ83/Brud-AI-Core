"""Phase 16 RAG knowledge retrieval, hybrid search, citation grounding,
and admin RAG Chat Lab APIs.

Every mutation requires admin authentication and CSRF, matching the
Phase 9-15 convention. The public chatbot route is untouched by this
module -- there is no public-facing RAG endpoint here.
"""

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.rag import RagRepository
from backend.models.rag import (
    ChunkSetCreate,
    EmbeddingModelCreate,
    EmbeddingRunCreate,
    EvaluationFixtureCreate,
    EvaluationRunCreate,
    EvaluationSuiteCreate,
    GroundedAnswerRequest,
    IndexComparisonRequest,
    KeywordIndexCreate,
    KnowledgeSourceCreate,
    KnowledgeSourcePatch,
    KnowledgeSpaceCreate,
    KnowledgeSpacePatch,
    RagSessionCreate,
    RagSessionMessageCreate,
    RetrievalProfileCreate,
    RetrievalProfilePatch,
    RetrieveRequest,
    VectorIndexCreate,
)
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.model_assignment_service import ModelAssignmentService
from backend.services.rag_evaluation_service import RagEvaluationService
from backend.services.rag_generation_service import RagGenerationService
from backend.services.rag_ingestion_service import RagIngestionService
from backend.services.rag_retrieval_service import RagRetrievalService

router = APIRouter(
    prefix="/admin/rag",
    tags=["admin-rag"],
    dependencies=[Depends(require_admin)],
)


def rag_repository(settings) -> RagRepository:
    return RagRepository(settings.resolved_database_path)


def ingestion_service(settings) -> RagIngestionService:
    return RagIngestionService(rag_repository(settings), settings)


def retrieval_service(settings) -> RagRetrievalService:
    return RagRetrievalService(rag_repository(settings), settings)


def generation_service(settings) -> RagGenerationService:
    inference_repository = InferenceRuntimeRepository(settings.resolved_database_path)
    release_repository = ModelReleaseRepository(settings.resolved_database_path)
    runtime_service = InferenceRuntimeService(inference_repository, release_repository, settings)
    assignment_service = ModelAssignmentService(
        inference_repository, release_repository, runtime_service, settings
    )
    return RagGenerationService(
        rag_repository(settings),
        inference_repository,
        runtime_service,
        assignment_service,
        retrieval_service(settings),
        settings,
    )


def evaluation_service(settings) -> RagEvaluationService:
    return RagEvaluationService(
        rag_repository(settings),
        retrieval_service(settings),
        generation_service(settings),
        settings,
    )


# --- knowledge spaces -----------------------------------------------------


@router.get("/spaces")
async def spaces(settings: SettingsDependency):
    return ingestion_service(settings).list_spaces()


@router.post("/spaces")
async def create_space(
    payload: KnowledgeSpaceCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return ingestion_service(settings).create_space(payload, admin.admin.public_id)


@router.get("/spaces/{public_id}")
async def space(public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).get_space(public_id)


@router.patch("/spaces/{public_id}")
async def patch_space(
    public_id: str, payload: KnowledgeSpacePatch, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return ingestion_service(settings).patch_space(public_id, payload, admin.admin.public_id)


# --- knowledge sources -----------------------------------------------------


@router.get("/spaces/{space_public_id}/sources")
async def sources(space_public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).list_sources(space_public_id)


@router.post("/spaces/{space_public_id}/sources")
async def create_source(
    space_public_id: str, payload: KnowledgeSourceCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return ingestion_service(settings).create_source(
        space_public_id, payload, admin.admin.public_id
    )


@router.get("/sources/{public_id}")
async def source(public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).get_source(public_id)


@router.patch("/sources/{public_id}")
async def patch_source(
    public_id: str, payload: KnowledgeSourcePatch, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return ingestion_service(settings).patch_source(public_id, payload, admin.admin.public_id)


# --- source versions -----------------------------------------------------


@router.get("/sources/{source_public_id}/versions")
async def source_versions(source_public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).list_source_versions(source_public_id)


@router.post("/sources/{source_public_id}/versions")
async def create_source_version(
    source_public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return ingestion_service(settings).create_source_version(
        source_public_id, admin.admin.public_id
    )


@router.get("/versions/{public_id}")
async def source_version(public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).get_source_version(public_id)


@router.post("/versions/{public_id}/validate")
async def validate_source_version(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return ingestion_service(settings).validate_source_version(public_id, admin.admin.public_id)


# --- chunk sets -----------------------------------------------------


@router.get("/versions/{version_public_id}/chunk-sets")
async def chunk_sets(version_public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).list_chunk_sets(version_public_id)


@router.post("/versions/{version_public_id}/chunk-sets")
async def create_chunk_set(
    version_public_id: str, payload: ChunkSetCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return ingestion_service(settings).create_chunk_set(
        version_public_id, payload, admin.admin.public_id
    )


@router.get("/chunk-sets/{public_id}")
async def chunk_set(public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).get_chunk_set(public_id)


@router.get("/chunk-sets/{public_id}/chunks")
async def chunks(public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).list_chunks(public_id)


@router.post("/chunk-sets/{public_id}/validate")
async def validate_chunk_set(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return ingestion_service(settings).validate_chunk_set(public_id, admin.admin.public_id)


# --- embedding models -----------------------------------------------------


@router.get("/embedding-models")
async def embedding_models(settings: SettingsDependency):
    return ingestion_service(settings).list_embedding_models()


@router.post("/embedding-models")
async def create_embedding_model(
    payload: EmbeddingModelCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return ingestion_service(settings).create_embedding_model(payload, admin.admin.public_id)


# --- embedding runs -----------------------------------------------------


@router.post("/chunk-sets/{chunk_set_public_id}/embedding-runs")
async def create_embedding_run(
    chunk_set_public_id: str, payload: EmbeddingRunCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return ingestion_service(settings).create_embedding_run(
        chunk_set_public_id, payload, admin.admin.public_id
    )


@router.get("/embedding-runs/{public_id}")
async def embedding_run(public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).get_embedding_run(public_id)


@router.post("/embedding-runs/{public_id}/execute")
async def execute_embedding_run(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return ingestion_service(settings).execute_embedding_run(public_id, admin.admin.public_id)


@router.get("/embedding-runs/{public_id}/verify")
async def verify_embedding_run(public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).verify_embedding_run(public_id)


# --- vector indexes -----------------------------------------------------


@router.post("/embedding-runs/{embedding_run_public_id}/vector-index")
async def create_vector_index(
    embedding_run_public_id: str, payload: VectorIndexCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return ingestion_service(settings).create_vector_index(
        embedding_run_public_id, payload, admin.admin.public_id
    )


@router.get("/vector-indexes/{public_id}")
async def vector_index(public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).get_vector_index(public_id)


@router.post("/vector-indexes/{public_id}/build")
async def build_vector_index(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return ingestion_service(settings).build_vector_index(public_id, admin.admin.public_id)


@router.post("/vector-indexes/{public_id}/validate")
async def validate_vector_index(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return ingestion_service(settings).validate_vector_index(public_id, admin.admin.public_id)


@router.post("/vector-indexes/{public_id}/activate")
async def activate_vector_index(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return ingestion_service(settings).activate_vector_index(public_id, admin.admin.public_id)


# --- keyword indexes -----------------------------------------------------


@router.post("/chunk-sets/{chunk_set_public_id}/keyword-index")
async def create_keyword_index(
    chunk_set_public_id: str, payload: KeywordIndexCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return ingestion_service(settings).create_keyword_index(
        chunk_set_public_id, payload, admin.admin.public_id
    )


@router.get("/keyword-indexes/{public_id}")
async def keyword_index(public_id: str, settings: SettingsDependency):
    return ingestion_service(settings).get_keyword_index(public_id)


@router.post("/keyword-indexes/{public_id}/build")
async def build_keyword_index(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return ingestion_service(settings).build_keyword_index(public_id, admin.admin.public_id)


@router.post("/keyword-indexes/{public_id}/validate")
async def validate_keyword_index(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return ingestion_service(settings).validate_keyword_index(public_id, admin.admin.public_id)


@router.post("/keyword-indexes/{public_id}/activate")
async def activate_keyword_index(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return ingestion_service(settings).activate_keyword_index(public_id, admin.admin.public_id)


# --- retrieval profiles -----------------------------------------------------


@router.get("/retrieval-profiles")
async def retrieval_profiles(settings: SettingsDependency):
    return retrieval_service(settings).list_profiles()


@router.post("/spaces/{space_public_id}/retrieval-profiles")
async def create_retrieval_profile(
    space_public_id: str, payload: RetrievalProfileCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return retrieval_service(settings).create_profile(
        space_public_id, payload, admin.admin.public_id
    )


@router.get("/retrieval-profiles/{public_id}")
async def retrieval_profile(public_id: str, settings: SettingsDependency):
    return retrieval_service(settings).get_profile(public_id)


@router.patch("/retrieval-profiles/{public_id}")
async def patch_retrieval_profile(
    public_id: str, payload: RetrievalProfilePatch, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return retrieval_service(settings).patch_profile(public_id, payload, admin.admin.public_id)


@router.post("/retrieval-profiles/{public_id}/validate")
async def validate_retrieval_profile(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return retrieval_service(settings).validate_profile(public_id, admin.admin.public_id)


@router.post("/retrieval-profiles/{public_id}/activate")
async def activate_retrieval_profile(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return retrieval_service(settings).activate_profile(public_id, admin.admin.public_id)


# --- retrieval -----------------------------------------------------


@router.post("/retrieve")
async def retrieve(payload: RetrieveRequest, settings: SettingsDependency, admin: CsrfDependency):
    return retrieval_service(settings).retrieve(payload, admin.admin.public_id)


@router.get("/retrieval-runs/{public_id}")
async def retrieval_run(public_id: str, settings: SettingsDependency):
    return retrieval_service(settings).get_retrieval_run(public_id)


@router.get("/retrieval-runs/{public_id}/results")
async def retrieval_results(public_id: str, settings: SettingsDependency):
    return retrieval_service(settings).get_retrieval_results(public_id)


# --- grounded generation -----------------------------------------------------


@router.post("/grounded-answer")
async def grounded_answer(
    payload: GroundedAnswerRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return generation_service(settings).grounded_answer(payload, admin.admin.public_id)


@router.get("/grounded-requests/{public_id}")
async def grounded_request(public_id: str, settings: SettingsDependency):
    return generation_service(settings).get_grounded_request(public_id)


@router.get("/grounded-requests/{public_id}/answer")
async def grounded_answer_result(public_id: str, settings: SettingsDependency):
    return generation_service(settings).get_answer(public_id)


@router.get("/grounded-requests/{public_id}/citations")
async def grounded_citations(public_id: str, settings: SettingsDependency):
    return generation_service(settings).get_citations(public_id)


@router.get("/grounded-requests/{public_id}/issues")
async def grounded_issues(public_id: str, settings: SettingsDependency):
    return generation_service(settings).get_issues(public_id)


# --- RAG chat lab -----------------------------------------------------


@router.post("/chat-lab/sessions")
async def create_chat_lab_session(
    payload: RagSessionCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return generation_service(settings).create_session(payload, admin.admin.public_id)


@router.get("/chat-lab/sessions/{public_id}")
async def chat_lab_session(public_id: str, settings: SettingsDependency):
    return generation_service(settings).get_session(public_id)


@router.post("/chat-lab/sessions/{public_id}/messages")
async def post_chat_lab_message(
    public_id: str, payload: RagSessionMessageCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return generation_service(settings).post_message(
        public_id, payload.message, payload.retrieval_profile_public_id, admin.admin.public_id
    )


@router.post("/chat-lab/sessions/{public_id}/close")
async def close_chat_lab_session(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return generation_service(settings).close_session(public_id, admin.admin.public_id)


# --- evaluation -----------------------------------------------------


@router.get("/evaluation-suites")
async def evaluation_suites(settings: SettingsDependency):
    return evaluation_service(settings).list_suites()


@router.post("/spaces/{space_public_id}/evaluation-suites")
async def create_evaluation_suite(
    space_public_id: str, payload: EvaluationSuiteCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return evaluation_service(settings).create_suite(
        space_public_id, payload, admin.admin.public_id
    )


@router.get("/evaluation-suites/{public_id}")
async def evaluation_suite(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).get_suite(public_id)


@router.post("/evaluation-suites/{public_id}/fixtures")
async def add_evaluation_fixture(
    public_id: str, payload: EvaluationFixtureCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return evaluation_service(settings).add_fixture(public_id, payload, admin.admin.public_id)


@router.post("/evaluation-suites/{public_id}/runs")
async def create_evaluation_run(
    public_id: str, payload: EvaluationRunCreate, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return evaluation_service(settings).create_run(public_id, payload, admin.admin.public_id)


@router.get("/evaluation-runs/{public_id}")
async def evaluation_run(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).get_run(public_id)


@router.post("/evaluation-runs/{public_id}/execute")
async def execute_evaluation_run(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return evaluation_service(settings).execute_run(public_id, admin.admin.public_id)


@router.get("/evaluation-runs/{public_id}/metrics")
async def evaluation_metrics(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).get_metrics(public_id)


# --- index comparison -----------------------------------------------------


@router.post("/index-comparisons")
async def create_index_comparison(
    payload: IndexComparisonRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return evaluation_service(settings).compare_indexes(payload, admin.admin.public_id)


@router.get("/index-comparisons/{public_id}")
async def index_comparison(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).get_comparison(public_id)


# --- manifest -----------------------------------------------------


@router.post("/spaces/{public_id}/manifest")
async def generate_manifest(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return evaluation_service(settings).generate_manifest(public_id, admin.admin.public_id)


@router.get("/spaces/{public_id}/manifest/verify")
async def verify_manifest(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).verify_manifest(public_id)
