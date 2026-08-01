"""Repository for the Phase 9 External Data Provider Registry:
``external_data_providers`` plus its five child tables (domains,
capabilities, credentials, connection tests, events).

Structurally separate from the existing Source & Rights Registry
(``backend/database/repositories/data_sources.py``) and from Phase 15
inference-model routing (``backend/database/repositories/
inference_runtime.py``) -- no table here is ever joined against
``data_sources`` or ``inference_model_assignments``. See
``docs/data_providers/phase9_external_data_provider_registry_plan.md``.

Credentials: this repository never reads or writes a secret value --
only a ``reference_key`` (an environment variable name) and derived
status columns. Resolving whether that environment variable is
actually set is the service layer's job (an impure, non-database
concern), not this repository's.
"""

from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

from backend.core.json_utils import dumps_json, loads_json
from backend.database.repositories.base import BaseRepository, NotFoundError

# A stable, documented "system" actor for rows created by idempotent
# built-in seeding rather than a real admin action -- never a real
# admin's public_id. Mirrors the existing precedent of
# `InferenceRuntimeRepository.ensure_default_scopes()` (Phase 15),
# which also seeds rows without an admin actor.
SYSTEM_SEED_ADMIN_ID = "00000000-0000-0000-0000-000000000000"

# Step 6: seed metadata only -- no credentials, no licences, no dataset
# permissions, no connection results. Every entry starts
# lifecycle_status='draft', trust_status='unverified', enabled=False
# (the table's own column defaults), matching "unknown providers must
# default to disabled and unverified" applied conservatively to every
# seed, not only admin-registered custom providers. The three
# "template" entries (government_portal/university_library/custom_api)
# intentionally seed no domain -- claiming a specific official website
# for an entire category of institutions would be exactly the kind of
# unverifiable claim rule 17 ("do not claim officially verified without
# evidence") forbids; an admin fills in the real domain for their own
# specific portal/institution when they use the template.
_BUILTIN_PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        "provider_code": "ai4bharat",
        "name": "AI4Bharat",
        "provider_type": "research_institution",
        "description": (
            "IIT Madras research initiative for Indic-language AI datasets and tools. "
            "Catalogue and manual discovery only -- individual dataset licences vary and "
            "must be checked per dataset before any use."
        ),
        "official_website": "https://ai4bharat.org",
        "catalogue_url": "https://ai4bharat.org/",
        "access_mode": "mixed",
        "authentication_type": "none",
        "supports_anonymous_read": 1,
        "supports_manual_discovery": 1,
        "domains": (("ai4bharat.org", "official"),),
        "capabilities": ("read_metadata",),
    },
    {
        "provider_code": "huggingface",
        "name": "Hugging Face",
        "provider_type": "repository_host",
        "description": (
            "Community model/dataset hosting platform. Public datasets are anonymously "
            "readable; gated/private datasets require a bearer token configured via the "
            "credential-reference model (Step 4) -- never stored as plaintext."
        ),
        "official_website": "https://huggingface.co",
        "catalogue_url": "https://huggingface.co/datasets",
        "access_mode": "mixed",
        "authentication_type": "bearer_token",
        "supports_anonymous_read": 1,
        "supports_authenticated_read": 1,
        "supports_api_search": 1,
        "supports_manual_discovery": 1,
        "domains": (("huggingface.co", "official"),),
        "capabilities": ("search_datasets", "read_dataset_card", "list_files"),
    },
    {
        "provider_code": "github",
        "name": "GitHub",
        "provider_type": "repository_host",
        "description": (
            "Source/repository hosting. Repository metadata, releases, and licence files "
            "only; an authenticated token raises rate limits but is not required for public "
            "repositories."
        ),
        "official_website": "https://github.com",
        "catalogue_url": None,
        "access_mode": "mixed",
        "authentication_type": "bearer_token",
        "supports_anonymous_read": 1,
        "supports_authenticated_read": 1,
        "supports_api_search": 1,
        "supports_manual_discovery": 1,
        "domains": (("github.com", "official"), ("api.github.com", "api")),
        "capabilities": ("read_metadata", "read_licence", "list_files"),
    },
    {
        "provider_code": "wikimedia",
        "name": "Wikimedia",
        "provider_type": "public_api",
        "description": (
            "Wikimedia Foundation projects (including Wikidata's structured-data API). "
            "Read-only metadata/API access; no authentication required for public content."
        ),
        "official_website": "https://wikimedia.org",
        "catalogue_url": "https://www.wikidata.org",
        "access_mode": "public",
        "authentication_type": "none",
        "supports_anonymous_read": 1,
        "supports_api_search": 1,
        "supports_manual_discovery": 1,
        "domains": (("wikimedia.org", "official"), ("www.wikidata.org", "api")),
        "capabilities": ("read_metadata", "search_datasets"),
    },
    {
        "provider_code": "bhashini",
        "name": "Bhashini",
        "provider_type": "government_portal",
        "description": (
            "India's National Language Translation Mission. Some endpoints require "
            "government-issued API access; this entry records the provider only, never a "
            "dataset licence or training permission."
        ),
        "official_website": "https://bhashini.gov.in",
        "catalogue_url": None,
        "access_mode": "mixed",
        "authentication_type": "api_key",
        "supports_authenticated_read": 1,
        "supports_manual_discovery": 1,
        "domains": (("bhashini.gov.in", "official"),),
        "capabilities": ("read_metadata",),
    },
    {
        "provider_code": "government-open-data-portal",
        "name": "Government Open Data Portal (template)",
        "provider_type": "government_portal",
        "description": (
            "Generic template for a national/state open-data portal -- update the official "
            "website, domains, and capabilities for the specific portal your organization "
            "uses. No specific portal is claimed or verified by this template entry."
        ),
        "official_website": None,
        "catalogue_url": None,
        "access_mode": "manual",
        "authentication_type": "none",
        "supports_manual_discovery": 1,
        "domains": (),
        "capabilities": (),
    },
    {
        "provider_code": "university-research-repository",
        "name": "University / Research Repository (template)",
        "provider_type": "university_library",
        "description": (
            "Generic template for a university or research-institution repository -- update "
            "the official website, domains, and capabilities for the specific institution. "
            "No specific institution is claimed or verified by this template entry."
        ),
        "official_website": None,
        "catalogue_url": None,
        "access_mode": "manual",
        "authentication_type": "none",
        "supports_manual_discovery": 1,
        "domains": (),
        "capabilities": (),
    },
    {
        "provider_code": "custom-provider-template",
        "name": "Custom Provider (template)",
        "provider_type": "custom_api",
        "description": (
            "Starting template for registering a one-off external data provider not covered "
            "by any built-in entry above. Fill in the real name, official website, domains, "
            "and capabilities -- see the Add Provider tab for the full guided form."
        ),
        "official_website": None,
        "catalogue_url": None,
        "access_mode": "manual",
        "authentication_type": "none",
        "supports_manual_discovery": 1,
        "domains": (),
        "capabilities": (),
    },
)


def _provider_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "provider_code": row["provider_code"],
        "name": row["name"],
        "provider_type": row["provider_type"],
        "description": row["description"],
        "official_website": row["official_website"],
        "catalogue_url": row["catalogue_url"],
        "access_mode": row["access_mode"],
        "authentication_type": row["authentication_type"],
        "trust_status": row["trust_status"],
        "lifecycle_status": row["lifecycle_status"],
        "enabled": bool(row["enabled"]),
        "supports_anonymous_read": bool(row["supports_anonymous_read"]),
        "supports_authenticated_read": bool(row["supports_authenticated_read"]),
        "supports_download": bool(row["supports_download"]),
        "supports_api_search": bool(row["supports_api_search"]),
        "supports_manual_discovery": bool(row["supports_manual_discovery"]),
        "supports_write": bool(row["supports_write"]),
        "rate_limit_notes": row["rate_limit_notes"],
        "terms_url": row["terms_url"],
        "privacy_url": row["privacy_url"],
        "support_url": row["support_url"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "archived_at": row["archived_at"],
    }


def _domain_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "provider_public_id": row["provider_public_id"],
        "domain": row["domain"],
        "domain_type": row["domain_type"],
        "verification_status": row["verification_status"],
        "verified_at": row["verified_at"],
        "verification_evidence": row["verification_evidence"],
        "created_at": row["created_at"],
    }


def _capability_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "provider_public_id": row["provider_public_id"],
        "capability_type": row["capability_type"],
        "language_codes": loads_json(row["language_codes_json"]),
        "dataset_categories": loads_json(row["dataset_categories_json"]),
        "connector_type": row["connector_type"],
        "enabled": bool(row["enabled"]),
        "configuration": loads_json(row["configuration_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _credential_public(row: sqlite3.Row) -> dict[str, Any]:
    """Includes ``reference_key`` -- an environment variable *name*,
    never a secret value. Callers exposing this over an API must still
    drop ``reference_key`` per Step 4's contract; kept here because
    internal callers (the connection-test service) need it to resolve
    the actual secret from the environment."""

    return {
        "public_id": row["public_id"],
        "provider_public_id": row["provider_public_id"],
        "credential_type": row["credential_type"],
        "reference_key": row["reference_key"],
        "status": row["status"],
        "last_rotated_at": row["last_rotated_at"],
        "last_tested_at": row["last_tested_at"],
        "created_by_admin_public_id": row["created_by_admin_public_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "revoked_at": row["revoked_at"],
    }


def _connection_test_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "provider_public_id": row["provider_public_id"],
        "result": row["result"],
        "capability_type": row["capability_type"],
        "latency_ms": row["latency_ms"],
        "evidence": loads_json(row["evidence_json"]),
        "error_code": row["error_code"],
        "tested_by_admin_public_id": row["tested_by_admin_public_id"],
        "tested_at": row["tested_at"],
    }


def _event_public(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "public_id": row["public_id"],
        "provider_public_id": row["provider_public_id"],
        "event_type": row["event_type"],
        "summary": row["summary"],
        "metadata": loads_json(row["metadata_json"]),
        "performed_by_admin_public_id": row["performed_by_admin_public_id"],
        "created_at": row["created_at"],
    }


class ExternalDataProviderRepository(BaseRepository):
    # -- built-in seeding (Step 6) ----------------------------------------

    def ensure_builtin_providers(self, connection: sqlite3.Connection) -> None:
        """Idempotently seeds the 8 built-in providers (5 real, 3
        clearly-labeled templates) the first time providers are listed
        -- mirrors `InferenceRuntimeRepository.ensure_default_scopes()`
        (Phase 15). Metadata only: no credentials, no licences, no
        connection-test results are ever seeded."""

        for spec in _BUILTIN_PROVIDERS:
            existing = connection.execute(
                "SELECT id FROM external_data_providers WHERE provider_code=?",
                (spec["provider_code"],),
            ).fetchone()
            if existing:
                continue
            public_id = str(uuid4())
            connection.execute(
                """INSERT INTO external_data_providers(
                public_id, provider_code, name, provider_type, description,
                official_website, catalogue_url, access_mode, authentication_type,
                supports_anonymous_read, supports_authenticated_read, supports_manual_discovery,
                supports_api_search, created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    spec["provider_code"],
                    spec["name"],
                    spec["provider_type"],
                    spec["description"],
                    spec["official_website"],
                    spec["catalogue_url"],
                    spec["access_mode"],
                    spec["authentication_type"],
                    spec.get("supports_anonymous_read", 0),
                    spec.get("supports_authenticated_read", 0),
                    spec.get("supports_manual_discovery", 0),
                    spec.get("supports_api_search", 0),
                    SYSTEM_SEED_ADMIN_ID,
                ),
            )
            provider_id = connection.execute(
                "SELECT id FROM external_data_providers WHERE public_id=?", (public_id,)
            ).fetchone()["id"]
            for domain, domain_type in spec["domains"]:
                connection.execute(
                    """INSERT INTO external_data_provider_domains(
                    public_id, provider_id, domain, domain_type) VALUES (?,?,?,?)""",
                    (str(uuid4()), provider_id, domain, domain_type),
                )
            for capability_type in spec["capabilities"]:
                connection.execute(
                    """INSERT INTO external_data_provider_capabilities(
                    public_id, provider_id, capability_type) VALUES (?,?,?)""",
                    (str(uuid4()), provider_id, capability_type),
                )
            connection.execute(
                """INSERT INTO external_data_provider_events(
                public_id, provider_id, event_type, summary, performed_by_admin_public_id)
                VALUES (?,?,?,?,?)""",
                (
                    str(uuid4()),
                    provider_id,
                    "provider_registered",
                    "Seeded as a built-in provider template.",
                    SYSTEM_SEED_ADMIN_ID,
                ),
            )

    # -- providers ----------------------------------------------------

    def create_provider(self, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            connection.execute(
                """INSERT INTO external_data_providers(
                public_id, provider_code, name, provider_type, description,
                official_website, catalogue_url, access_mode, authentication_type,
                rate_limit_notes, terms_url, privacy_url, support_url,
                created_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    values["provider_code"],
                    values["name"],
                    values["provider_type"],
                    values.get("description", ""),
                    values.get("official_website"),
                    values.get("catalogue_url"),
                    values["access_mode"],
                    values.get("authentication_type", "none"),
                    values.get("rate_limit_notes", ""),
                    values.get("terms_url"),
                    values.get("privacy_url"),
                    values.get("support_url"),
                    values["created_by_admin_public_id"],
                ),
            )
        return self.get_provider(public_id)

    def get_provider(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                "SELECT * FROM external_data_providers WHERE public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("external data provider not found")
        return _provider_public(row)

    def get_provider_by_code(self, provider_code: str) -> dict[str, Any] | None:
        with self.transaction() as connection:
            self.ensure_builtin_providers(connection)
            row = connection.execute(
                "SELECT * FROM external_data_providers WHERE provider_code=?", (provider_code,)
            ).fetchone()
        return _provider_public(row) if row else None

    def list_providers(
        self,
        *,
        provider_type: str | None = None,
        lifecycle_status: str | None = None,
        enabled: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        limit, offset = self.pagination(limit, offset)
        clauses: list[str] = []
        params: list[Any] = []
        if provider_type:
            clauses.append("provider_type=?")
            params.append(provider_type)
        if lifecycle_status:
            clauses.append("lifecycle_status=?")
            params.append(lifecycle_status)
        if enabled is not None:
            clauses.append("enabled=?")
            params.append(int(enabled))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self.transaction() as connection:
            self.ensure_builtin_providers(connection)
            rows = connection.execute(
                f"SELECT * FROM external_data_providers {where} "  # noqa: S608
                "ORDER BY id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [_provider_public(row) for row in rows]

    def update_provider(self, public_id: str, fields: dict[str, Any]) -> dict[str, Any]:
        if not fields:
            return self.get_provider(public_id)
        assignments = ", ".join(f'"{key}"=?' for key in fields)
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT id FROM external_data_providers WHERE public_id=?", (public_id,)
            ).fetchone()
            if not current:
                raise NotFoundError("external data provider not found")
            connection.execute(
                f'UPDATE external_data_providers SET {assignments}, '  # noqa: S608
                'updated_at=CURRENT_TIMESTAMP WHERE public_id=?',
                (*fields.values(), public_id),
            )
        return self.get_provider(public_id)

    def _provider_id(self, connection: sqlite3.Connection, provider_public_id: str) -> int:
        row = connection.execute(
            "SELECT id FROM external_data_providers WHERE public_id=?", (provider_public_id,)
        ).fetchone()
        if not row:
            raise NotFoundError("external data provider not found")
        return row["id"]

    # -- domains --------------------------------------------------------

    def add_domain(self, provider_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            provider_id = self._provider_id(connection, provider_public_id)
            connection.execute(
                """INSERT INTO external_data_provider_domains(
                public_id, provider_id, domain, domain_type)
                VALUES (?,?,?,?)""",
                (public_id, provider_id, values["domain"], values["domain_type"]),
            )
        return self.get_domain(public_id)

    def get_domain(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._domain_select_sql() + " WHERE d.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("provider domain not found")
        return _domain_public(row)

    def list_domains(self, provider_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            provider_id = self._provider_id(connection, provider_public_id)
            rows = connection.execute(
                self._domain_select_sql() + " WHERE d.provider_id=? ORDER BY d.id", (provider_id,)
            ).fetchall()
        return [_domain_public(row) for row in rows]

    def verify_domain(
        self, public_id: str, *, verification_status: str, evidence: str
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT id FROM external_data_provider_domains WHERE public_id=?", (public_id,)
            ).fetchone()
            if not current:
                raise NotFoundError("provider domain not found")
            connection.execute(
                """UPDATE external_data_provider_domains SET verification_status=?,
                verification_evidence=?, verified_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (verification_status, evidence, public_id),
            )
        return self.get_domain(public_id)

    @staticmethod
    def _domain_select_sql() -> str:
        return (
            "SELECT d.*, p.public_id AS provider_public_id "
            "FROM external_data_provider_domains d "
            "JOIN external_data_providers p ON p.id = d.provider_id"
        )

    # -- capabilities -----------------------------------------------------

    def upsert_capability(self, provider_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        with self.transaction() as connection:
            provider_id = self._provider_id(connection, provider_public_id)
            existing = connection.execute(
                """SELECT public_id FROM external_data_provider_capabilities
                WHERE provider_id=? AND capability_type=?""",
                (provider_id, values["capability_type"]),
            ).fetchone()
            if existing:
                connection.execute(
                    """UPDATE external_data_provider_capabilities SET
                    language_codes_json=?, dataset_categories_json=?, connector_type=?,
                    enabled=?, configuration_json=?, updated_at=CURRENT_TIMESTAMP
                    WHERE public_id=?""",
                    (
                        dumps_json(values.get("language_codes", [])),
                        dumps_json(values.get("dataset_categories", [])),
                        values.get("connector_type"),
                        int(values.get("enabled", False)),
                        dumps_json(values.get("configuration", {})),
                        existing["public_id"],
                    ),
                )
                public_id = existing["public_id"]
            else:
                public_id = str(uuid4())
                connection.execute(
                    """INSERT INTO external_data_provider_capabilities(
                    public_id, provider_id, capability_type, language_codes_json,
                    dataset_categories_json, connector_type, enabled, configuration_json)
                    VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        public_id,
                        provider_id,
                        values["capability_type"],
                        dumps_json(values.get("language_codes", [])),
                        dumps_json(values.get("dataset_categories", [])),
                        values.get("connector_type"),
                        int(values.get("enabled", False)),
                        dumps_json(values.get("configuration", {})),
                    ),
                )
        return self.get_capability(public_id)

    def get_capability(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._capability_select_sql() + " WHERE c.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("provider capability not found")
        return _capability_public(row)

    def list_capabilities(self, provider_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            provider_id = self._provider_id(connection, provider_public_id)
            rows = connection.execute(
                self._capability_select_sql() + " WHERE c.provider_id=? ORDER BY c.id",
                (provider_id,),
            ).fetchall()
        return [_capability_public(row) for row in rows]

    @staticmethod
    def _capability_select_sql() -> str:
        return (
            "SELECT c.*, p.public_id AS provider_public_id "
            "FROM external_data_provider_capabilities c "
            "JOIN external_data_providers p ON p.id = c.provider_id"
        )

    # -- credentials --------------------------------------------------------

    def add_or_replace_credential(
        self, provider_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            provider_id = self._provider_id(connection, provider_public_id)
            existing = connection.execute(
                """SELECT public_id FROM external_data_provider_credentials
                WHERE provider_id=? AND credential_type=?""",
                (provider_id, values["credential_type"]),
            ).fetchone()
            if existing:
                connection.execute(
                    """UPDATE external_data_provider_credentials SET reference_key=?,
                    status='configured', last_rotated_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP, revoked_at=NULL WHERE public_id=?""",
                    (values["reference_key"], existing["public_id"]),
                )
                public_id = existing["public_id"]
            else:
                public_id = str(uuid4())
                connection.execute(
                    """INSERT INTO external_data_provider_credentials(
                    public_id, provider_id, credential_type, reference_key, status,
                    last_rotated_at, created_by_admin_public_id)
                    VALUES (?,?,?,?,'configured',CURRENT_TIMESTAMP,?)""",
                    (
                        public_id,
                        provider_id,
                        values["credential_type"],
                        values["reference_key"],
                        values["created_by_admin_public_id"],
                    ),
                )
        return self.get_credential(public_id)

    def get_credential(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._credential_select_sql() + " WHERE cr.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("provider credential not found")
        return _credential_public(row)

    def list_credentials(self, provider_public_id: str) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            provider_id = self._provider_id(connection, provider_public_id)
            rows = connection.execute(
                self._credential_select_sql() + " WHERE cr.provider_id=? ORDER BY cr.id",
                (provider_id,),
            ).fetchall()
        return [_credential_public(row) for row in rows]

    def set_credential_status(
        self, public_id: str, *, status: str, last_tested_at: bool = False
    ) -> dict[str, Any]:
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT id FROM external_data_provider_credentials WHERE public_id=?", (public_id,)
            ).fetchone()
            if not current:
                raise NotFoundError("provider credential not found")
            if last_tested_at:
                connection.execute(
                    """UPDATE external_data_provider_credentials SET status=?,
                    last_tested_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP
                    WHERE public_id=?""",
                    (status, public_id),
                )
            else:
                connection.execute(
                    """UPDATE external_data_provider_credentials SET status=?,
                    updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                    (status, public_id),
                )
        return self.get_credential(public_id)

    def revoke_credential(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            current = connection.execute(
                "SELECT id FROM external_data_provider_credentials WHERE public_id=?", (public_id,)
            ).fetchone()
            if not current:
                raise NotFoundError("provider credential not found")
            connection.execute(
                """UPDATE external_data_provider_credentials SET status='revoked',
                revoked_at=CURRENT_TIMESTAMP, updated_at=CURRENT_TIMESTAMP WHERE public_id=?""",
                (public_id,),
            )
        return self.get_credential(public_id)

    @staticmethod
    def _credential_select_sql() -> str:
        return (
            "SELECT cr.*, p.public_id AS provider_public_id "
            "FROM external_data_provider_credentials cr "
            "JOIN external_data_providers p ON p.id = cr.provider_id"
        )

    # -- connection tests (append-only) ------------------------------------

    def record_connection_test(
        self, provider_public_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            provider_id = self._provider_id(connection, provider_public_id)
            connection.execute(
                """INSERT INTO external_data_provider_connection_tests(
                public_id, provider_id, result, capability_type, latency_ms,
                evidence_json, error_code, tested_by_admin_public_id)
                VALUES (?,?,?,?,?,?,?,?)""",
                (
                    public_id,
                    provider_id,
                    values["result"],
                    values.get("capability_type"),
                    values.get("latency_ms"),
                    dumps_json(values.get("evidence", {})),
                    values.get("error_code"),
                    values["tested_by_admin_public_id"],
                ),
            )
        return self.get_connection_test(public_id)

    def get_connection_test(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._connection_test_select_sql() + " WHERE t.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("connection test not found")
        return _connection_test_public(row)

    def list_connection_tests(
        self, provider_public_id: str, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            provider_id = self._provider_id(connection, provider_public_id)
            rows = connection.execute(
                self._connection_test_select_sql()
                + " WHERE t.provider_id=? ORDER BY t.id DESC LIMIT ?",
                (provider_id, limit),
            ).fetchall()
        return [_connection_test_public(row) for row in rows]

    @staticmethod
    def _connection_test_select_sql() -> str:
        return (
            "SELECT t.*, p.public_id AS provider_public_id "
            "FROM external_data_provider_connection_tests t "
            "JOIN external_data_providers p ON p.id = t.provider_id"
        )

    # -- events (append-only) -----------------------------------------------

    def record_event(self, provider_public_id: str, values: dict[str, Any]) -> dict[str, Any]:
        public_id = str(uuid4())
        with self.transaction() as connection:
            provider_id = self._provider_id(connection, provider_public_id)
            connection.execute(
                """INSERT INTO external_data_provider_events(
                public_id, provider_id, event_type, summary, metadata_json,
                performed_by_admin_public_id)
                VALUES (?,?,?,?,?,?)""",
                (
                    public_id,
                    provider_id,
                    values["event_type"],
                    values.get("summary", ""),
                    dumps_json(values.get("metadata", {})),
                    values["performed_by_admin_public_id"],
                ),
            )
        return self.get_event(public_id)

    def get_event(self, public_id: str) -> dict[str, Any]:
        with self.transaction() as connection:
            row = connection.execute(
                self._event_select_sql() + " WHERE e.public_id=?", (public_id,)
            ).fetchone()
        if not row:
            raise NotFoundError("provider event not found")
        return _event_public(row)

    def list_events(self, provider_public_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        with self.transaction() as connection:
            provider_id = self._provider_id(connection, provider_public_id)
            rows = connection.execute(
                self._event_select_sql() + " WHERE e.provider_id=? ORDER BY e.id DESC LIMIT ?",
                (provider_id, limit),
            ).fetchall()
        return [_event_public(row) for row in rows]

    @staticmethod
    def _event_select_sql() -> str:
        return (
            "SELECT e.*, p.public_id AS provider_public_id "
            "FROM external_data_provider_events e "
            "JOIN external_data_providers p ON p.id = e.provider_id"
        )
