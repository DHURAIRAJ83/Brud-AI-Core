"""Reusable admin session and CSRF dependencies."""

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from backend.core.config import Settings
from backend.database.repositories.admin import (
    AdminRepository,
    AuthenticationError,
    AuthorizationError,
)
from backend.models.auth import AdminPublic, SessionPublic


@dataclass(frozen=True)
class AdminContext:
    admin: AdminPublic
    session: SessionPublic
    session_id: int
    token: str


async def require_admin(request: Request) -> AdminContext:
    settings: Settings = request.app.state.settings
    token = request.cookies.get(settings.admin_cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    try:
        admin, session, session_id = AdminRepository(
            settings.resolved_database_path
        ).validate_session(token)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        ) from exc
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied") from exc
    return AdminContext(admin=admin, session=session, session_id=session_id, token=token)


AdminDependency = Annotated[AdminContext, Depends(require_admin)]


async def require_csrf(request: Request, context: AdminDependency) -> AdminContext:
    settings: Settings = request.app.state.settings
    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(settings.csrf_header_name)
    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    if not AdminRepository(settings.resolved_database_path).validate_csrf(
        context.session_id, header_token
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF validation failed")
    return context


CsrfDependency = Annotated[AdminContext, Depends(require_csrf)]
