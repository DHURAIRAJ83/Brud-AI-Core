"""Phase 1 chatbot placeholder endpoint."""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(tags=["chat"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    language: Literal["auto", "ta", "en", "tanglish"] = "auto"


class ChatResponse(BaseModel):
    reply: str
    detected_language: str
    model: str
    phase: int


@router.post("/chat", response_model=ChatResponse)
async def chat(_: ChatRequest) -> ChatResponse:
    """Return an explicit non-AI placeholder without storing private messages."""

    return ChatResponse(
        reply="Brud AI chatbot foundation is working.",
        detected_language="unknown",
        model="placeholder",
        phase=1,
    )
