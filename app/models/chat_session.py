from __future__ import annotations

import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Index, func
from sqlalchemy.orm import relationship

from ..db.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String, nullable=True)
    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    is_active = Column("isActive", Boolean, default=True, nullable=False)
    created_at = Column("createdAt", DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        "updatedAt", DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan"
    )


Index("ix_chat_sessions_user_created", ChatSession.user_id, ChatSession.created_at)
Index("ix_chat_sessions_user", ChatSession.user_id)
