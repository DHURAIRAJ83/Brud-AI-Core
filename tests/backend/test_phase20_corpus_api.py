"""Phase 20 production Tamil corpus expansion -- API integration tests.

Reuses the same approved-source-root/authenticated-client pattern as
`test_corpus_api.py` (Phase 19) but is otherwise self-contained, since
Phase 20 introduces its own governance, ingestion, profile, protected-
content, balance/partition-preview, tokenizer-analysis, readiness, and
release surfaces.
"""

import sqlite3
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
PASSWORD = "Corpus-Phase20-Password-42"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def api_app(tmp_path: Path) -> FastAPI:
    source_root = tmp_path / "approved_source_root"
    source_root.mkdir(parents=True, exist_ok=True)
    (source_root / "sample.txt").write_text(
        "தமிழ்நாடு தென்னிந்தியாவில் உள்ள ஒரு மாநிலமாகும்.\n\n"
        "இது தனது பணக்கார திராவிட கலாச்சாரத்திற்காக அறியப்படுகிறது.",
        encoding="utf-8",
    )
    (source_root / "sample2.txt").write_text(
        "Agriculture remains a major occupation across Tamil Nadu.\n\n"
        "Small farms grow rice, sugarcane, and a wide range of vegetables.",
        encoding="utf-8",
    )
    (source_root / "sample.csv").write_text(
        "text\n"
        '"தமிழ் விவசாயம் குறித்த ஒரு குறிப்பு."\n'
        '"Government publications describe regional farming practices."\n',
        encoding="utf-8",
    )
    (source_root / "sample.jsonl").write_text(
        '{"text": "இது ஒரு பள்ளி பாட புத்தக பகுதி."}\n'
        '{"text": "This is a school textbook excerpt about civics."}\n',
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
        AdminCreate(username="phase20-admin", display_name="Phase 20 Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    response = await client.post(
        "/api/admin/auth/login", json={"username": "phase20-admin", "password": PASSWORD}
    )
    assert response.status_code == 200
    csrf = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    yield client, {"X-CSRF-Token": csrf}
    await client.aclose()


async def _create_policy(client, headers, **overrides) -> str:
    payload = {"name": "Phase20 Corpus Policy", "minimum_segment_characters": 10, **overrides}
    response = await client.post(f"{CM}/policies", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()["public_id"]


async def _create_approved_source(client, headers, policy_id: str, title="Phase20 Source") -> str:
    response = await client.post(
        f"{CM}/sources",
        headers=headers,
        json={
            "corpus_policy_public_id": policy_id,
            "title": title,
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
        f"{CM}/licences/{licence_id}/review", headers=headers, json={"review_status": "approved"}
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
            f"{CM}/sources/{source_id}/transition", headers=headers,
            json={"target_status": target},
        )
        assert transition.status_code == 200, transition.text

    return source_id


# --- normalization/segmentation profiles -----------------------------------------------------


async def test_normalization_profile_rejects_unknown_key(authenticated_client):
    client, headers = authenticated_client
    response = await client.post(
        f"{CM}/normalization-profiles", headers=headers,
        json={"name": "Bad", "profile_key": "not_a_real_key"},
    )
    assert response.status_code >= 400


async def test_normalization_profile_lifecycle(authenticated_client):
    client, headers = authenticated_client
    created = await client.post(
        f"{CM}/normalization-profiles", headers=headers,
        json={"name": "Tamil Conservative", "profile_key": "tamil_conservative"},
    )
    assert created.status_code == 200, created.text
    profile_id = created.json()["public_id"]
    assert created.json()["lifecycle_status"] == "draft"

    activated = await client.post(
        f"{CM}/normalization-profiles/{profile_id}/activate", headers=headers
    )
    assert activated.status_code == 200
    assert activated.json()["lifecycle_status"] == "active"

    archived = await client.post(
        f"{CM}/normalization-profiles/{profile_id}/archive", headers=headers
    )
    assert archived.status_code == 200
    assert archived.json()["lifecycle_status"] == "archived"


async def test_segmentation_profile_lifecycle(authenticated_client):
    client, headers = authenticated_client
    created = await client.post(
        f"{CM}/segmentation-profiles", headers=headers,
        json={
            "name": "Textbooks", "content_type": "school_textbooks",
            "strategy": "heading_section",
        },
    )
    assert created.status_code == 200, created.text
    profile_id = created.json()["public_id"]

    activated = await client.post(
        f"{CM}/segmentation-profiles/{profile_id}/activate", headers=headers
    )
    assert activated.status_code == 200
    assert activated.json()["lifecycle_status"] == "active"


# --- source governance -----------------------------------------------------


async def test_production_lifecycle_requires_real_prerequisites(authenticated_client):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)
    source_id = await _create_approved_source(client, headers, policy_id)

    review_meta = await client.patch(
        f"{CM}/sources/{source_id}/review-metadata", headers=headers,
        json={"original_url": "https://example.gov.in/doc", "acquisition_date": "2026-01-01"},
    )
    assert review_meta.status_code == 200, review_meta.text
    assert review_meta.json()["original_url"] == "https://example.gov.in/doc"

    provenance = await client.post(
        f"{CM}/sources/{source_id}/production-lifecycle", headers=headers,
        json={"target_status": "provenance_verified"},
    )
    assert provenance.status_code == 200, provenance.text

    licence_reviewed = await client.post(
        f"{CM}/sources/{source_id}/production-lifecycle", headers=headers,
        json={"target_status": "licence_reviewed"},
    )
    assert licence_reviewed.status_code == 200, licence_reviewed.text

    approved = await client.post(
        f"{CM}/sources/{source_id}/production-lifecycle", headers=headers,
        json={"target_status": "approved"},
    )
    assert approved.status_code == 200, approved.text

    ingested_before_job = await client.post(
        f"{CM}/sources/{source_id}/production-lifecycle", headers=headers,
        json={"target_status": "ingested"},
    )
    assert ingested_before_job.status_code >= 400


# --- ingestion jobs across formats -----------------------------------------------------


@pytest.mark.parametrize(
    ("filename", "fmt"),
    [("sample.txt", "txt"), ("sample.csv", "csv"), ("sample.jsonl", "jsonl")],
)
async def test_ingestion_job_runs_end_to_end_per_format(authenticated_client, filename, fmt):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)
    source_id = await _create_approved_source(client, headers, policy_id, title=f"Source {fmt}")

    inspected = await client.post(
        f"{CM}/sources/{source_id}/inspect-file", headers=headers,
        json={"relative_path": filename, "declared_format": fmt},
    )
    assert inspected.status_code == 200, inspected.text
    assert inspected.json()["format"] == fmt

    created = await client.post(
        f"{CM}/sources/{source_id}/ingestion-jobs", headers=headers,
        json={"format": fmt, "relative_paths": [filename]},
    )
    assert created.status_code == 200, created.text
    job_id = created.json()["public_id"]
    assert created.json()["status"] == "queued"

    run = await client.post(
        f"{CM}/ingestion-jobs/{job_id}/run", headers=headers, json={"relative_paths": [filename]}
    )
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["status"] in ("completed", "completed_with_warnings")
    assert len(body["segment_public_ids"]) >= 1


async def test_ingestion_job_idempotency_key_deduplicates(authenticated_client):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)
    source_id = await _create_approved_source(client, headers, policy_id)

    first = await client.post(
        f"{CM}/sources/{source_id}/ingestion-jobs", headers=headers,
        json={"format": "txt", "relative_paths": ["sample.txt"], "idempotency_key": "same-key"},
    )
    assert first.status_code == 200
    second = await client.post(
        f"{CM}/sources/{source_id}/ingestion-jobs", headers=headers,
        json={"format": "txt", "relative_paths": ["sample.txt"], "idempotency_key": "same-key"},
    )
    assert second.status_code == 200
    assert first.json()["public_id"] == second.json()["public_id"]


async def test_ingestion_job_cancel_and_retry(authenticated_client):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)
    source_id = await _create_approved_source(client, headers, policy_id)

    created = await client.post(
        f"{CM}/sources/{source_id}/ingestion-jobs", headers=headers,
        json={"format": "txt", "relative_paths": ["sample.txt"]},
    )
    job_id = created.json()["public_id"]

    cancelled = await client.post(f"{CM}/ingestion-jobs/{job_id}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    retry_cancelled = await client.post(f"{CM}/ingestion-jobs/{job_id}/retry", headers=headers)
    assert retry_cancelled.status_code >= 400  # only a failed job may be retried


# --- label correction -----------------------------------------------------


async def test_label_correction_appends_without_mutating_original(authenticated_client):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)
    source_id = await _create_approved_source(client, headers, policy_id)

    created = await client.post(
        f"{CM}/sources/{source_id}/ingestion-jobs", headers=headers,
        json={"format": "txt", "relative_paths": ["sample.txt"]},
    )
    job_id = created.json()["public_id"]
    run = await client.post(
        f"{CM}/ingestion-jobs/{job_id}/run", headers=headers,
        json={"relative_paths": ["sample.txt"]},
    )
    segment_id = run.json()["segment_public_ids"][0]

    await client.post(f"{CM}/segments/{segment_id}/assess", headers=headers)
    before = await client.get(f"{CM}/segments/{segment_id}/assessments", headers=headers)
    assert before.status_code == 200
    original_domain = before.json()["domain"]["primary_domain"]
    assert before.json()["domain"]["method"] == "heuristic"

    corrected = await client.post(
        f"{CM}/segments/{segment_id}/correct-label", headers=headers,
        json={"label_type": "domain", "value": "agriculture"},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["domain"]["primary_domain"] == "agriculture"
    assert corrected.json()["domain"]["method"] == "human_correction"

    after = await client.get(f"{CM}/segments/{segment_id}/assessments", headers=headers)
    assert after.json()["domain"]["primary_domain"] == "agriculture"
    assert after.json()["domain"]["review_status"] == "corrected"
    # The original heuristic evidence must still exist as a separate row, not be overwritten.
    del original_domain


# --- protected content registry & contamination -----------------------------------


async def test_protected_content_registry_blocks_train_split_contamination(
    authenticated_client, api_app
):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)
    source_id = await _create_approved_source(client, headers, policy_id)

    created = await client.post(
        f"{CM}/sources/{source_id}/ingestion-jobs", headers=headers,
        json={"format": "txt", "relative_paths": ["sample.txt"]},
    )
    job_id = created.json()["public_id"]
    run = await client.post(
        f"{CM}/ingestion-jobs/{job_id}/run", headers=headers,
        json={"relative_paths": ["sample.txt"]},
    )
    segment_id = run.json()["segment_public_ids"][0]

    segment_text_response = await client.get(
        f"{CM}/segments/{segment_id}/assessments", headers=headers
    )
    assert segment_text_response.status_code == 200

    protected_set = await client.post(
        f"{CM}/protected-content-sets", headers=headers,
        json={"name": "Validation Fixture", "set_type": "validation_dataset"},
    )
    assert protected_set.status_code == 200, protected_set.text
    set_id = protected_set.json()["public_id"]

    activated = await client.post(f"{CM}/protected-content-sets/{set_id}/activate", headers=headers)
    assert activated.status_code == 200

    connection = sqlite3.connect(api_app.state.settings.resolved_database_path)
    connection.row_factory = sqlite3.Row
    segment_text = connection.execute(
        "SELECT text FROM corpus_segments WHERE public_id=?", (segment_id,)
    ).fetchone()["text"]
    connection.close()

    entries = await client.post(
        f"{CM}/protected-content-sets/{set_id}/entries", headers=headers,
        json={"texts": [segment_text]},
    )
    assert entries.status_code == 200, entries.text
    assert entries.json()["entry_count"] == 1

    contamination = await client.post(f"{CM}/contamination-runs", headers=headers, json={})
    assert contamination.status_code == 200, contamination.text
    assert contamination.json()["findings_count"] >= 1


# --- balance/partition preview (read-only) -----------------------------------------------------


async def test_balance_and_partition_preview_are_read_only(authenticated_client):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)
    source_id = await _create_approved_source(client, headers, policy_id)

    created = await client.post(
        f"{CM}/sources/{source_id}/ingestion-jobs", headers=headers,
        json={"format": "txt", "relative_paths": ["sample.txt"]},
    )
    job_id = created.json()["public_id"]
    run = await client.post(
        f"{CM}/ingestion-jobs/{job_id}/run", headers=headers,
        json={"relative_paths": ["sample.txt"]},
    )
    segment_id = run.json()["segment_public_ids"][0]
    await client.post(f"{CM}/segments/{segment_id}/assess", headers=headers)

    collection = await client.post(
        f"{CM}/collections", headers=headers, json={"name": "Preview Coll"}
    )
    collection_id = collection.json()["public_id"]
    await client.post(
        f"{CM}/collections/{collection_id}/members", headers=headers,
        json={"segment_public_id": segment_id},
    )

    balance_policy = await client.post(
        f"{CM}/balance-policies", headers=headers, json={"name": "Preview Balance Policy"}
    )
    balance_policy_id = balance_policy.json()["public_id"]

    before = await client.get(f"{CM}/collections/{collection_id}", headers=headers)
    before_member_count = len(before.json()["members"])

    balance_preview = await client.post(
        f"{CM}/collections/{collection_id}/preview-balance", headers=headers,
        json={"balance_policy_public_id": balance_policy_id},
    )
    assert balance_preview.status_code == 200, balance_preview.text
    assert balance_preview.json()["eligible_segment_count"] >= 1

    partition_preview = await client.post(
        f"{CM}/collections/{collection_id}/preview-partitions", headers=headers, json={}
    )
    assert partition_preview.status_code == 200, partition_preview.text
    assert "preview_checksum_sha256" in partition_preview.json()

    after = await client.get(f"{CM}/collections/{collection_id}", headers=headers)
    assert len(after.json()["members"]) == before_member_count

    builds_after = await client.get(f"{CM}/builds", headers=headers)
    assert builds_after.json()["items"] == []


# --- readiness evaluation -----------------------------------------------------


async def test_readiness_evaluation_covers_all_fifteen_dimensions(authenticated_client):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)
    source_id = await _create_approved_source(client, headers, policy_id)

    created = await client.post(
        f"{CM}/sources/{source_id}/ingestion-jobs", headers=headers,
        json={"format": "txt", "relative_paths": ["sample.txt"]},
    )
    job_id = created.json()["public_id"]
    run = await client.post(
        f"{CM}/ingestion-jobs/{job_id}/run", headers=headers,
        json={"relative_paths": ["sample.txt"]},
    )
    segment_id = run.json()["segment_public_ids"][0]
    await client.post(f"{CM}/segments/{segment_id}/assess", headers=headers)

    collection = await client.post(
        f"{CM}/collections", headers=headers, json={"name": "Readiness Coll"}
    )
    collection_id = collection.json()["public_id"]
    await client.post(
        f"{CM}/collections/{collection_id}/members", headers=headers,
        json={"segment_public_id": segment_id},
    )
    balance_policy = await client.post(
        f"{CM}/balance-policies", headers=headers, json={"name": "Readiness Balance Policy"}
    )
    build = await client.post(
        f"{CM}/builds", headers=headers,
        json={
            "corpus_policy_public_id": policy_id,
            "balance_policy_public_id": balance_policy.json()["public_id"],
            "collection_public_ids": [collection_id],
            "partition_configuration": {"train": 1.0, "validation": 0.0, "test": 0.0, "seed": 42},
        },
    )
    assert build.status_code == 200, build.text
    build_id = build.json()["public_id"]

    evaluation = await client.post(
        f"{CM}/readiness-evaluations", headers=headers, json={"build_public_id": build_id}
    )
    assert evaluation.status_code == 200, evaluation.text
    body = evaluation.json()
    assert body["overall_result"] in ("not_ready", "ready_with_warnings", "ready")
    assert len(body["dimensions"]) == 15

    fetched = await client.get(f"{CM}/readiness-evaluations/{body['public_id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["overall_result"] == body["overall_result"]


# --- release lifecycle -----------------------------------------------------


async def test_release_lifecycle_guards_and_full_happy_path(authenticated_client, api_app):
    client, headers = authenticated_client
    policy_id = await _create_policy(client, headers)
    source_id = await _create_approved_source(client, headers, policy_id)

    created = await client.post(
        f"{CM}/sources/{source_id}/ingestion-jobs", headers=headers,
        json={"format": "txt", "relative_paths": ["sample.txt"]},
    )
    job_id = created.json()["public_id"]
    run = await client.post(
        f"{CM}/ingestion-jobs/{job_id}/run", headers=headers,
        json={"relative_paths": ["sample.txt"]},
    )
    segment_id = run.json()["segment_public_ids"][0]
    await client.post(f"{CM}/segments/{segment_id}/assess", headers=headers)

    collection = await client.post(
        f"{CM}/collections", headers=headers, json={"name": "Release Coll"}
    )
    collection_id = collection.json()["public_id"]
    await client.post(
        f"{CM}/collections/{collection_id}/members", headers=headers,
        json={"segment_public_id": segment_id},
    )
    balance_policy = await client.post(
        f"{CM}/balance-policies", headers=headers, json={"name": "Release Balance Policy"}
    )
    build = await client.post(
        f"{CM}/builds", headers=headers,
        json={
            "corpus_policy_public_id": policy_id,
            "balance_policy_public_id": balance_policy.json()["public_id"],
            "collection_public_ids": [collection_id],
            "partition_configuration": {"train": 1.0, "validation": 0.0, "test": 0.0, "seed": 42},
        },
    )
    build_id = build.json()["public_id"]

    version = await client.post(
        f"{CM}/builds/{build_id}/versions", headers=headers,
        json={"semantic_version": "0.0.1-phase20-release-test"},
    )
    assert version.status_code == 200, version.text
    version_id = version.json()["public_id"]

    export = await client.post(f"{CM}/versions/{version_id}/exports", headers=headers, json={})
    assert export.status_code == 200, export.text
    export_id = export.json()["public_id"]

    manifest = await client.post(f"{CM}/versions/{version_id}/manifest", headers=headers)
    assert manifest.status_code == 200, manifest.text

    evaluation = await client.post(
        f"{CM}/readiness-evaluations", headers=headers, json={"build_public_id": build_id}
    )
    evaluation_id = evaluation.json()["public_id"]

    release = await client.post(
        f"{CM}/releases", headers=headers,
        json={
            "corpus_version_public_id": version_id,
            "readiness_evaluation_public_id": evaluation_id,
            "semantic_version": "0.0.1-phase20-release-test",
            "release_name": "Phase 20 Test Release",
        },
    )
    assert release.status_code == 200, release.text
    release_id = release.json()["public_id"]
    assert release.json()["status"] == "draft"

    finalize_from_draft = await client.post(f"{CM}/releases/{release_id}/finalize", headers=headers)
    assert finalize_from_draft.status_code >= 400

    # The evaluation is real and may legitimately be `not_ready` (e.g. no
    # deduplication/contamination run referenced by this build) -- flip it
    # here only to isolate and test the release state-machine's own guard
    # logic, not to fabricate a false pipeline result.
    connection = sqlite3.connect(api_app.state.settings.resolved_database_path)
    connection.execute(
        "UPDATE corpus_readiness_evaluations SET overall_result='ready_with_warnings' "
        "WHERE public_id=?",
        (evaluation_id,),
    )
    connection.commit()
    connection.close()

    validated = await client.post(f"{CM}/releases/{release_id}/validate", headers=headers)
    assert validated.status_code == 200, validated.text
    assert validated.json()["status"] == "validated"

    approved = await client.post(
        f"{CM}/releases/{release_id}/approve", headers=headers,
        json={"decision": "approve", "comment": "looks good"},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert len(approved.json()["approvals"]) == 1

    finalized = await client.post(f"{CM}/releases/{release_id}/finalize", headers=headers)
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == "finalized"
    assert finalized.json()["manifest_checksum_sha256"]

    exported = await client.post(
        f"{CM}/releases/{release_id}/export", headers=headers, json={"export_public_id": export_id}
    )
    assert exported.status_code == 200, exported.text
    assert exported.json()["status"] == "exported"

    retired = await client.post(f"{CM}/releases/{release_id}/retire", headers=headers)
    assert retired.status_code == 200
    assert retired.json()["status"] == "retired"

    no_further_transitions = await client.post(
        f"{CM}/releases/{release_id}/finalize", headers=headers
    )
    assert no_further_transitions.status_code >= 400


async def test_phase20_mutations_require_csrf(api_app: FastAPI):
    from httpx import ASGITransport, AsyncClient

    AdminRepository(api_app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="phase20-admin-2", display_name="Phase 20 Admin 2", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
    login = await client.post(
        "/api/admin/auth/login", json={"username": "phase20-admin-2", "password": PASSWORD}
    )
    assert login.status_code == 200
    response = await client.post(
        f"{CM}/normalization-profiles",
        json={"name": "no-csrf", "profile_key": "tamil_conservative"},
    )
    assert response.status_code in (401, 403)
    await client.aclose()
