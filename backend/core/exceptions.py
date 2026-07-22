"""Application exceptions and centralized FastAPI handlers."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.database.repositories.base import ConflictError, NotFoundError, RepositoryError

logger = logging.getLogger(__name__)


class BrudError(Exception):
    """Base class for expected application errors."""

    status_code = 500
    code = "brud_error"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def register_exception_handlers(app: FastAPI) -> None:
    """Register consistent JSON responses without exposing internal details."""

    @app.exception_handler(BrudError)
    async def handle_brud_error(request: Request, exc: BrudError) -> JSONResponse:
        logger.warning(
            "application_request_failed",
            extra={"path": request.url.path, "error_code": exc.code},
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(RepositoryError)
    async def handle_repository_error(request: Request, exc: RepositoryError) -> JSONResponse:
        status_code = (
            404
            if isinstance(exc, NotFoundError)
            else 409
            if isinstance(exc, ConflictError)
            else 422
        )
        logger.warning(
            "repository_request_rejected",
            extra={"path": request.url.path, "error_type": type(exc).__name__},
        )
        return JSONResponse(
            status_code=status_code,
            content={"error": {"code": "request_rejected", "message": str(exc)}},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unexpected_request_failure", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Internal server error"}},
        )
