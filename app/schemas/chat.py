from __future__ import annotations

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class SendMessageRequest(BaseModel):
    message: str = Field(..., max_length=10000)
    sessionId: str | None = None


class ChatSessionResponse(BaseModel):
    id: str
    title: str | None
    createdAt: str | None
    updatedAt: str | None


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    metadata: dict | None
    createdAt: str | None


class SendMessageResponse(BaseModel):
    session: ChatSessionResponse
    response: MessageResponse
