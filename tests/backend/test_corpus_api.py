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
PASSWORD = "Corpus-Admin-Password-42"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    source_root = tmp_path / "approved_source_root"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "sample_en.txt").write_text(
        "Tamil Nadu is a state in southern India known for its rich Dravidian culture.\n\n"
        "Agriculture remains a major occupation across the region.",
        encoding="utf-8",
    )
    (source_root / "sample_ta.txt").write_text(
        "தமிழ்நாடு தென்னிந்தியாவில் உள்ள ஒரு மாநிலமாகும்.\n\n"
        "இது தனது பணக்கார திராவிட கலாச்சாரத்திற்காக அறியப்படுகிறது.",
        encoding="utf-8",
    )
    (source_root / "sample_history.txt").write_text(
        "The history of South Indian temple architecture spans over a thousand years.\n\n"
        "Successive dynasties contributed distinct sculptural styles across centuries.",
        encoding="utf-8",
    )
    (source_root / "sample_science.txt").write_text(
        "Photosynthesis converts sunlight into chemical energy stored in glucose.\n\n"
        "Plants use chlorophyll pigments to absorb light for this biological process.",
        encoding="utf-8",
    )
    (source_root / "duplicate_of_en.txt").write_text(
        (source_root / "sample_en.txt").read_text(encoding="utf-8"), encoding="utf-8"
    )
    (source_root / "near_duplicate_of_en.txt").write_text(
        "Tamil Nadu is a state in southern India known for its rich Dravidian culture!\n\n"
        "Agriculture remains a major occupation across the region and beyond.",
        encoding="utf-8",
    )
    (source_root / "sample_business.txt").write_text(
        "Small businesses in Tamil Nadu often rely on local supply chains.\n\n"
        "Marketing strategies increasingly use regional language content.",
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
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    return create_app(settings)


@pytest.fixture
async def authenticated_client(api_app: FastAPI):
    from httpx import ASGITransport, AsyncClient

    AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="corpus-admin", display_name="Corpus Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "corpus-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    yield client, {"X-CSRF-Token": csrf}
    await client.aclose()


async def _create_policy(client, headers, **overrides) -> str:
    payload = {"name": "Test Corpus Policy", "minimum_segment_characters": 20, **overrides}
    response = await client.post(f"{CM}/policies", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["public_id"]


async def _create_approved_source(client, headers, policy_id: str) -> str:
    response = await client.post(
        f"{CM}/sources",
        headers=headers,
        json={
            "corpus_policy_public_id": policy_id,
            "title": "Hand-composed test corpus",
            "source_type": "manual_admin_text",
            "ownership_claim": "admin_authored",
        },
    )
    assert response.status_code == 200, response.text
    source_id = response.json()["public_id"]

    licence_response = await client.post(
        f"{CM}/sources/{source_id}/licences",
        headers=headers,
        json={
            "licence_family": "public_domain",
            "copyright_holder": "none",
            "ai_training_permitted": True,
        },
    )
    assert licence_response.status_code == 200, licence_response.text
    licence_id = licence_response.json()["public_id"]
    review = await client.post(
        f"{CM}/licences/{licence_id}/review",
        headers=headers,
        json={"review_status": "approved"},
    )
    assert review.status_code == 200, review.text

    verify = await client.post(
        f"{CM}/sources/{source_id}/verify-origin",
        headers=headers,
        json={"evidence": "hand-authored for automated test"},
    )
    assert verify.status_code == 200, verify.text

    for target in ("origin_review", "licence_review", "approved"):
        transition = await client.post(
            f"{CM}/sources/{source_id}/transition",
            headers=headers,
            json={"target_status": target},
        )
        assert transition.status_code == 200, transition.text

    return source_id


async def _build_full_corpus(client, headers) -> dict:
    policy_id = await _create_policy(client, headers)
    source_id = await _create_approved_source(client, headers, policy_id)

    eligibility = await client.get(
        f"{CM}/sources/{source_id}/training-eligibility", headers=headers
    )
    assert eligibility.status_code == 200
    assert eligibility.json()["eligible"] is True

    snapshot_response = await client.post(
        f"{CM}/sources/{source_id}/snapshots",
        headers=headers,
        json={
            "files": [
                {"relative_path": "sample_en.txt"},
                {"relative_path": "sample_ta.txt"},
                {"relative_path": "sample_history.txt"},
                {"relative_path": "sample_science.txt"},
                {"relative_path": "duplicate_of_en.txt"},
                {"relative_path": "near_duplicate_of_en.txt"},
                {"relative_path": "sample_business.txt"},
            ]
        },
    )
    assert snapshot_response.status_code == 200, snapshot_response.text
    snapshot = snapshot_response.json()
    assert len(snapshot["files"]) == 7

    extraction_response = await client.post(
        f"{CM}/snapshots/{snapshot['public_id']}/extraction-runs",
        headers=headers,
        json={"extraction_method": "plain_text"},
    )
    assert extraction_response.status_code == 200, extraction_response.text
    extraction_run = extraction_response.json()
    assert extraction_run["documents_created"] == 7

    normalization_response = await client.post(
        f"{CM}/extraction-runs/{extraction_run['public_id']}/normalization-runs",
        headers=headers,
        json={},
    )
    assert normalization_response.status_code == 200, normalization_response.text
    normalization_run = normalization_response.json()

    segment_ids = []
    for document in normalization_run["documents"]:
        segment_response = await client.post(
            f"{CM}/normalized-documents/{document['public_id']}/segment",
            headers=headers,
            json={"strategy": "paragraph"},
        )
        assert segment_response.status_code == 200, segment_response.text
        segment_ids.extend(segment_response.json()["segment_public_ids"])

    assert len(segment_ids) >= 6

    for segment_id in segment_ids:
        assess_response = await client.post(f"{CM}/segments/{segment_id}/assess", headers=headers)
        assert assess_response.status_code == 200, assess_response.text

    return {
        "policy_id": policy_id,
        "source_id": source_id,
        "snapshot_id": snapshot["public_id"],
        "segment_ids": segment_ids,
    }


async def test_full_corpus_pipeline_source_to_export(authenticated_client):
    client, headers = authenticated_client
    corpus = await _build_full_corpus(client, headers)

    dedup_response = await client.post(
        f"{CM}/deduplication-runs",
        headers=headers,
        json={"near_duplicate_method": "character_ngram_jaccard", "near_duplicate_threshold": 0.7},
    )
    assert dedup_response.status_code == 200, dedup_response.text
    dedup = dedup_response.json()
    assert dedup["exact_duplicate_count"] >= 1
    assert dedup["near_duplicate_count"] >= 1

    contamination_response = await client.post(
        f"{CM}/contamination-runs",
        headers=headers,
        json={"test_fixture_texts": ["a held out evaluation-only sentence"]},
    )
    assert contamination_response.status_code == 200, contamination_response.text

    collection_response = await client.post(
        f"{CM}/collections", headers=headers, json={"name": "Test Collection"}
    )
    assert collection_response.status_code == 200, collection_response.text
    collection_id = collection_response.json()["public_id"]

    for segment_id in corpus["segment_ids"]:
        member_response = await client.post(
            f"{CM}/collections/{collection_id}/members",
            headers=headers,
            json={"segment_public_id": segment_id},
        )
        assert member_response.status_code == 200, member_response.text

    collection_detail = await client.get(f"{CM}/collections/{collection_id}", headers=headers)
    assert collection_detail.status_code == 200
    assert len(collection_detail.json()["members"]) == len(corpus["segment_ids"])

    balance_response = await client.post(
        f"{CM}/balance-policies",
        headers=headers,
        json={"name": "Test Balance Policy", "maximum_single_source_share": 1.0},
    )
    assert balance_response.status_code == 200, balance_response.text
    balance_policy_id = balance_response.json()["public_id"]

    build_response = await client.post(
        f"{CM}/builds",
        headers=headers,
        json={
            "corpus_policy_public_id": corpus["policy_id"],
            "balance_policy_public_id": balance_policy_id,
            "collection_public_ids": [collection_id],
            "partition_configuration": {
                "train": 1.0,
                "validation": 0.0,
                "test": 0.0,
                "seed": 42,
            },
        },
    )
    assert build_response.status_code == 200, build_response.text
    build = build_response.json()
    assert build["status"] == "completed"
    assert build["included_segment_count"] > 0

    version_response = await client.post(
        f"{CM}/builds/{build['public_id']}/versions",
        headers=headers,
        json={"semantic_version": "0.1.0-test"},
    )
    assert version_response.status_code == 200, version_response.text
    version = version_response.json()
    assert version["status"] == "ready"

    export_response = await client.post(
        f"{CM}/versions/{version['public_id']}/exports", headers=headers, json={}
    )
    assert export_response.status_code == 200, export_response.text
    export = export_response.json()
    assert export["total_records"] > 0
    assert export["notice"]

    manifest_response = await client.post(
        f"{CM}/versions/{version['public_id']}/manifest", headers=headers
    )
    assert manifest_response.status_code == 200, manifest_response.text
    manifest = manifest_response.json()
    assert manifest["manifest_checksum_sha256"]

    # Public API surface must never expose absolute filesystem paths.
    export_body = str(export)
    assert str(client._transport.app.state.settings.resolved_corpus_export_dir) not in export_body


async def test_snapshot_rejects_path_outside_approved_roots(authenticated_client):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)
    source_response = await client.post(
        f"{CM}/sources",
        headers=headers,
        json={
            "corpus_policy_public_id": policy_id,
            "title": "Untrusted source",
            "source_type": "manual_admin_text",
        },
    )
    source_id = source_response.json()["public_id"]

    response = await client.post(
        f"{CM}/sources/{source_id}/snapshots",
        headers=headers,
        json={"files": [{"relative_path": "../../etc/passwd"}]},
    )
    assert response.status_code >= 400


async def test_unknown_licence_blocks_training_eligibility(authenticated_client):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)
    source_response = await client.post(
        f"{CM}/sources",
        headers=headers,
        json={
            "corpus_policy_public_id": policy_id,
            "title": "Unreviewed source",
            "source_type": "manual_admin_text",
        },
    )
    source_id = source_response.json()["public_id"]
    await client.post(
        f"{CM}/sources/{source_id}/licences",
        headers=headers,
        json={"licence_family": "unknown"},
    )
    for target in ("origin_review", "licence_review", "approved"):
        await client.post(
            f"{CM}/sources/{source_id}/transition",
            headers=headers,
            json={"target_status": target},
        )

    eligibility = await client.get(
        f"{CM}/sources/{source_id}/training-eligibility", headers=headers
    )
    assert eligibility.status_code == 200
    body = eligibility.json()
    assert body["eligible"] is False
    assert "ai_training_permission_absent" in body["blocking_reasons"]


async def test_policy_validate_activate_lifecycle(authenticated_client):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)

    created = await client.get(f"{CM}/policies/{policy_id}", headers=headers)
    assert created.json()["lifecycle_status"] == "draft"

    activate_before_validate = await client.post(
        f"{CM}/policies/{policy_id}/activate", headers=headers
    )
    assert activate_before_validate.status_code >= 400

    validated = await client.post(f"{CM}/policies/{policy_id}/validate", headers=headers)
    assert validated.status_code == 200, validated.text
    assert validated.json()["lifecycle_status"] == "validated"

    activated = await client.post(f"{CM}/policies/{policy_id}/activate", headers=headers)
    assert activated.status_code == 200, activated.text
    assert activated.json()["lifecycle_status"] == "active"


async def test_mutations_require_csrf(api_app: FastAPI):
    from httpx import ASGITransport, AsyncClient

    AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="corpus-admin-2", display_name="Corpus Admin 2", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    login = await client.post(
        "/api/admin/auth/login", json={"username": "corpus-admin-2", "password": PASSWORD}
    )
    assert login.status_code == 200
    response = await client.post(f"{CM}/policies", json={"name": "no-csrf"})
    assert response.status_code in (401, 403)
    await client.aclose()


async def test_mutations_require_authentication(api_app: FastAPI):
    from httpx import ASGITransport, AsyncClient

    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    response = await client.post(f"{CM}/policies", json={"name": "anonymous"})
    assert response.status_code in (401, 403)
    await client.aclose()
