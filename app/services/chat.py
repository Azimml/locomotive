from __future__ import annotations

from sqlalchemy.orm import Session
from datetime import datetime, timezone
from fastapi import HTTPException, status

from ..models.chat_session import ChatSession
from ..models.message import Message
from .ai import AiService


class ChatService:
    def __init__(self, db: Session, ai_service: AiService):
        self.db = db
        self.ai_service = ai_service

    def create_session(self, user_id: str, title: str | None = None) -> ChatSession:
        session = ChatSession(user_id=user_id, title=title or "Yangi suhbat")
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_user_sessions(self, user_id: str) -> list[ChatSession]:
        return (
            self.db.query(ChatSession)
            .filter(ChatSession.user_id == user_id, ChatSession.is_active == True)
            .order_by(ChatSession.updated_at.desc())
            .all()
        )

    def get_session_by_id(self, session_id: str, user_id: str) -> ChatSession:
        session = (
            self.db.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.user_id == user_id)
            .first()
        )
        if not session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Session topilmadi"
            )
        return session

    def get_session_messages(
        self, session_id: str, user_id: str, limit: int = 50, offset: int = 0
    ) -> list[Message]:
        self.get_session_by_id(session_id, user_id)
        return (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def send_message(self, user_id: str, message: str, session_id: str | None = None):
        if session_id:
            session = self.get_session_by_id(session_id, user_id)
        else:
            session = self.create_session(user_id, self._generate_session_title(message))

        user_message = self._save_message(session.id, "user", message)

        conversation_history = self._get_conversation_history(session.id)
        ai_response = self.ai_service.process_message(message, conversation_history)

        assistant_message = self._save_message(
            session.id,
            "assistant",
            ai_response["content"],
            ai_response.get("metadata"),
        )

        session.updated_at = datetime.now(timezone.utc)
        self.db.add(session)
        self.db.commit()

        return {
            "session": session,
            "response": assistant_message,
        }

    def delete_session(self, session_id: str, user_id: str) -> None:
        session = self.get_session_by_id(session_id, user_id)
        session.is_active = False
        self.db.add(session)
        self.db.commit()

    def _save_message(
        self, session_id: str, role: str, content: str, metadata: dict | None = None
    ) -> Message:
        message = Message(
            session_id=session_id,
            role=role,
            content=content,
            metadata_json=metadata,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def _get_conversation_history(self, session_id: str, limit: int = 20):
        messages = (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
            .all()
        )
        return list(reversed([{"role": m.role, "content": m.content} for m in messages]))

    def _generate_session_title(self, message: str) -> str:
        return message if len(message) <= 50 else message[:50] + "..."
