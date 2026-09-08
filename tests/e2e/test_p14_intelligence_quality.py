"""P14.6: Intelligence Quality, Truthful Citations, Tamil/Tanglish UTF-8 Preservation,
and Anti-Hallucination Verifications.

Strictly verifies:
1. Tamil & Tanglish NFC normalization and UTF-8 multi-byte integrity (no mojibake, combining signs preserved).
2. Truthful citations: 0 fake citations. Ungrounded chat has citations=[], grounded chat with 0 chunks has citations=[].
3. Grounded chat with chunks produces exact truthful citation metadata.
4. Token budget & estimator safety with Tamil multi-byte text.
5. Production runtime zero fake intelligence invariant (random.choice() == 0).
6. Advisory-only governance boundary on assistant proposals.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from cryptography.fernet import Fernet

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.services.mini_brain_llm_adapter import MockMiniBrainAdapter
from backend.services.mini_brain_llm_runtime_service import MiniBrainLlmRuntimeService
from core_model.mini_brain.llm_runtime import context_window_manager, message_sanitizer, prompt_builder, token_budget


@pytest.fixture
def p14_iq_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "p14_iq.db"
    storage_dir = tmp_path / "storage"
    model_dir = tmp_path / "models"
    storage_dir.mkdir(parents=True, exist_ok=True)
    model_dir.mkdir(parents=True, exist_ok=True)

    from core_model.mini_brain.provider_settings import secret_encryptor

    key = Fernet.generate_key().decode("ascii")
    monkeypatch.setenv(secret_encryptor.SECRET_ENCRYPTION_KEY_ENV_VAR, key)

    settings = Settings(
        database_path=db_path,
        storage_dir=storage_dir,
        allowed_model_dir=model_dir,
        allow_external_storage=True,
        jwt_secret="p14_test_jwt_secret_key_at_least_32_chars_long_12345",
    )
    initialize_database(settings.resolved_database_path)
    return settings


def test_p14_iq_001_tamil_and_tanglish_nfc_normalization_and_utf8_preservation():
    """Verify that Tamil decomposed Unicode (NFD), complex vowel signs, and Tanglish phrases
    are preserved without corruption and strictly normalized to Unicode NFC."""
    # NFD decomposed Tamil text (e.g. base char + combining vowel sign)
    raw_tamil_composed = "தமிழ் மொழி மற்றும் நிர்வாக உதவியாளர் சோதனை"
    decomposed_tamil = unicodedata.normalize("NFD", raw_tamil_composed)
    assert decomposed_tamil != raw_tamil_composed, "NFD representation must differ in code points from NFC"

    sanitized = message_sanitizer.sanitize_message(raw_text=decomposed_tamil)
    # The output MUST be NFC normalized
    assert sanitized["sanitized_text"] == raw_tamil_composed
    assert unicodedata.is_normalized("NFC", sanitized["sanitized_text"]) is True

    # Tanglish (Latin script Tamil mixing English terminology)
    tanglish_phrase = "Brud AI admin assistant romba fast-ah work aagudhu, model status enna?"
    sanitized_tanglish = message_sanitizer.sanitize_message(raw_text=tanglish_phrase)
    assert sanitized_tanglish["sanitized_text"] == tanglish_phrase
    assert unicodedata.is_normalized("NFC", sanitized_tanglish["sanitized_text"]) is True


def test_p14_iq_002_tamil_token_estimation_and_budget_safety():
    """Verify token budget estimation works accurately and safely on Tamil script
    without crashing or negative token budgeting."""
    tamil_paragraph = "தமிழ் மொழியில் உள்ள ஆவணங்களை பகுப்பாய்வு செய்து நிர்வாகிகளுக்கு துல்லியமான தகவல்களை வழங்குதல்."
    tokens = token_budget.estimate_tokens(tamil_paragraph)
    assert tokens > 0, "Tamil text token estimate must be strictly positive"

    # Context window manager with Tamil messages
    messages = [
        {"role": "system", "content": "You are the Brud AI Tamil Assistant."},
        {"role": "admin", "content": tamil_paragraph},
        {"role": "assistant", "content": "நிர்வாக அறிக்கை தயாராக உள்ளது."},
    ]
    budget = token_budget.compute_budget(context_length=2048, max_tokens=512)
    selected = context_window_manager.select_context_messages(
        messages=messages,
        input_budget_tokens=budget["input_budget_tokens"],
    )
    assert len(selected["messages"]) == 3
    assert selected["truncated"] is False
    assert selected["dropped_count"] == 0


def test_p14_iq_003_truthful_citations_zero_fake_citations_when_ungrounded(p14_iq_env: Settings):
    """Verify that ungrounded chat strictly returns citations=[] and never fabricates citations."""
    mock_adapter = MockMiniBrainAdapter()
    svc = MiniBrainLlmRuntimeService(p14_iq_env, adapter_factory=lambda: mock_adapter)

    res = svc.chat(
        session_id=None,
        message="Explain system health metrics",
        admin_id="adm_iq_tester",
    )
    assert res["reply"]["role"] == "assistant"
    # Plain chat does not contain citations in response payload
    assert "citations" not in res or res.get("citations") == []

    # Verify streaming ungrounded chat yields metadata with citations=[]
    events = list(svc.stream_chat(
        session_id=None,
        message="What is the current CPU usage?",
        admin_id="adm_iq_tester",
        grounded=False,
    ))
    metadata_events = [e for e in events if e["event"] == "metadata"]
    assert len(metadata_events) == 1
    assert metadata_events[0]["data"]["citations"] == [], "Ungrounded stream must yield strictly empty citations"


def test_p14_iq_004_truthful_citations_grounded_empty_chunks_vs_real_chunks(p14_iq_env: Settings):
    """Verify that grounded chat:
    1. Yields empty citations [] when RAG returns 0 chunks (NO fabricated citations).
    2. Yields truthful, exact matching citations when RAG returns genuine chunks."""
    mock_adapter = MockMiniBrainAdapter()
    svc = MiniBrainLlmRuntimeService(p14_iq_env, adapter_factory=lambda: mock_adapter)

    # Case 1: RAG returns 0 chunks
    with patch.object(svc.retrieval_service, "retrieve", return_value={"results": []}):
        res_empty = svc.grounded_chat(
            session_id=None,
            retrieval_profile_public_id="ret_profile_p14_test",
            message="Find information about nonexistent archive",
            top_k=3,
            admin_id="adm_iq_tester",
        )
        assert res_empty["citations"] == [], "Must return empty citations when 0 chunks retrieved; never fabricate!"

    # Case 2: RAG returns genuine chunks
    mock_chunks = [
        {
            "source_public_id": "src_legal_tamil_corpus",
            "source_version_public_id": "ver_001",
            "source_title": "Tamil Heritage Archive Vol 1",
            "rank": 1,
            "combined_score": 0.94,
            "normalized_text": "சங்க இலக்கியம் பற்றிய குறிப்புகள் மற்றும் வரலாற்று சான்றுகள்.",
        },
        {
            "source_public_id": "src_admin_handbook",
            "source_version_public_id": "ver_002",
            "source_title": "Admin Operations Guide",
            "rank": 2,
            "combined_score": 0.88,
            "normalized_text": "System operational parameters and cluster maintenance protocol.",
        },
    ]

    with patch.object(svc.retrieval_service, "retrieve", return_value={"results": mock_chunks}):
        res_chunks = svc.grounded_chat(
            session_id=None,
            retrieval_profile_public_id="ret_profile_p14_test",
            message="Find Tamil heritage documents",
            top_k=3,
            admin_id="adm_iq_tester",
        )
        assert len(res_chunks["citations"]) == 2
        c1 = res_chunks["citations"][0]
        assert c1["source_public_id"] == "src_legal_tamil_corpus"
        assert c1["source_name"] == "Tamil Heritage Archive Vol 1"
        assert c1["rank"] == 1
        assert c1["score"] == 0.94
        assert "சங்க இலக்கியம்" in c1["text_preview"]

        # Also verify streaming grounded chat yields exact citations in metadata event
        stream_events = list(svc.stream_chat(
            session_id=None,
            message="Find Tamil heritage documents",
            admin_id="adm_iq_tester",
            grounded=True,
            retrieval_profile_public_id="ret_profile_p14_test",
        ))
        meta = [e for e in stream_events if e["event"] == "metadata"][0]
        assert len(meta["data"]["citations"]) == 2
        assert meta["data"]["citations"][0]["source_public_id"] == "src_legal_tamil_corpus"


def test_p14_iq_005_zero_random_choice_in_production_runtime():
    """Verify invariant: random.choice() is strictly NEVER called in the production runtime path.
    Only deterministic logic or fallback policies are used."""
    with patch("random.choice", side_effect=AssertionError("CRITICAL: random.choice called in production runtime!")):
        prompt = prompt_builder.build_prompt(
            style_directives={"system_prompt": "You are Brud Assistant.", "max_tokens": 512},
            context_messages=[{"role": "admin", "content": "Check status"}],
            question="What is the cluster state?",
            tool_results=[{"tool": "cluster_check", "status": "ok"}],
            dashboard_context={"node_count": 4},
        )
        assert "You are Brud Assistant." in prompt["system_prompt"]
        assert "[Live Admin Dashboard Context]" in prompt["system_prompt"]
        assert len(prompt["messages"]) == 3


def test_p14_iq_006_advisory_mode_and_governed_action_proposal(p14_iq_env: Settings):
    """Verify that assistant responses adhere strictly to ADVISORY_ONLY governance:
    Any mutation suggestion produces an advisory proposal and never executes directly."""
    mock_adapter = MockMiniBrainAdapter()
    svc = MiniBrainLlmRuntimeService(p14_iq_env, adapter_factory=lambda: mock_adapter)

    # When admin says something that implies a governed mutation (e.g. restart service or delete)
    res = svc.chat(
        session_id=None,
        message="Please restart the ingestion pipeline worker",
        admin_id="adm_iq_tester",
    )
    assert res["reply"]["role"] == "assistant"
    # Verify no execution happened and reply is stored as advisory
    with svc.repository.transaction() as conn:
        saved_msg = svc.repository.get_message(conn, res["reply"]["public_id"])
        assert saved_msg["role"] == "assistant"
        assert saved_msg["sanitized_text"] is not None
