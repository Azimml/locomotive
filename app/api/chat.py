from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..api.deps import get_current_user
from ..db.deps import get_db
from ..schemas.chat import (
    CreateSessionRequest,
    SendMessageRequest,
    ChatSessionResponse,
    MessageResponse,
    SendMessageResponse,
)
from ..services.chat import ChatService
from ..services.ai import AiService

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _session_to_response(session) -> ChatSessionResponse:
    return ChatSessionResponse(
        id=str(session.id),
        title=session.title,
        createdAt=session.created_at.isoformat() if session.created_at else None,
        updatedAt=session.updated_at.isoformat() if session.updated_at else None,
    )


def _message_to_response(message) -> MessageResponse:
    return MessageResponse(
        id=str(message.id),
        role=message.role,
        content=message.content,
        metadata=message.metadata_json,
        createdAt=message.created_at.isoformat() if message.created_at else None,
    )


@router.post("/sessions", response_model=ChatSessionResponse)
def create_session(
    payload: CreateSessionRequest | None = None,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    service = ChatService(db, AiService())
    session = service.create_session(user["id"], payload.title if payload else None)
    return _session_to_response(session)


@router.get("/sessions", response_model=list[ChatSessionResponse])
def get_user_sessions(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    service = ChatService(db, AiService())
    sessions = service.get_user_sessions(user["id"])
    return [_session_to_response(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
def get_session(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    service = ChatService(db, AiService())
    session = service.get_session_by_id(session_id, user["id"])
    return _session_to_response(session)


@router.get("/sessions/{session_id}/messages", response_model=list[MessageResponse])
def get_session_messages(
    session_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    service = ChatService(db, AiService())
    messages = service.get_session_messages(session_id, user["id"], limit, offset)
    return [_message_to_response(m) for m in messages]


@router.post("/send", response_model=SendMessageResponse)
def send_message(
    payload: SendMessageRequest,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    service = ChatService(db, AiService())
    result = service.send_message(user["id"], payload.message, payload.sessionId)
    return SendMessageResponse(
        session=_session_to_response(result["session"]),
        response=_message_to_response(result["response"]),
    )


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    service = ChatService(db, AiService())
    service.delete_session(session_id, user["id"])
    return {"success": True}
