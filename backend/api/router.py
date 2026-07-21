"""Top-level API router."""

from fastapi import APIRouter

from backend.api.routes import admin, chat, health

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(chat.router)
api_router.include_router(admin.router)
