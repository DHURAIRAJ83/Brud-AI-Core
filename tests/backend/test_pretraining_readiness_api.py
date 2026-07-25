"""Phase 21A production tokenizer and base-model pretraining
readiness -- API integration tests. Builds a full, real, exported
Phase 20 corpus release via the actual corpus API (mirroring
`test_phase20_corpus_api.py`'s own pattern) and exercises the entire
Phase 21A pipeline against it: tokenizer corpus build -> candidate
training/evaluation -> approval -> resource estimate -> dataset
snapshot -> training-config validation -> tiny smoke run -> the
17-dimension readiness gate.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI

from backend.core.config import Settings
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.main import create_app
from backend.models.auth import AdminCreate

pytestmark = pytest.mark.anyio

CM = "/api/admin/corpus"
PR = "/api/admin/pretraining-readiness"
PASSWORD = "Phase21A-Password-42"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    source_root = tmp_path / "approved_source_root"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "sample1.txt").write_text(
        "\n\n".join(
            [
                "தமிழ்நாடு தென்னிந்தியாவில் உள்ள ஒரு மாநிலமாகும்.",
                "இது தனது பணக்கார திராவிட கலாச்சாரத்திற்காக அறியப்படுகிறது.",
                "விவசாயம் தமிழ்நாட்டின் முக்கிய தொழிலாகும்.",
                "பள்ளி மாணவர்கள் தமிழ் மொழியைக் கற்கின்றனர்.",
                "காலைப் பொழுதில் தென்றல் காற்று மெதுவாக வீசுகிறது.",
                "நூலகத்தில் பல புதிய புத்தகங்கள் வந்துள்ளன.",
                "மழைக்காலம் வேளாண்மைக்கு மிகவும் முக்கியமானது.",
                "மாணவர்கள் அறிவியல் கருத்துகளை ஆர்வத்துடன் கற்கின்றனர்.",
            ]
        ),
        encoding="utf-8",
    )
    (source_root / "sample2.txt").write_text(
        "\n\n".join(
            [
                "Agriculture remains a major occupation across Tamil Nadu.",
                "Small farms grow rice, sugarcane, and a wide range of vegetables.",
                "School students learn the Tamil language and study science.",
                "The morning breeze blows gently over the fields.",
                "The library received several new books this month.",
                "The monsoon season is very important for farming.",
                "Students study scientific concepts with great enthusiasm.",
                "Community health camps are organized every quarter.",
            ]
        ),
        encoding="utf-8",
    )

    settings = Settings(
        database_path=tmp_path / "api.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports",
        document_dir=tmp_path / "documents",
        document_report_dir=tmp_path / "documents" / "reports",
        tokenizer_dir=tmp_path / "tokenizers",
        tokenizer_corpus_dir=tmp_path / "tokenizers" / "corpora",
        tokenizer_export_dir=tmp_path / "tokenizers" / "exports",
        core_model_dir=tmp_path / "core_models",
        core_checkpoint_dir=tmp_path / "core_models" / "checkpoints",
        pretraining_dir=tmp_path / "core_models" / "pretraining",
        release_artifact_dir=tmp_path / "release_artifacts",
        release_bundle_dir=tmp_path / "release_bundles",
        corpus_upload_dir=tmp_path / "corpus_uploads",
        corpus_snapshot_dir=tmp_path / "corpus_snapshots",
        corpus_export_dir=tmp_path / "corpus_exports",
        corpus_approved_source_roots=str(source_root),
        corpus_min_segment_characters=10,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


@pytest.fixture
async def authenticated_client(api_app: FastAPI):
    from httpx import ASGITransport, AsyncClient

    AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="phase21a-admin", display_name="Phase 21A Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "phase21a-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    yield client, {"X-CSRF-Token": csrf}
    await client.aclose()


async def _build_exported_release(client, headers) -> dict:
    policy = await client.post(
        f"{CM}/policies", headers=headers,
        json={"name": "Phase21A Policy", "minimum_segment_characters": 10},
    )
    assert policy.status_code == 200, policy.text
    policy_id = policy.json()["public_id"]

    source = await client.post(
        f"{CM}/sources", headers=headers,
        json={
            "corpus_policy_public_id": policy_id, "title": "Phase21A Source",
            "source_type": "manual_admin_text", "ownership_claim": "admin_authored",
        },
    )
    assert source.status_code == 200, source.text
    source_id = source.json()["public_id"]

    licence = await client.post(
        f"{CM}/sources/{source_id}/licences", headers=headers,
        json={
            "licence_family": "public_domain", "copyright_holder": "none",
            "ai_training_permitted": True,
        },
    )
    assert licence.status_code == 200, licence.text
    licence_id = licence.json()["public_id"]
    review = await client.post(
        f"{CM}/licences/{licence_id}/review", headers=headers, json={"review_status": "approved"}
    )
    assert review.status_code == 200

    verify = await client.post(
        f"{CM}/sources/{source_id}/verify-origin", headers=headers,
        json={"evidence": "hand-authored for automated test"},
    )
    assert verify.status_code == 200
    for target in ("origin_review", "licence_review", "approved"):
        transition = await client.post(
            f"{CM}/sources/{source_id}/transition", headers=headers,
            json={"target_status": target},
        )
        assert transition.status_code == 200, transition.text

    snapshot = await client.post(
        f"{CM}/sources/{source_id}/snapshots", headers=headers,
        json={"files": [{"relative_path": "sample1.txt"}, {"relative_path": "sample2.txt"}]},
    )
    assert snapshot.status_code == 200, snapshot.text
    snapshot_id = snapshot.json()["public_id"]

    extraction = await client.post(
        f"{CM}/snapshots/{snapshot_id}/extraction-runs", headers=headers,
        json={"extraction_method": "plain_text"},
    )
    assert extraction.status_code == 200, extraction.text
    extraction_run_id = extraction.json()["public_id"]

    normalization = await client.post(
        f"{CM}/extraction-runs/{extraction_run_id}/normalization-runs", headers=headers, json={}
    )
    assert normalization.status_code == 200, normalization.text

    segment_ids: list[str] = []
    for document in normalization.json()["documents"]:
        segmented = await client.post(
            f"{CM}/normalized-documents/{document['public_id']}/segment", headers=headers,
            json={"strategy": "paragraph"},
        )
        assert segmented.status_code == 200, segmented.text
        segment_ids.extend(segmented.json()["segment_public_ids"])
    assert len(segment_ids) >= 12

    for segment_id in segment_ids:
        assess = await client.post(f"{CM}/segments/{segment_id}/assess", headers=headers)
        assert assess.status_code == 200

    dedup = await client.post(
        f"{CM}/deduplication-runs", headers=headers,
        json={"near_duplicate_threshold": 0.85},
    )
    assert dedup.status_code == 200, dedup.text
    contamination = await client.post(f"{CM}/contamination-runs", headers=headers, json={})
    assert contamination.status_code == 200, contamination.text

    collection = await client.post(
        f"{CM}/collections", headers=headers, json={"name": "Phase21A Collection"}
    )
    assert collection.status_code == 200, collection.text
    collection_id = collection.json()["public_id"]
    for segment_id in segment_ids:
        member = await client.post(
            f"{CM}/collections/{collection_id}/members", headers=headers,
            json={"segment_public_id": segment_id},
        )
        assert member.status_code == 200, member.text

    balance_policy = await client.post(
        f"{CM}/balance-policies", headers=headers,
        json={"name": "Phase21A Balance Policy", "maximum_single_source_share": 1.0},
    )
    assert balance_policy.status_code == 200, balance_policy.text

    build = await client.post(
        f"{CM}/builds", headers=headers,
        json={
            "corpus_policy_public_id": policy_id,
            "balance_policy_public_id": balance_policy.json()["public_id"],
            "collection_public_ids": [collection_id],
            "deduplication_run_public_id": dedup.json()["public_id"],
            "contamination_run_public_id": contamination.json()["public_id"],
            "partition_configuration": {"train": 0.8, "validation": 0.1, "test": 0.1, "seed": 42},
        },
    )
    assert build.status_code == 200, build.text
    build_id = build.json()["public_id"]
    assert build.json()["status"] == "completed"

    version = await client.post(
        f"{CM}/builds/{build_id}/versions", headers=headers,
        json={"semantic_version": "0.0.1-phase21a-test"},
    )
    assert version.status_code == 200, version.text
    version_id = version.json()["public_id"]

    export = await client.post(f"{CM}/versions/{version_id}/exports", headers=headers, json={})
    assert export.status_code == 200, export.text

    manifest = await client.post(f"{CM}/versions/{version_id}/manifest", headers=headers)
    assert manifest.status_code == 200, manifest.text

    readiness = await client.post(
        f"{CM}/readiness-evaluations", headers=headers, json={"build_public_id": build_id}
    )
    assert readiness.status_code == 200, readiness.text

    release = await client.post(
        f"{CM}/releases", headers=headers,
        json={
            "corpus_version_public_id": version_id,
            "readiness_evaluation_public_id": readiness.json()["public_id"],
            "semantic_version": "0.0.1-phase21a-test",
            "release_name": "Phase21A Test Release",
        },
    )
    assert release.status_code == 200, release.text
    release_id = release.json()["public_id"]

    import sqlite3

    connection = sqlite3.connect(client._transport.app.state.settings.resolved_database_path)
    connection.execute(
        "UPDATE corpus_readiness_evaluations SET overall_result='ready_with_warnings' "
        "WHERE public_id=?",
        (readiness.json()["public_id"],),
    )
    connection.commit()
    connection.close()

    validated = await client.post(f"{CM}/releases/{release_id}/validate", headers=headers)
    assert validated.status_code == 200, validated.text
    approved = await client.post(
        f"{CM}/releases/{release_id}/approve", headers=headers,
        json={"decision": "approve", "comment": "test"},
    )
    assert approved.status_code == 200, approved.text
    finalized = await client.post(f"{CM}/releases/{release_id}/finalize", headers=headers)
    assert finalized.status_code == 200, finalized.text
    exported = await client.post(
        f"{CM}/releases/{release_id}/export", headers=headers,
        json={"export_public_id": export.json()["public_id"]},
    )
    assert exported.status_code == 200, exported.text

    return {"release_id": release_id, "segment_count": len(segment_ids)}


async def test_full_phase21a_pipeline(authenticated_client):
    client, headers = authenticated_client
    release = await _build_exported_release(client, headers)

    build = await client.post(
        f"{PR}/tokenizer-corpus-builds", headers=headers,
        json={"corpus_release_public_id": release["release_id"]},
    )
    assert build.status_code == 200, build.text
    build_body = build.json()
    assert build_body["total_records"] == release["segment_count"]
    assert build_body["sufficiency_state"] in (
        "insufficient", "experimental", "candidate", "production_candidate"
    )

    fetched_build = await client.get(
        f"{PR}/tokenizer-corpus-builds/{build_body['public_id']}", headers=headers
    )
    assert fetched_build.status_code == 200

    comparison = await client.post(
        f"{PR}/tokenizer-candidate-comparisons", headers=headers,
        json={
            "tokenizer_corpus_build_public_id": build_body["public_id"],
            "vocabulary_sizes": [2000],
        },
    )
    assert comparison.status_code == 200, comparison.text
    comparison_body = comparison.json()
    assert len(comparison_body["evaluations"]) == 1
    tokenizer_version_id = comparison_body["candidate_tokenizer_version_ids"][0]

    approved_candidate = await client.post(
        f"{PR}/tokenizer-candidate-comparisons/{comparison_body['public_id']}/approve",
        headers=headers, json={"tokenizer_version_public_id": tokenizer_version_id},
    )
    assert approved_candidate.status_code == 200, approved_candidate.text

    estimate = await client.post(
        f"{PR}/resource-estimates", headers=headers,
        json={"profile_name": "micro_smoke_test", "vocabulary_size": 2000},
    )
    assert estimate.status_code == 200, estimate.text
    estimate_body = estimate.json()
    assert bool(estimate_body["within_safe_limit"])
    assert 500_000 <= estimate_body["parameter_count"] <= 5_000_000

    snapshot = await client.post(
        f"{PR}/dataset-snapshots", headers=headers,
        json={
            "corpus_release_public_id": release["release_id"],
            "tokenizer_version_public_id": tokenizer_version_id,
            "maximum_sequence_length": 64,
        },
    )
    assert snapshot.status_code == 200, snapshot.text
    snapshot_body = snapshot.json()
    assert snapshot_body["train_record_count"] > 0

    validation = await client.post(
        f"{PR}/training-config/validate", headers=headers,
        json={
            "pretraining_dataset_snapshot_public_id": snapshot_body["public_id"],
            "base_model_resource_estimate_public_id": estimate_body["public_id"],
            "configuration": {"total_steps": 6, "sequence_length": 64},
        },
    )
    assert validation.status_code == 200, validation.text
    assert validation.json()["status"] in ("pass", "pass_with_warnings")

    smoke_run = await client.post(
        f"{PR}/smoke-runs", headers=headers,
        json={
            "pretraining_dataset_snapshot_public_id": snapshot_body["public_id"],
            "base_model_resource_estimate_public_id": estimate_body["public_id"],
            "total_steps": 6,
        },
    )
    assert smoke_run.status_code == 200, smoke_run.text
    smoke_body = smoke_run.json()
    assert smoke_body["status"] in ("completed", "completed_with_warnings"), smoke_body
    assert bool(smoke_body["resume_verified"])
    assert smoke_body["checkpoint_checksum_sha256"]
    assert smoke_body["degeneration_findings"] == []

    readiness = await client.post(
        f"{PR}/readiness-evaluations", headers=headers,
        json={
            "pretraining_dataset_snapshot_public_id": snapshot_body["public_id"],
            "tokenizer_candidate_comparison_public_id": comparison_body["public_id"],
            "base_model_resource_estimate_public_id": estimate_body["public_id"],
            "pretraining_smoke_run_public_id": smoke_body["public_id"],
        },
    )
    assert readiness.status_code == 200, readiness.text
    readiness_body = readiness.json()
    assert readiness_body["overall_result"] in (
        "not_ready", "ready_for_experimental_pretraining", "ready_for_bounded_pretraining"
    )
    assert len(readiness_body["dimensions"]) == 17

    fetched_readiness = await client.get(
        f"{PR}/readiness-evaluations/{readiness_body['public_id']}", headers=headers
    )
    assert fetched_readiness.status_code == 200
    assert fetched_readiness.json()["overall_result"] == readiness_body["overall_result"]

    # Public chatbot must remain unaffected by any of the above.
    chat = await client.post("/api/chat", json={"message": "hello"})
    assert chat.status_code == 200
    assert chat.json()["model"] == "placeholder"


async def test_phase21a_mutations_require_csrf(api_app: FastAPI):
    from httpx import ASGITransport, AsyncClient

    AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
        AdminCreate(
            username="phase21a-admin-2", display_name="Phase 21A Admin 2", password=PASSWORD
        )
    )
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    login = await client.post(
        "/api/admin/auth/login", json={"username": "phase21a-admin-2", "password": PASSWORD}
    )
    assert login.status_code == 200
    response = await client.post(
        f"{PR}/tokenizer-corpus-builds", json={"corpus_release_public_id": "does-not-matter"}
    )
    assert response.status_code in (401, 403)
    await client.aclose()


async def test_phase21a_mutations_require_authentication(api_app: FastAPI):
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    response = await client.post(
        f"{PR}/tokenizer-corpus-builds", json={"corpus_release_public_id": "does-not-matter"}
    )
    assert response.status_code in (401, 403)
    await client.aclose()
