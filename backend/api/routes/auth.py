"""Cookie-based local administrator authentication API."""

from fastapi import APIRouter, HTTPException, Request, Response, status

from backend.api.auth import AdminDependency, CsrfDependency
from backend.api.dependencies import SettingsDependency
from backend.database.repositories.admin import AdminRepository, AuthenticationError
from backend.models.auth import (
    AuthenticatedResponse,
    CurrentAdminResponse,
    LoginRequest,
)

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


@router.post("/login", response_model=AuthenticatedResponse)
async def login(
    payload: LoginRequest, response: Response, settings: SettingsDependency
) -> AuthenticatedResponse:
    repository = AdminRepository(settings.resolved_database_path)
    try:
        admin = repository.authenticate(
            payload.username,
            payload.password,
            max_failures=settings.admin_max_failed_logins,
            lockout_minutes=settings.admin_lockout_minutes,
        )
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password"
        ) from exc
    token, csrf, _ = repository.create_session(admin.public_id, settings.admin_session_ttl_minutes)
    max_age = settings.admin_session_ttl_minutes * 60
    response.set_cookie(
        settings.admin_cookie_name,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.admin_cookie_secure,
        samesite="strict",
        path="/api/admin",
    )
    response.set_cookie(
        settings.csrf_cookie_name,
        csrf,
        max_age=max_age,
        httponly=False,
        secure=settings.admin_cookie_secure,
        samesite="strict",
        path="/api/admin",
    )
    return AuthenticatedResponse(admin=admin)


@router.get("/me", response_model=CurrentAdminResponse)
async def me(context: AdminDependency) -> CurrentAdminResponse:
    return CurrentAdminResponse(admin=context.admin, session=context.session)


@router.get("/csrf")
async def csrf(request: Request, _: AdminDependency) -> dict[str, str]:
    settings = request.app.state.settings
    token = request.cookies.get(settings.csrf_cookie_name)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    return {"csrf_token": token, "header_name": settings.csrf_header_name}


@router.post("/logout")
async def logout(
    response: Response,
    settings: SettingsDependency,
    context: CsrfDependency,
) -> dict[str, bool]:
    AdminRepository(settings.resolved_database_path).logout(context.token)
    response.delete_cookie(settings.admin_cookie_name, path="/api/admin")
    response.delete_cookie(settings.csrf_cookie_name, path="/api/admin")
    return {"authenticated": False}
