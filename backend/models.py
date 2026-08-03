"""Pydantic request/response schemas for the FastAPI backend."""

from typing import Optional

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None  # omit on the first message; server creates one
    language: Optional[str] = (
        "auto"  # "auto" (match question language) or an ISO code like "en"
    )


class SourceOut(BaseModel):
    source: str
    title: str
    url: str
    score: float


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[SourceOut]
