"""MB-02: Brud Knowledge Core -- authenticated admin-only APIs.

Prefix is `/admin/mini-brain/knowledge-core`, deliberately distinct
from MB-01's own `GET /admin/mini-brain/knowledge` placeholder (that
route stays exactly as MB-01 left it, still returning
`available: false` -- wiring it to this real catalog is left to a
future phase, per MB-02's own "future compatibility, not integration"
scope). Structured search only: no query parameter here ever triggers
an embedding or similarity computation.
"""

from fastapi import APIRouter, Depends, Query

from backend.api.auth import CsrfDependency, require_admin
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.mini_brain_knowledge import MiniBrainKnowledgeRepository
from backend.models.mini_brain_knowledge import KnowledgeItemCreate, KnowledgeRelationshipCreate
from backend.services.mini_brain_knowledge_service import MiniBrainKnowledgeService

router = APIRouter(
    prefix="/admin/mini-brain/knowledge-core",
    tags=["admin-mini-brain-knowledge-core"],
    dependencies=[Depends(require_admin)],
)


def service(settings) -> MiniBrainKnowledgeService:
    return MiniBrainKnowledgeService(
        MiniBrainKnowledgeRepository(settings.resolved_database_path), settings
    )


@router.post("/seed")
async def seed(settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).seed_defaults(admin.admin.public_id)


@router.get("/domains")
async def domains(settings: SettingsDependency):
    return service(settings).list_domains()


@router.get("/items")
async def items(
    settings: SettingsDependency,
    domain: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).list_items(domain, limit, offset)


@router.get("/items/{public_id}")
async def item(public_id: str, settings: SettingsDependency):
    return service(settings).get_item(public_id)


@router.post("/items")
async def create_item(payload: KnowledgeItemCreate, settings: SettingsDependency, admin: CsrfDependency):
    body = payload.model_dump()
    domain_key = body.pop("domain")
    return service(settings).create_item(domain_key, body, admin.admin.public_id)


@router.get("/search")
async def search(
    settings: SettingsDependency,
    q: str | None = Query(default=None),
    category: str | None = Query(default=None),
    tag: str | None = Query(default=None),
    domain: str | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    return service(settings).search(
        query=q, category=category, tag=tag, domain_key=domain, status=status,
        limit=limit, offset=offset,
    )


@router.post("/relationships")
async def create_relationship(
    payload: KnowledgeRelationshipCreate, settings: SettingsDependency, admin: CsrfDependency,
):
    return service(settings).create_relationship(
        payload.from_public_id, payload.to_public_id, payload.relationship_type, payload.description,
    )


@router.post("/validate")
async def validate(settings: SettingsDependency, admin: CsrfDependency):
    return service(settings).run_validation(admin.admin.public_id)


@router.get("/validation-reports")
async def validation_reports(settings: SettingsDependency, limit: int = Query(default=10, ge=1, le=50)):
    return service(settings).list_validation_reports(limit)


@router.get("/coverage")
async def coverage(settings: SettingsDependency):
    return service(settings).coverage()


@router.get("/diagnostics")
async def diagnostics(settings: SettingsDependency):
    return service(settings).diagnostics()
