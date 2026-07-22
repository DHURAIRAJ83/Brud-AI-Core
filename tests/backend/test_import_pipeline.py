import json

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.core.config import Settings
from backend.database.connection import database_connection
from backend.database.migrations import initialize_database
from backend.database.repositories.admin import AdminRepository
from backend.database.repositories.base import ValidationError
from backend.main import create_app
from backend.models.auth import AdminCreate
from backend.services.import_service import _formula_safe, _safe_filename

pytestmark = pytest.mark.anyio
PASSWORD = "Import-Pipeline-Password-42"


async def client_and_csrf(app: FastAPI):
    AdminRepository(app.state.settings.resolved_database_path).create_admin(
        AdminCreate(username="import-admin", display_name="Import Admin", password=PASSWORD)
    )
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")
    assert (
        await client.post(
            "/api/admin/auth/login",
            json={"username": "import-admin", "password": PASSWORD},
        )
    ).status_code == 200
    token = (await client.get("/api/admin/auth/csrf")).json()["csrf_token"]
    return client, {"X-CSRF-Token": token}


async def upload(
    client,
    headers,
    filename: str,
    content: bytes,
    *,
    content_type: str = "application/x-ndjson",
    record_type: str = "instruction",
    language: str = "unknown",
    mode: str = "skip_duplicates",
    mapping: dict | None = None,
    options: dict | None = None,
):
    return await client.post(
        "/api/admin/datasets/imports",
        headers=headers,
        files={"file": (filename, content, content_type)},
        data={
            "record_type": record_type,
            "default_language": language,
            "import_mode": mode,
            "field_mapping_json": json.dumps(mapping or {}),
            "parser_options_json": json.dumps(options or {}),
        },
    )


async def test_jsonl_preview_confirmation_report_and_idempotency(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    mapping = {
        "record_type": "record_type",
        "language": "language",
        "instruction": "instruction",
        "input_text": "input_text",
        "output_text": "output_text",
        "normalized_input": "normalized_input",
    }
    lines = [
        json.dumps(
            {
                "record_type": "instruction",
                "language": "ta",
                "instruction": "வணக்கம் கூறுக",
                "output_text": "வணக்கம்",
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "record_type": "instruction",
                "language": "en",
                "instruction": "Say hello",
                "output_text": "Hello",
            }
        ),
        json.dumps(
            {
                "record_type": "tanglish_pair",
                "language": "tgl",
                "input_text": "vanakkam",
                "normalized_input": "வணக்கம்",
                "output_text": "வணக்கம்",
            },
            ensure_ascii=False,
        ),
        json.dumps(
            {
                "record_type": "instruction",
                "language": "ta",
                "instruction": "வணக்கம் கூறுக",
                "output_text": "வணக்கம்",
            },
            ensure_ascii=False,
        ),
        "{malformed",
        json.dumps({"record_type": "instruction", "language": "en", "instruction": "Missing"}),
    ]
    try:
        unauthenticated = AsyncClient(transport=ASGITransport(app=api_app), base_url="http://test")
        assert (await unauthenticated.get("/api/admin/datasets/imports")).status_code == 401
        await unauthenticated.aclose()
        no_csrf = await upload(client, {}, "sample.jsonl", b"{}\n", mapping=mapping)
        assert no_csrf.status_code == 403
        response = await upload(
            client,
            headers,
            "../sample.jsonl",
            "\n".join(lines).encode(),
            mapping=mapping,
        )
        assert response.status_code == 200
        job = response.json()
        assert job["original_filename"] == "sample.jsonl"
        assert "stored_filename" not in job and "/tmp/" not in response.text
        job_id = job["public_id"]
        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            assert connection.execute("SELECT COUNT(*) FROM dataset_records").fetchone()[0] == 0
        parsed = await client.post(f"/api/admin/datasets/imports/{job_id}/parse", headers=headers)
        assert parsed.status_code == 200
        preview = parsed.json()
        assert preview["total_rows"] == 6
        assert preview["duplicate_rows"] == 1
        assert preview["invalid_rows"] == 2
        rows = (await client.get(f"/api/admin/datasets/imports/{job_id}/rows?page_size=200")).json()
        assert rows["total"] == 6
        assert {item["row_number"] for item in rows["items"]} == {1, 2, 3, 4, 5, 6}
        assert all("id" not in item for item in rows["items"])
        confirmed = await client.post(
            f"/api/admin/datasets/imports/{job_id}/confirm",
            headers=headers,
            json={"confirm": True, "include_warnings": True},
        )
        assert confirmed.status_code == 200
        assert confirmed.json()["status"] == "completed_with_warnings"
        assert confirmed.json()["imported_rows"] == 3
        retry = await client.post(
            f"/api/admin/datasets/imports/{job_id}/confirm",
            headers=headers,
            json={"confirm": True},
        )
        assert retry.status_code == 200 and retry.json()["imported_rows"] == 3
        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            records = connection.execute(
                "SELECT status,COUNT(*) FROM dataset_records GROUP BY status"
            ).fetchall()
        assert [tuple(row) for row in records] == [("draft", 3)]
        events = (await client.get(f"/api/admin/datasets/imports/{job_id}/events")).json()
        names = {item["event_type"] for item in events["items"]}
        assert {"upload_received", "parse_started", "preview_created", "import_completed"} <= names
        report = await client.get(f"/api/admin/datasets/imports/{job_id}/report", headers=headers)
        assert report.status_code == 200 and "text/csv" in report.headers["content-type"]
        assert "invalid_json" in report.text and "/tmp/" not in report.text
    finally:
        await client.aclose()


@pytest.mark.parametrize(
    ("filename", "content_type", "content", "record_type", "mapping", "options", "expected"),
    [
        (
            "rows.json",
            "application/json",
            json.dumps([{"question": "கேள்வி", "answer": "பதில்"}], ensure_ascii=False).encode(),
            "instruction",
            {"instruction": "question", "output_text": "answer"},
            {},
            1,
        ),
        (
            "rows.csv",
            "text/csv",
            "question;answer\nவணக்கம்;நல்வரவு\n".encode(),
            "instruction",
            {"instruction": "question", "output_text": "answer"},
            {"delimiter": "semicolon"},
            1,
        ),
        (
            "rows.txt",
            "text/plain",
            "முதல் வரி\n\nஇரண்டாம் வரி\n".encode(),
            "pretrain",
            {"output_text": "text"},
            {"txt_mode": "one_record_per_line"},
            2,
        ),
        (
            "whole.txt",
            "text/plain",
            "முழு கோப்பு\nஉள்ளடக்கம்".encode(),
            "pretrain",
            {"output_text": "text"},
            {"txt_mode": "whole_file_as_pretrain"},
            1,
        ),
    ],
)
async def test_supported_parsers(
    api_app: FastAPI,
    filename,
    content_type,
    content,
    record_type,
    mapping,
    options,
    expected,
) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        created = await upload(
            client,
            headers,
            filename,
            content,
            content_type=content_type,
            record_type=record_type,
            language="ta",
            mapping=mapping,
            options=options,
        )
        assert created.status_code == 200
        job_id = created.json()["public_id"]
        parsed = await client.post(f"/api/admin/datasets/imports/{job_id}/parse", headers=headers)
        assert parsed.status_code == 200 and parsed.json()["total_rows"] == expected
        rows = (await client.get(f"/api/admin/datasets/imports/{job_id}/rows")).json()
        serialized = json.dumps(rows, ensure_ascii=False)
        assert "வ" in serialized or "ம" in serialized
    finally:
        await client.aclose()


async def test_upload_security_mapping_cancel_and_create_only(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        assert (await upload(client, headers, "bad.exe", b"payload")).status_code == 422
        assert (
            await upload(client, headers, "empty.txt", b"", content_type="text/plain")
        ).status_code == 422
        assert (
            await upload(
                client, headers, "bad.json", b"plain text", content_type="application/json"
            )
        ).status_code == 422
        valid = await upload(
            client,
            headers,
            "cancel.txt",
            b"safe text",
            content_type="text/plain",
            record_type="pretrain",
            language="en",
            mapping={"output_text": "text"},
            options={"txt_mode": "one_record_per_line"},
            mode="create_only",
        )
        job_id = valid.json()["public_id"]
        changed = await client.patch(
            f"/api/admin/datasets/imports/{job_id}/mapping",
            headers=headers,
            json={"field_mapping": {"output_text": "text"}, "default_language": "en"},
        )
        assert changed.status_code == 200
        cancelled = await client.post(
            f"/api/admin/datasets/imports/{job_id}/cancel", headers=headers
        )
        assert cancelled.json()["status"] == "cancelled"
        assert (
            await client.post(f"/api/admin/datasets/imports/{job_id}/parse", headers=headers)
        ).status_code == 409
        listed = (await client.get("/api/admin/datasets/imports?status=cancelled")).json()
        assert listed["total"] == 1 and "stored_filename" not in json.dumps(listed)
    finally:
        await client.aclose()


def test_partial_upload_cleanup_and_limits(api_app: FastAPI) -> None:
    settings = api_app.state.settings
    assert settings.import_max_file_bytes > 0
    pending = settings.resolved_import_dir / "pending"
    assert not pending.exists() or not list(pending.iterdir())


async def test_oversized_upload_is_removed_and_audited(tmp_path) -> None:
    settings = Settings(
        database_path=tmp_path / "small.db",
        database_backup_dir=tmp_path / "backups",
        allowed_data_dir=tmp_path,
        import_dir=tmp_path / "imports",
        import_report_dir=tmp_path / "imports" / "reports",
        import_max_file_bytes=8,
        allow_external_storage=True,
        log_level="CRITICAL",
    )
    initialize_database(settings.resolved_database_path)
    app = create_app(settings)
    client, headers = await client_and_csrf(app)
    try:
        response = await upload(
            client,
            headers,
            "large.txt",
            b"123456789",
            content_type="text/plain",
            record_type="pretrain",
            mapping={"output_text": "text"},
        )
        assert response.status_code == 422
        pending = settings.resolved_import_dir / "pending"
        assert pending.is_dir() and not list(pending.iterdir())
        with database_connection(settings.resolved_database_path) as connection:
            assert (
                connection.execute(
                    """SELECT COUNT(*) FROM audit_logs
                    WHERE event_type='dataset_import_upload_rejected'"""
                ).fetchone()[0]
                == 1
            )
    finally:
        await client.aclose()


async def test_create_only_duplicate_and_expired_preview_are_blocked(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    mapping = {"instruction": "instruction", "output_text": "output"}
    duplicate_lines = (
        b'{"instruction":"Same","output":"Answer"}\n{"instruction":"Same","output":"Answer"}\n'
    )
    try:
        created = await upload(
            client,
            headers,
            "duplicates.jsonl",
            duplicate_lines,
            mapping=mapping,
            language="en",
            mode="create_only",
        )
        job_id = created.json()["public_id"]
        parsed = await client.post(f"/api/admin/datasets/imports/{job_id}/parse", headers=headers)
        assert parsed.json()["duplicate_rows"] == 1
        blocked = await client.post(
            f"/api/admin/datasets/imports/{job_id}/confirm",
            headers=headers,
            json={"confirm": True},
        )
        assert blocked.status_code == 409

        expiring = await upload(
            client,
            headers,
            "expires.txt",
            b"text",
            content_type="text/plain",
            record_type="pretrain",
            language="en",
            mapping={"output_text": "text"},
        )
        expiring_id = expiring.json()["public_id"]
        await client.post(f"/api/admin/datasets/imports/{expiring_id}/parse", headers=headers)
        with database_connection(api_app.state.settings.resolved_database_path) as connection:
            connection.execute(
                """UPDATE dataset_import_jobs SET previewed_at='2000-01-01T00:00:00+00:00'
                WHERE public_id=?""",
                (expiring_id,),
            )
            connection.commit()
        expired = await client.post(
            f"/api/admin/datasets/imports/{expiring_id}/confirm",
            headers=headers,
            json={"confirm": True},
        )
        assert expired.status_code == 409
        assert (await client.get(f"/api/admin/datasets/imports/{expiring_id}")).json()[
            "status"
        ] == "expired"
    finally:
        await client.aclose()


async def test_csv_limits_and_deep_json_fail_safely(api_app: FastAPI) -> None:
    client, headers = await client_and_csrf(api_app)
    try:
        wide = (
            ",".join(f"c{i}" for i in range(51)) + "\n" + ",".join("x" for _ in range(51))
        ).encode()
        created = await upload(
            client,
            headers,
            "wide.csv",
            wide,
            content_type="text/csv",
            record_type="pretrain",
            mapping={"output_text": "c0"},
        )
        parsed = await client.post(
            f"/api/admin/datasets/imports/{created.json()['public_id']}/parse", headers=headers
        )
        assert parsed.status_code == 422 and "row_too_wide" in parsed.text

        nested = value = {}
        for _ in range(12):
            value["nested"] = {}
            value = value["nested"]
        deep = await upload(
            client,
            headers,
            "deep.json",
            json.dumps([nested]).encode(),
            content_type="application/json",
            record_type="pretrain",
            mapping={"output_text": "text"},
        )
        failed = await client.post(
            f"/api/admin/datasets/imports/{deep.json()['public_id']}/parse", headers=headers
        )
        assert failed.status_code == 422
    finally:
        await client.aclose()


def test_filename_and_csv_report_safety_helpers() -> None:
    sanitized = _safe_filename("../../தமிழ் dataset.csv")
    assert "/" not in sanitized and ".." not in sanitized and sanitized.endswith("dataset.csv")
    with pytest.raises(ValidationError):
        _safe_filename("bad\x00.csv")
    assert _formula_safe("=HYPERLINK('bad')").startswith("'")
