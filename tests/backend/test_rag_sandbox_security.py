"""Phase 13 Step 38 security tests.

Complements the fine-grained checks already covered in each service's
own test file with the cross-cutting checks that need their own file:
a structural no-execution/no-download scan across every Phase 13
module (mirrors Phase 11/12's own security test files), expired-
approval enforcement at corpus preparation, production/sandbox
isolation, and audit completeness.
"""

from __future__ import annotations

import ast
import sqlite3
from pathlib import Path

import pytest

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.dataset_sample_import import DatasetSampleImportRepository
from backend.database.repositories.dataset_verification import DatasetVerificationRepository
from backend.database.repositories.external_dataset_discovery import (
    ExternalDatasetDiscoveryRepository,
)
from backend.services.rag_sandbox_corpus_service import RagSandboxCorpusService
from backend.services.rag_sandbox_eligibility_service import (
    RagSandboxApprovalService,
    RagSandboxEligibilityService,
    RagSandboxError,
)

ADMIN_ID = "00000000-0000-0000-0000-000000000001"
REVIEWER_ID = "00000000-0000-0000-0000-000000000002"

PHASE13_MODULES = (
    "backend/services/rag_sandbox_eligibility_service.py",
    "backend/services/rag_sandbox_corpus_service.py",
    "backend/services/rag_sandbox_index_service.py",
    "backend/services/rag_sandbox_query_set_service.py",
    "backend/services/rag_sandbox_retrieval_service.py",
    "backend/services/rag_sandbox_answer_service.py",
    "backend/services/rag_sandbox_evaluation_service.py",
    "backend/services/rag_sandbox_human_review_service.py",
    "backend/services/rag_sandbox_report_service.py",
    "backend/services/rag_sandbox_acceptance_service.py",
    "backend/services/rag_sandbox_deletion_service.py",
    "backend/database/repositories/rag_sandbox.py",
    "backend/api/routes/rag_sandbox.py",
    "core_model/rag_sandbox/__init__.py",
)

_FORBIDDEN_CALL_NAMES = frozenset({"eval", "exec", "compile", "__import__"})
# "rag_sandbox_" tables are this phase's own governance tables and are
# deliberately excluded -- these are the *production* RAG/training
# tables Phase 13 must never write to directly (it only ever reaches
# them through the existing, unmodified Phase 16 ingestion/retrieval/
# generation services).
_FORBIDDEN_TABLES = (
    "dataset_records", "manual_data_records", "semantic_chunks",
    "structured_record_candidates", "training_dataset", "rag_knowledge_spaces",
    "rag_knowledge_sources", "rag_source_versions", "rag_chunk_sets", "rag_chunks",
    "rag_embedding_models", "rag_embedding_runs", "rag_chunk_embeddings",
    "rag_vector_indexes", "rag_keyword_indexes", "rag_retrieval_profiles",
    "rag_retrieval_runs", "rag_retrieved_chunks", "rag_context_assemblies",
    "rag_grounded_requests", "rag_grounded_answers", "rag_answer_citations",
    "rag_grounding_issues", "rag_evaluation_suites", "rag_evaluation_fixtures",
    "rag_evaluation_runs", "rag_evaluation_metrics",
)


def _module_source(relative_path: str) -> str:
    return (Path(__file__).resolve().parents[2] / relative_path).read_text(encoding="utf-8")


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    settings = Settings(
        database_path=tmp_path / "rag_sandbox_security.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def _build_finalized_sample_import(settings: Settings) -> dict:
    discovery = ExternalDatasetDiscoveryRepository(settings.resolved_database_path)
    session = discovery.create_session(
        {"session_code": "session-1", "requested_by_admin_public_id": ADMIN_ID}
    )
    candidate = discovery.create_candidate(
        session["public_id"],
        {
            "canonical_name": "Tamil Corpus", "normalized_name": "tamil corpus",
            "declared_licence": "CC-BY-4.0",
        },
    )
    verification = DatasetVerificationRepository(settings.resolved_database_path)
    case = verification.create_case(
        {
            "candidate_public_id": candidate["public_id"], "verification_code": "VC-1",
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    verification.update_case(case["public_id"], {"identity_status": "verified"})
    verification.assess_permission(
        case["public_id"], "rag_use",
        {"candidate_public_id": candidate["public_id"], "status": "likely_allowed"},
    )
    verification.review_permission(
        case["public_id"], "rag_use",
        status="approved", reviewed_by=ADMIN_ID, reason="Licence review",
    )
    verification.lock_case(case["public_id"], {"summary": "finalized for test"})

    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    sample_import = samples.create_sample_import(
        {
            "sample_import_code": "SI-1", "verification_case_public_id": case["public_id"],
            "candidate_public_id": candidate["public_id"], "purpose": "manual_review",
            "selection_method": "deterministic_first_n", "requested_count": 10,
            "requested_by_admin_public_id": ADMIN_ID,
        }
    )
    sample_file = samples.add_file(
        sample_import["public_id"],
        {
            "original_filename": "corpus.txt", "safe_filename": "corpus.txt",
            "relative_path": "corpus.txt", "declared_format": "txt",
        },
    )
    record = samples.add_record(
        sample_import["public_id"],
        {
            "source_file_public_id": sample_file["public_id"],
            "modality": "text", "language": "tamil",
            "raw_content": "தமிழ் உரை", "normalized_content": "தமிழ் உரை",
            "source_checksum": "chk-source-0", "record_checksum": "chk-record-0",
            "status": "accepted",
        },
    )
    with sqlite3.connect(settings.resolved_database_path) as connection:
        record_id = connection.execute(
            "SELECT id FROM external_dataset_sample_records WHERE public_id=?",
            (record["public_id"],),
        ).fetchone()[0]
    samples.add_review(
        sample_import["public_id"],
        {
            "target_type": "record", "target_id": record_id, "decision": "accept",
            "reason": "clean record", "reviewer_admin_public_id": REVIEWER_ID,
        },
    )
    samples.add_report(
        sample_import["public_id"],
        {
            "rag_sandbox_eligible": True, "training_assessment_status": "not_assessed",
            "report": {"summary": "ok"}, "finalized_by_admin_public_id": ADMIN_ID,
        },
    )
    samples.lock_sample_import(
        sample_import["public_id"], report={"summary": "ok"},
        rag_sandbox_eligible=True, training_assessment_status="not_assessed", status="validated",
    )
    return samples.get_sample_import(sample_import["public_id"])


# -- structural no-execution / no-download / no-production-write scan --------------------


@pytest.mark.parametrize("relative_path", PHASE13_MODULES)
def test_module_never_calls_eval_exec_or_a_shell(relative_path: str) -> None:
    source = _module_source(relative_path)
    tree = ast.parse(source, filename=relative_path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in _FORBIDDEN_CALL_NAMES, (
                f"{relative_path} calls forbidden builtin {node.func.id}"
            )
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in ("subprocess",), f"{relative_path} imports subprocess"
    assert "subprocess" not in source, f"{relative_path} references subprocess"
    assert "os.system(" not in source, f"{relative_path} calls os.system"


@pytest.mark.parametrize("relative_path", PHASE13_MODULES)
def test_module_never_writes_directly_to_a_production_table(relative_path: str) -> None:
    source = _module_source(relative_path)
    lowered = source.lower()
    for forbidden in _FORBIDDEN_TABLES:
        assert f"insert into {forbidden}" not in lowered, (
            f"{relative_path} inserts directly into forbidden production table '{forbidden}'"
        )
        assert f"update {forbidden}" not in lowered, (
            f"{relative_path} updates forbidden production table '{forbidden}' directly"
        )


@pytest.mark.parametrize(
    "relative_path",
    # core_model/rag_sandbox/__init__.py is deliberately excluded: it
    # defines PROHIBITED_SANDBOX_SIGNALS, the one legitimate place these
    # strings must appear -- to enumerate what every other module must
    # never produce, mirroring Phase 12's own PROHIBITED_SAMPLE_IMPORT_
    # PURPOSES pattern.
    tuple(path for path in PHASE13_MODULES if path != "core_model/rag_sandbox/__init__.py"),
)
def test_module_never_claims_production_activation_or_training_approval(
    relative_path: str,
) -> None:
    source = _module_source(relative_path)
    for forbidden in (
        "training_approved", "production_rag_activated", "Training Approved",
        "Production RAG Activated", "Model Released",
    ):
        assert forbidden not in source, f"{relative_path} contains forbidden phrase {forbidden!r}"


def test_prohibited_sandbox_signals_are_declared_exactly_once() -> None:
    from core_model.rag_sandbox import PROHIBITED_SANDBOX_SIGNALS

    assert set(PROHIBITED_SANDBOX_SIGNALS) == {
        "production_rag_activated", "training_approved", "training_started",
    }


@pytest.mark.parametrize("relative_path", PHASE13_MODULES)
def test_module_never_downloads_external_content(relative_path: str) -> None:
    source = _module_source(relative_path)
    for forbidden in ("requests.get(", "requests.post(", "urlopen(", "git clone", "urllib.request"):
        assert forbidden not in source, f"{relative_path} appears to download external content"


# -- expiry enforcement -------------------------------------------------------------------


def test_prepare_corpus_rejects_an_expired_approval(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings)
    eligibility_service = RagSandboxEligibilityService(settings)
    experiment = eligibility_service.create_experiment(
        sample_import["public_id"],
        {"purpose": "retrieval_validation", "created_by_admin_public_id": ADMIN_ID},
    )
    approval_service = RagSandboxApprovalService(settings)
    approval = approval_service.request_approval(
        experiment["public_id"],
        {
            "purpose": "retrieval_validation", "maximum_records": 100,
            "maximum_total_characters": 500_000, "maximum_total_tokens": 100_000,
        },
        admin_id=ADMIN_ID,
    )
    approval_service.approve(
        approval["public_id"], admin_id=ADMIN_ID, expires_at="2000-01-01T00:00:00+00:00"
    )

    corpus_service = RagSandboxCorpusService(settings)
    with pytest.raises(RagSandboxError, match="expired"):
        corpus_service.prepare_corpus(experiment["public_id"], admin_id=ADMIN_ID)


def test_prepare_corpus_succeeds_with_a_future_expiry(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings)
    eligibility_service = RagSandboxEligibilityService(settings)
    experiment = eligibility_service.create_experiment(
        sample_import["public_id"],
        {"purpose": "retrieval_validation", "created_by_admin_public_id": ADMIN_ID},
    )
    approval_service = RagSandboxApprovalService(settings)
    approval = approval_service.request_approval(
        experiment["public_id"],
        {
            "purpose": "retrieval_validation", "maximum_records": 100,
            "maximum_total_characters": 500_000, "maximum_total_tokens": 100_000,
        },
        admin_id=ADMIN_ID,
    )
    approval_service.approve(
        approval["public_id"], admin_id=ADMIN_ID, expires_at="2099-01-01T00:00:00+00:00"
    )

    corpus_service = RagSandboxCorpusService(settings)
    corpus = corpus_service.prepare_corpus(experiment["public_id"], admin_id=ADMIN_ID)
    assert corpus["status"] == "ready"


# -- isolation ---------------------------------------------------------------------------


def test_production_visible_column_is_hard_checked_to_zero_at_schema_level(
    settings: Settings,
) -> None:
    with sqlite3.connect(settings.resolved_database_path) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """INSERT INTO rag_sandbox_corpora(
                public_id, experiment_id, knowledge_space_id, sandbox_scope_key,
                production_visible, created_by_admin_public_id)
                VALUES ('x', 1, 1, 'sandbox-x', 1, ?)""",
                (ADMIN_ID,),
            )


def test_rejected_record_cannot_be_promoted(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings)
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    records = samples.list_records(sample_import["public_id"])
    samples.update_record_status(records[0]["public_id"], "rejected")

    eligibility_service = RagSandboxEligibilityService(settings)
    result = eligibility_service.check_eligibility(sample_import["public_id"])
    assert result["eligible"] is False
    assert any("accepted" in reason for reason in result["blocking_reasons"])


def test_pii_blocked_record_blocks_eligibility(settings: Settings) -> None:
    sample_import = _build_finalized_sample_import(settings)
    samples = DatasetSampleImportRepository(settings.resolved_database_path)
    records = samples.list_records(sample_import["public_id"])
    samples.add_record_issue(
        sample_import["public_id"],
        {
            "record_public_id": records[0]["public_id"],
            "issue_category": "pii",
            "issue_type": "detected_pii",
            "status": "blocked",
            "severity": "high",
        },
    )
    eligibility_service = RagSandboxEligibilityService(settings)
    result = eligibility_service.check_eligibility(sample_import["public_id"])
    assert result["eligible"] is False
    assert any("PII" in reason for reason in result["blocking_reasons"])


# -- audit completeness -------------------------------------------------------------------


@pytest.mark.parametrize(
    "relative_path",
    (
        "backend/services/rag_sandbox_eligibility_service.py",
        "backend/services/rag_sandbox_corpus_service.py",
        "backend/services/rag_sandbox_index_service.py",
        "backend/services/rag_sandbox_report_service.py",
        "backend/services/rag_sandbox_acceptance_service.py",
        "backend/services/rag_sandbox_deletion_service.py",
    ),
)
def test_every_mutating_service_imports_and_uses_audit_logging(relative_path: str) -> None:
    source = _module_source(relative_path)
    assert "AuditLogRepository" in source, f"{relative_path} never imports AuditLogRepository"
    assert "_audit(" in source, f"{relative_path} never calls the shared _audit() helper"
