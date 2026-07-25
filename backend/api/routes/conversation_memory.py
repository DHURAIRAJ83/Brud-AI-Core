"""Phase 17 conversation memory, sessions, consent, memory items,
memory retrieval, chat orchestration, and evaluation APIs.

Every mutation requires admin authentication and CSRF. There is no
public-facing route here -- the public chatbot route is untouched.
"""

from fastapi import APIRouter, Depends

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.conversation_memory import ConversationMemoryRepository
from backend.database.repositories.inference_runtime import InferenceRuntimeRepository
from backend.database.repositories.model_release import ModelReleaseRepository
from backend.database.repositories.rag import RagRepository
from backend.models.conversation_memory import (
    ConsentCreate,
    EvaluationFixtureCreate,
    EvaluationRunCreate,
    EvaluationSuiteCreate,
    MemoryItemCorrect,
    MemoryItemCreate,
    MemoryPolicyCreate,
    MemoryPolicyPatch,
    MemoryRetrieveRequest,
    MessageCreate,
    RetrievalProfileCreate,
    RetrievalProfilePatch,
    SessionCreate,
    SummaryCreate,
)
from backend.services.chat_orchestration_service import ChatOrchestrationService
from backend.services.conversation_session_service import ConversationSessionService
from backend.services.inference_runtime_service import InferenceRuntimeService
from backend.services.memory_evaluation_service import MemoryEvaluationService
from backend.services.memory_service import MemoryService
from backend.services.model_assignment_service import ModelAssignmentService
from backend.services.rag_retrieval_service import RagRetrievalService

router = APIRouter(
    prefix="/admin/conversation-memory",
    tags=["admin-conversation-memory"],
    dependencies=[Depends(require_admin)],
)


def _repository(settings) -> ConversationMemoryRepository:
    return ConversationMemoryRepository(settings.resolved_database_path)


def session_service(settings) -> ConversationSessionService:
    return ConversationSessionService(_repository(settings), settings)


def memory_service(settings) -> MemoryService:
    return MemoryService(_repository(settings), settings)


def evaluation_service(settings) -> MemoryEvaluationService:
    return MemoryEvaluationService(_repository(settings), memory_service(settings), settings)


def orchestration_service(settings) -> ChatOrchestrationService:
    inference_repository = InferenceRuntimeRepository(settings.resolved_database_path)
    release_repository = ModelReleaseRepository(settings.resolved_database_path)
    runtime_service = InferenceRuntimeService(inference_repository, release_repository, settings)
    assignment_service = ModelAssignmentService(
        inference_repository, release_repository, runtime_service, settings
    )
    rag_retrieval_service = RagRetrievalService(
        RagRepository(settings.resolved_database_path), settings
    )
    return ChatOrchestrationService(
        _repository(settings),
        inference_repository,
        runtime_service,
        assignment_service,
        session_service(settings),
        memory_service(settings),
        rag_retrieval_service,
        settings,
    )


# --- policies -----------------------------------------------------


@router.get("/policies")
async def policies(settings: SettingsDependency):
    return session_service(settings).list_policies()


@router.post("/policies")
async def create_policy(
    payload: MemoryPolicyCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return session_service(settings).create_policy(payload, admin.admin.public_id)


@router.get("/policies/{public_id}")
async def policy(public_id: str, settings: SettingsDependency):
    return session_service(settings).get_policy(public_id)


@router.patch("/policies/{public_id}")
async def patch_policy(
    public_id: str, payload: MemoryPolicyPatch, settings: SettingsDependency, admin: CsrfDependency
):
    return session_service(settings).patch_policy(public_id, payload, admin.admin.public_id)


@router.post("/policies/{public_id}/validate")
async def validate_policy(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return session_service(settings).validate_policy(public_id, admin.admin.public_id)


@router.post("/policies/{public_id}/activate")
async def activate_policy(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return session_service(settings).activate_policy(public_id, admin.admin.public_id)


# --- sessions -----------------------------------------------------


@router.get("/sessions")
async def sessions(settings: SettingsDependency):
    return session_service(settings).list_sessions()


@router.post("/sessions")
async def create_session(
    payload: SessionCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return session_service(settings).create_session(payload, admin.admin.public_id)


@router.get("/sessions/{public_id}")
async def session(public_id: str, settings: SettingsDependency):
    return session_service(settings).get_session(public_id)


@router.post("/sessions/{public_id}/pause")
async def pause_session(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return session_service(settings).pause_session(public_id, admin.admin.public_id)


@router.post("/sessions/{public_id}/resume")
async def resume_session(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return session_service(settings).resume_session(public_id, admin.admin.public_id)


@router.post("/sessions/{public_id}/close")
async def close_session(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return session_service(settings).close_session(public_id, admin.admin.public_id)


@router.post("/sessions/{public_id}/expire")
async def expire_session(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return session_service(settings).expire_session(public_id, admin.admin.public_id)


@router.get("/sessions/{public_id}/turns")
async def session_turns(public_id: str, settings: SettingsDependency):
    return session_service(settings).list_turns(public_id)


# --- turns and orchestration -----------------------------------------------------


@router.post("/sessions/{public_id}/messages")
async def post_message(
    public_id: str, payload: MessageCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return orchestration_service(settings).send_message(public_id, payload, admin.admin.public_id)


@router.get("/orchestration-runs/{public_id}")
async def orchestration_run(public_id: str, settings: SettingsDependency):
    return orchestration_service(settings).get_orchestration_run(public_id)


@router.get("/orchestration-runs/{public_id}/context")
async def orchestration_context(public_id: str, settings: SettingsDependency):
    return orchestration_service(settings).get_context(public_id)


@router.get("/orchestration-runs/{public_id}/response")
async def orchestration_response(public_id: str, settings: SettingsDependency):
    return orchestration_service(settings).get_response(public_id)


@router.get("/orchestration-runs/{public_id}/issues")
async def orchestration_issues(public_id: str, settings: SettingsDependency):
    return orchestration_service(settings).get_issues(public_id)


# --- summaries -----------------------------------------------------


@router.post("/sessions/{public_id}/summaries")
async def create_summary(
    public_id: str, payload: SummaryCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return session_service(settings).create_summary(public_id, payload, admin.admin.public_id)


@router.get("/sessions/{public_id}/summaries")
async def session_summaries(public_id: str, settings: SettingsDependency):
    return session_service(settings).list_summaries(public_id)


@router.get("/summaries/{public_id}")
async def summary(public_id: str, settings: SettingsDependency):
    return session_service(settings).get_summary(public_id)


@router.post("/summaries/{public_id}/validate")
async def validate_summary(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return session_service(settings).validate_summary_endpoint(public_id, admin.admin.public_id)


@router.post("/summaries/{public_id}/accept")
async def accept_summary(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return session_service(settings).accept_summary(public_id, admin.admin.public_id)


@router.post("/summaries/{public_id}/reject")
async def reject_summary(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return session_service(settings).reject_summary(public_id, admin.admin.public_id)


# --- consent -----------------------------------------------------


@router.get("/consents")
async def consents(settings: SettingsDependency):
    return memory_service(settings).list_consents()


@router.post("/consents")
async def create_consent(
    payload: ConsentCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return memory_service(settings).create_consent(payload, admin.admin.public_id)


@router.get("/consents/{public_id}")
async def consent(public_id: str, settings: SettingsDependency):
    return memory_service(settings).get_consent(public_id)


@router.post("/consents/{public_id}/revoke")
async def revoke_consent(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return memory_service(settings).revoke_consent(public_id, admin.admin.public_id)


@router.post("/consents/{public_id}/expire")
async def expire_consent(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return memory_service(settings).expire_consent(public_id, admin.admin.public_id)


# --- memory items -----------------------------------------------------


@router.get("/memory-items")
async def memory_items(settings: SettingsDependency, participant_scope_key: str | None = None):
    return memory_service(settings).list_memory_items(participant_scope_key)


@router.post("/memory-items")
async def create_memory_item(
    payload: MemoryItemCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return memory_service(settings).propose_memory(payload, admin.admin.public_id)


@router.get("/memory-items/{public_id}")
async def memory_item(public_id: str, settings: SettingsDependency):
    return memory_service(settings).get_memory_item(public_id)


@router.post("/memory-items/{public_id}/confirm")
async def confirm_memory_item(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return memory_service(settings).confirm_memory(public_id, admin.admin.public_id)


@router.post("/memory-items/{public_id}/reject")
async def reject_memory_item(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return memory_service(settings).reject_memory(public_id, admin.admin.public_id)


@router.post("/memory-items/{public_id}/correct")
async def correct_memory_item(
    public_id: str, payload: MemoryItemCorrect, settings: SettingsDependency, admin: CsrfDependency
):
    return memory_service(settings).correct_memory(public_id, payload, admin.admin.public_id)


@router.post("/memory-items/{public_id}/expire")
async def expire_memory_item(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return memory_service(settings).expire_memory(public_id, admin.admin.public_id)


@router.post("/memory-items/{public_id}/delete")
async def delete_memory_item(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return memory_service(settings).delete_memory(public_id, admin.admin.public_id)


@router.get("/memory-items/{public_id}/versions")
async def memory_item_versions(public_id: str, settings: SettingsDependency):
    return memory_service(settings).get_versions(public_id)


@router.get("/memory-items/{public_id}/events")
async def memory_item_events(public_id: str, settings: SettingsDependency):
    return memory_service(settings).get_events(public_id)


# --- memory retrieval -----------------------------------------------------


@router.get("/retrieval-profiles")
async def retrieval_profiles(settings: SettingsDependency):
    return memory_service(settings).list_profiles()


@router.post("/retrieval-profiles")
async def create_retrieval_profile(
    payload: RetrievalProfileCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return memory_service(settings).create_profile(payload, admin.admin.public_id)


@router.get("/retrieval-profiles/{public_id}")
async def retrieval_profile(public_id: str, settings: SettingsDependency):
    return memory_service(settings).get_profile(public_id)


@router.patch("/retrieval-profiles/{public_id}")
async def patch_retrieval_profile(
    public_id: str, payload: RetrievalProfilePatch, settings: SettingsDependency,
    admin: CsrfDependency,
):
    return memory_service(settings).patch_profile(public_id, payload, admin.admin.public_id)


@router.post("/retrieval-profiles/{public_id}/validate")
async def validate_retrieval_profile(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return memory_service(settings).validate_profile(public_id, admin.admin.public_id)


@router.post("/retrieval-profiles/{public_id}/activate")
async def activate_retrieval_profile(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return memory_service(settings).activate_profile(public_id, admin.admin.public_id)


@router.post("/retrieve")
async def retrieve(
    payload: MemoryRetrieveRequest, settings: SettingsDependency, admin: CsrfDependency
):
    return memory_service(settings).retrieve(payload, admin.admin.public_id)


@router.get("/retrieval-runs/{public_id}")
async def retrieval_run(public_id: str, settings: SettingsDependency):
    return memory_service(settings).get_retrieval_run(public_id)


@router.get("/retrieval-runs/{public_id}/results")
async def retrieval_results(public_id: str, settings: SettingsDependency):
    return memory_service(settings).get_retrieval_results(public_id)


# --- evaluation -----------------------------------------------------


@router.get("/evaluation-suites")
async def evaluation_suites(settings: SettingsDependency):
    return evaluation_service(settings).list_suites()


@router.post("/evaluation-suites")
async def create_evaluation_suite(
    payload: EvaluationSuiteCreate, settings: SettingsDependency, admin: CsrfDependency
):
    return evaluation_service(settings).create_suite(payload, admin.admin.public_id)


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


@router.post("/evaluation-runs/{public_id}/execute")
async def execute_evaluation_run(
    public_id: str, settings: SettingsDependency, admin: CsrfDependency
):
    return evaluation_service(settings).execute_run(public_id, admin.admin.public_id)


@router.get("/evaluation-runs/{public_id}")
async def evaluation_run(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).get_run(public_id)


@router.get("/evaluation-runs/{public_id}/metrics")
async def evaluation_metrics(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).get_metrics(public_id)


# --- manifest -----------------------------------------------------
#
# Manifest generation writes a new append-only row, so it is a POST
# requiring CSRF like every other mutation (deviating from a literal
# GET-for-generate reading of the route table, which would conflict
# with the "all mutations require authentication and CSRF" rule).
# Verification is read-only (it recomputes and compares a checksum,
# writing nothing) and stays a GET, matching Phase 16's identical
# manifest generate/verify precedent.


@router.post("/policies/{public_id}/manifest")
async def generate_manifest(public_id: str, settings: SettingsDependency, admin: CsrfDependency):
    return evaluation_service(settings).generate_manifest(public_id, admin.admin.public_id)


@router.get("/policies/{public_id}/manifest/verify")
async def verify_manifest(public_id: str, settings: SettingsDependency):
    return evaluation_service(settings).verify_manifest(public_id)
